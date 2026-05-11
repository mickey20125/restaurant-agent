from __future__ import annotations

import gzip
import json
import os
import time
from datetime import date
from pathlib import Path

DEFAULT_THREADS_CACHE_PATH = ".cache/threads_cache.json"
DEFAULT_THREADS_USAGE_PATH = ".cache/threads_daily_usage.json"


class ThreadsScraper:
    """Fetch Threads post snippets for a restaurant via Brave Search API.

    Searches `site:threads.net "<name>"` using the Brave Search API.

    Required env vars:
      BRAVE_SEARCH_API_KEY — Brave Search API key (free tier: 2000 queries/month)
    """

    def __init__(
        self,
        *,
        cache_path: str = DEFAULT_THREADS_CACHE_PATH,
        usage_path: str = DEFAULT_THREADS_USAGE_PATH,
        cache_ttl_seconds: int = 3600,
        daily_limit: int = 50,
        monthly_limit: int = 2000,
        headless: bool = True,  # kept for call-site backward compat
    ) -> None:
        del headless
        self.cache_path = Path(cache_path)
        self.usage_path = Path(usage_path)
        self.cache_ttl_seconds = cache_ttl_seconds
        self.daily_limit = daily_limit
        self.monthly_limit = monthly_limit

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

        allowed, budget_error = self._allow_usage()
        if not allowed:
            return [], {"budget": budget_error}

        try:
            posts, errors = self._scrape(name, max_posts)
        except Exception as exc:
            return [], {"scrape": str(exc)}

        self._put_cached(name, posts)
        return posts, errors

    def get_monthly_usage(self) -> int:
        """Return total Brave Search API calls made this calendar month."""
        if not self.usage_path.exists():
            return 0
        try:
            payload = json.loads(self.usage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return 0
        month = date.today().isoformat()[:7]  # YYYY-MM
        return sum(int(v) for k, v in payload.items() if k.startswith(month))

    # ------------------------------------------------------------------
    # Scraping
    # ------------------------------------------------------------------

    def _scrape(self, name: str, max_posts: int) -> tuple[list[dict], dict[str, str]]:
        brave_key = os.environ.get("BRAVE_SEARCH_API_KEY", "")
        if not brave_key:
            return [], {"scrape": "BRAVE_SEARCH_API_KEY not configured"}

        posts = self._scrape_via_brave(name, brave_key, max_posts)
        if posts:
            return posts[:max_posts], {}
        return [], {"scrape": "no Threads results found on Brave Search"}

    def _scrape_via_brave(self, name: str, api_key: str, max_posts: int) -> list[dict]:
        """Search site:threads.net via Brave Search API."""
        import urllib.request
        import urllib.parse

        params = urllib.parse.urlencode({
            "q": f'site:threads.net "{name}"',
            "count": min(max_posts, 20),
            "search_lang": "zh-hant",
        })
        req = urllib.request.Request(
            f"https://api.search.brave.com/res/v1/web/search?{params}",
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
                if resp.info().get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                data = json.loads(raw.decode("utf-8", errors="ignore"))
        except Exception as exc:
            raise RuntimeError(f"Brave Search failed: {exc}") from exc

        posts: list[dict] = []
        _generic = ("join threads to share", "we cannot provide a description")
        for item in data.get("web", {}).get("results", []):
            desc = (item.get("description", "") or "").strip()
            title = (item.get("title", "") or "").strip()
            # description is often Threads' generic login prompt; prefer title
            text = title if any(g in desc.lower() for g in _generic) else (desc or title)
            text = text.replace("\n", " ").strip()
            if len(text) >= 15:
                posts.append({"text": text, "like_count": 0})
        return posts

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
    # Usage guard (daily + monthly)
    # ------------------------------------------------------------------

    def _allow_usage(self) -> tuple[bool, str]:
        """Return (allowed, error_message). Enforces both daily and monthly limits."""
        payload: dict = {}
        if self.usage_path.exists():
            try:
                payload = json.loads(self.usage_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        today = date.today().isoformat()
        month = today[:7]  # YYYY-MM

        current_day = int(payload.get(today, 0))
        if current_day >= self.daily_limit:
            return False, f"daily limit reached ({current_day}/{self.daily_limit})"

        current_month = sum(int(v) for k, v in payload.items() if k.startswith(month))
        if current_month >= self.monthly_limit:
            return False, f"monthly limit reached ({current_month}/{self.monthly_limit})"

        payload[today] = current_day + 1
        self.usage_path.parent.mkdir(parents=True, exist_ok=True)
        self.usage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return True, ""

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
        monthly_limit: int = 2000,
        headless: bool = True,  # kept for call-site backward compat
    ) -> "ThreadsScraper | None":
        """Return a ThreadsScraper unless THREADS_ENABLED=false."""
        del headless
        if os.environ.get("THREADS_ENABLED", "true").lower() == "false":
            return None
        monthly_limit = int(os.environ.get("BRAVE_MONTHLY_LIMIT", monthly_limit))
        return cls(
            cache_path=cache_path,
            usage_path=usage_path,
            cache_ttl_seconds=cache_ttl_seconds,
            daily_limit=daily_limit,
            monthly_limit=monthly_limit,
        )
