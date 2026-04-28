from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

DEFAULT_THREADS_CACHE_PATH = ".cache/threads_cache.json"
DEFAULT_THREADS_USAGE_PATH = ".cache/threads_daily_usage.json"


class ThreadsScraper:
    """Scrape Threads.net public search results (no login required).

    Fetches post captions for a restaurant name via:
      https://www.threads.net/search?q={name}&serp_type=keyword

    Uses Playwright (headless Chromium) with:
    1. GraphQL/API response interception as the primary extraction path
    2. DOM text extraction as fallback
    """

    def __init__(
        self,
        *,
        cache_path: str = DEFAULT_THREADS_CACHE_PATH,
        usage_path: str = DEFAULT_THREADS_USAGE_PATH,
        cache_ttl_seconds: int = 3600,
        daily_limit: int = 50,
        headless: bool = True,
    ) -> None:
        self.cache_path = Path(cache_path)
        self.usage_path = Path(usage_path)
        self.cache_ttl_seconds = cache_ttl_seconds
        self.daily_limit = daily_limit
        self.headless = headless

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_for_candidate(
        self,
        *,
        name: str,
        max_posts: int = 10,
    ) -> tuple[list[str], dict[str, str]]:
        """Return (captions, errors). errors is empty dict on success."""
        posts_with_meta, errors = self.fetch_posts_with_engagement(name=name, max_posts=max_posts)
        return [p["text"] for p in posts_with_meta], errors

    def fetch_posts_with_engagement(
        self,
        *,
        name: str,
        max_posts: int = 10,
    ) -> tuple[list[dict], dict[str, str]]:
        """Return (posts, errors) where each post is {"text": str, "like_count": int}."""
        cached = self._get_cached(name)
        if cached is not None:
            return cached, {}

        if not self._allow_usage():
            return [], {"budget": "daily limit reached"}

        try:
            posts, errors = self._scrape(name, max_posts)
        except Exception as exc:
            return [], {"scrape": str(exc)}

        self._put_cached(name, posts)
        return posts, errors

    # ------------------------------------------------------------------
    # Playwright scraping
    # ------------------------------------------------------------------

    def _scrape(self, name: str, max_posts: int) -> tuple[list[dict], dict[str, str]]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "playwright is not installed. Run: pip install playwright && playwright install chromium"
            ) from exc

        posts: list[dict] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.headless)
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="zh-TW",
            )
            page = ctx.new_page()

            # Intercept API / GraphQL JSON responses
            captured: list[Any] = []

            def _on_response(response: Any) -> None:
                url = response.url
                if not any(kw in url for kw in ("graphql", "/api/", "search")):
                    return
                ct = response.headers.get("content-type", "")
                if "json" not in ct:
                    return
                try:
                    captured.append(response.json())
                except Exception:
                    pass

            page.on("response", _on_response)

            url = self._build_search_url(name)
            try:
                page.goto(url, timeout=30_000, wait_until="networkidle")
            except Exception:
                try:
                    page.goto(url, timeout=30_000, wait_until="domcontentloaded")
                    page.wait_for_timeout(4000)
                except Exception:
                    pass

            # Extract from captured API responses (with engagement)
            seen: set[str] = set()
            for body in captured:
                for post in self._extract_posts_from_json(body):
                    if post["text"] not in seen:
                        seen.add(post["text"])
                        posts.append(post)
                    if len(posts) >= max_posts:
                        break
                if len(posts) >= max_posts:
                    break

            # DOM fallback when API extraction yielded nothing
            if len(posts) < 3:
                for text in self._extract_from_dom(page):
                    if text not in seen:
                        seen.add(text)
                        posts.append({"text": text, "like_count": 0})
                    if len(posts) >= max_posts:
                        break

            browser.close()

        return posts[:max_posts], {}

    @staticmethod
    def _build_search_url(name: str) -> str:
        return f"https://www.threads.net/search?q={quote(name)}&serp_type=keyword"

    # ------------------------------------------------------------------
    # JSON extraction helpers
    # ------------------------------------------------------------------

    def _extract_posts_from_json(self, obj: Any, depth: int = 0) -> list[dict]:
        """Recursively extract posts with engagement from Threads API JSON blobs.

        Returns list of {"text": str, "like_count": int}.
        like_count is 0 when the API response doesn't include engagement data.
        """
        if depth > 12:
            return []
        results: list[dict] = []
        if isinstance(obj, dict):
            for key in ("text", "caption", "body", "content", "message"):
                val = obj.get(key)
                if isinstance(val, str) and len(val) > 10:
                    like_count = obj.get("like_count", 0)
                    results.append({
                        "text": val,
                        "like_count": like_count if isinstance(like_count, int) else 0,
                    })
            for val in obj.values():
                results.extend(self._extract_posts_from_json(val, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                results.extend(self._extract_posts_from_json(item, depth + 1))
        return results

    def _extract_texts_from_json(self, obj: Any, depth: int = 0) -> list[str]:
        """Recursively find caption/text strings in Threads API JSON blobs."""
        return [p["text"] for p in self._extract_posts_from_json(obj, depth)]

    # ------------------------------------------------------------------
    # DOM fallback
    # ------------------------------------------------------------------

    # Threads page UI strings that appear in DOM but are not user posts
    _UI_NOISE: frozenset[str] = frozenset([
        "查看人們談論的主題，並加入對話。",
        "使用 Instagram 帳號繼續",
        "繼續使用 Facebook",
        "登入",
        "Sign in",
        "Log in",
        "Join the conversation",
        "See what people are talking about",
        "Continue with Instagram",
        "Continue with Facebook",
    ])

    def _is_ui_noise(self, text: str) -> bool:
        return text in self._UI_NOISE or len(text) < 15

    def _extract_from_dom(self, page: Any) -> list[str]:
        selectors = [
            "article span",
            "[data-pressable-container] span",
            "div[dir='auto']",
            "span[class*='x1lliihq']",  # common Threads text class prefix
        ]
        texts: list[str] = []
        seen: set[str] = set()
        for sel in selectors:
            try:
                elements = page.query_selector_all(sel)
                for el in elements:
                    t = el.inner_text().strip()
                    if t and not self._is_ui_noise(t) and t not in seen:
                        seen.add(t)
                        texts.append(t)
            except Exception:
                pass
            if len(texts) >= 30:
                break
        return texts

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _get_cached(self, name: str) -> list[dict] | None:
        if not self.cache_path.exists():
            return None
        try:
            payload: dict = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        entry = payload.get(name)
        if not entry:
            return None
        if int(time.time()) - int(entry.get("cached_at", 0)) > self.cache_ttl_seconds:
            return None
        data = entry.get("data", [])
        # Backward compat: old cache stored list[str], upgrade on read
        if data and isinstance(data[0], str):
            return [{"text": t, "like_count": 0} for t in data]
        return data

    def _put_cached(self, name: str, posts: list[dict]) -> None:
        payload: dict = {}
        if self.cache_path.exists():
            try:
                payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        payload[name] = {
            "cached_at": int(time.time()),
            "data": posts,
        }
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    # Daily usage guard
    # ------------------------------------------------------------------

    def _allow_usage(self) -> bool:
        payload: dict = {}
        if self.usage_path.exists():
            try:
                payload = json.loads(self.usage_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        today = date.today().isoformat()
        current = int(payload.get(today, 0))
        if current >= self.daily_limit:
            return False
        payload[today] = current + 1
        self.usage_path.parent.mkdir(parents=True, exist_ok=True)
        self.usage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(
        cls,
        *,
        cache_path: str = DEFAULT_THREADS_CACHE_PATH,
        usage_path: str = DEFAULT_THREADS_USAGE_PATH,
        cache_ttl_seconds: int = 3600,
        daily_limit: int = 50,
        headless: bool = True,
    ) -> "ThreadsScraper | None":
        """Return a ThreadsScraper unless THREADS_ENABLED=false."""
        if os.environ.get("THREADS_ENABLED", "true").lower() == "false":
            return None
        return cls(
            cache_path=cache_path,
            usage_path=usage_path,
            cache_ttl_seconds=cache_ttl_seconds,
            daily_limit=daily_limit,
            headless=headless,
        )
