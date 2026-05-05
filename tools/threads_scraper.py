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
    """Fetch Threads post snippets for a restaurant via Google Custom Search.

    Searches `site:threads.net "<name>"` using the Google Custom Search JSON API,
    which requires no Threads authentication.

    Required env vars:
      GOOGLE_MAPS_API_KEY  — existing Google API key (must have Custom Search API enabled)
      GOOGLE_SEARCH_CX     — Custom Search Engine ID from programmablesearch.google.com
    """

    def __init__(
        self,
        *,
        cache_path: str = DEFAULT_THREADS_CACHE_PATH,
        usage_path: str = DEFAULT_THREADS_USAGE_PATH,
        cache_ttl_seconds: int = 3600,
        daily_limit: int = 50,
        # kept for call-site backward compat
        headless: bool = True,
    ) -> None:
        self.cache_path = Path(cache_path)
        self.usage_path = Path(usage_path)
        self.cache_ttl_seconds = cache_ttl_seconds
        self.daily_limit = daily_limit

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
    # Scraping
    # ------------------------------------------------------------------

    def _scrape(self, name: str, max_posts: int) -> tuple[list[dict], dict[str, str]]:
        google_cx = os.environ.get("GOOGLE_SEARCH_CX", "")
        # Prefer a dedicated key; fall back to the Maps key if not set
        google_key = (
            os.environ.get("GOOGLE_SEARCH_API_KEY")
            or os.environ.get("GOOGLE_MAPS_API_KEY", "")
        )
        if not google_cx or not google_key:
            return [], {"scrape": "GOOGLE_SEARCH_CX not configured"}

        posts = self._scrape_via_google(name, google_key, google_cx, max_posts)
        if posts:
            return posts[:max_posts], {}
        return [], {"scrape": "no Threads results found on Google"}

    def _scrape_via_google(
        self, name: str, api_key: str, cx: str, max_posts: int
    ) -> list[dict]:
        """Search site:threads.net via Google Custom Search API."""
        import urllib.request
        import urllib.parse

        params = urllib.parse.urlencode({
            "key": api_key,
            "cx": cx,
            "q": f'site:threads.net "{name}"',
            "num": min(max_posts, 10),
            "lr": "lang_zh-TW",
        })
        req = urllib.request.Request(
            f"https://www.googleapis.com/customsearch/v1?{params}",
            headers={"accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        except Exception as exc:
            raise RuntimeError(f"Google Custom Search failed: {exc}") from exc

        posts: list[dict] = []
        for item in data.get("items", []):
            text = (item.get("snippet", "") or item.get("title", "")).replace("\n", " ").strip()
            if len(text) >= 15:
                posts.append({"text": text, "like_count": 0})
        return posts

    # ------------------------------------------------------------------
    # JSON extraction helpers (used by tests and future API integrations)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_search_url(name: str) -> str:
        return f"https://www.threads.net/search?q={quote(name)}&serp_type=keyword"

    def _extract_texts_from_json(self, obj: Any, depth: int = 0) -> list[str]:
        return [p["text"] for p in self._extract_posts_from_json(obj, depth)]

    def _extract_posts_from_json(self, obj: Any, depth: int = 0) -> list[dict]:
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
        payload[name] = {"cached_at": int(time.time()), "data": posts}
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
        )
