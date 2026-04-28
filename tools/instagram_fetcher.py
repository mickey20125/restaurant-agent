from __future__ import annotations

import json
import os
import re
import time
from datetime import date
from pathlib import Path
from typing import Any

DEFAULT_SESSION_PATH = ".cache/instagram_session.json"
DEFAULT_IG_CACHE_PATH = ".cache/instagram_cache.json"
DEFAULT_IG_USAGE_PATH = ".cache/instagram_daily_usage.json"


class InstagramFetcher:
    """Fetch Instagram post captions for a restaurant candidate.

    Searches via two signals in parallel and deduplicates:
    1. Hashtag search  — #{store_name}
    2. Location search — nearest IG location to candidate lat/lng
    """

    def __init__(
        self,
        *,
        username: str = "",
        password: str = "",
        sessionid: str = "",
        session_path: str = DEFAULT_SESSION_PATH,
        cache_path: str = DEFAULT_IG_CACHE_PATH,
        usage_path: str = DEFAULT_IG_USAGE_PATH,
        cache_ttl_seconds: int = 3600,
        daily_limit: int = 100,
    ) -> None:
        self.username = username
        self.password = password
        self.sessionid = sessionid
        self.session_path = Path(session_path)
        self.cache_path = Path(cache_path)
        self.usage_path = Path(usage_path)
        self.cache_ttl_seconds = cache_ttl_seconds
        self.daily_limit = daily_limit
        self._client: Any = None  # instagrapi.Client, lazy-init on first use

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_for_candidate(
        self,
        *,
        name: str,
        lat: float | None,
        lng: float | None,
        max_posts: int = 10,
    ) -> tuple[list[str], dict[str, str | None]]:
        """Return (captions, errors) from hashtag + location search, deduplicated.

        errors keys: "hashtag", "location" — None means success.
        """
        cached = self._get_cached(name, lat, lng)
        if cached is not None:
            return cached, {}

        if not self._allow_usage():
            return [], {"budget": "daily limit reached"}

        posts: list[str] = []
        seen: set[str] = set()
        errors: dict[str, str | None] = {}

        hashtag_posts, errors["hashtag"] = self._fetch_by_hashtag(
            self._to_hashtag(name), max_posts
        )
        for text in hashtag_posts:
            if text not in seen:
                seen.add(text)
                posts.append(text)

        if lat is not None and lng is not None:
            location_posts, errors["location"] = self._fetch_by_location(lat, lng, max_posts)
            for text in location_posts:
                if text not in seen:
                    seen.add(text)
                    posts.append(text)

        self._put_cached(name, lat, lng, posts)
        return posts, {k: v for k, v in errors.items() if v is not None}

    # ------------------------------------------------------------------
    # Challenge resolution (interactive, one-time per new IP)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_challenge(cl: Any) -> None:
        """Handle Instagram security challenge by prompting user for the verification code."""
        try:
            cl.challenge_resolve(cl.last_json)
        except Exception:
            pass  # some flows don't need this step

        print("\n[Instagram] 需要驗證身份：請到手機 Instagram App 或信箱查看驗證碼")
        code = input("[Instagram] 輸入驗證碼：").strip()
        if not code:
            raise RuntimeError("未輸入驗證碼，登入中止。")
        cl.challenge_send_security_code(code)

    # ------------------------------------------------------------------
    # Search backends
    # ------------------------------------------------------------------

    def _fetch_by_hashtag(self, hashtag: str, max_posts: int) -> tuple[list[str], str | None]:
        """Returns (captions, error_message | None)."""
        try:
            cl = self._get_client()
            medias = cl.hashtag_medias_top(hashtag, amount=max_posts)
            return [m.caption_text for m in medias if m.caption_text], None
        except Exception as exc:
            return [], str(exc)

    def _fetch_by_location(self, lat: float, lng: float, max_posts: int) -> tuple[list[str], str | None]:
        """Returns (captions, error_message | None)."""
        try:
            cl = self._get_client()
            locations = cl.location_search(lat, lng)
            if not locations:
                return [], "no locations found near coordinates"
            medias = cl.location_medias_recent(locations[0].pk, amount=max_posts)
            return [m.caption_text for m in medias if m.caption_text], None
        except Exception as exc:
            return [], str(exc)

    # ------------------------------------------------------------------
    # Client / session management
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from instagrapi import Client
        except ImportError as exc:
            raise RuntimeError(
                "instagrapi is not installed. Run: pip install instagrapi"
            ) from exc

        cl = Client()

        if self.session_path.exists():
            try:
                cl.load_settings(str(self.session_path))
                cl.account_info()  # lightweight verify, avoids re-login
                self._client = cl
                return cl
            except Exception:
                pass  # session stale or invalid — fall through to fresh login

        # Fresh login via username + password (only reliable method for mobile API)
        if self.username and self.password:
            try:
                cl.login(self.username, self.password)
            except Exception as exc:
                if "challenge_required" in str(exc).lower():
                    self._resolve_challenge(cl)
                else:
                    raise
        else:
            raise RuntimeError(
                "Instagram credentials missing: set INSTAGRAM_USERNAME + INSTAGRAM_PASSWORD in .env"
            )

        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        cl.dump_settings(str(self.session_path))
        self._client = cl
        return cl

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _cache_key(self, name: str, lat: float | None, lng: float | None) -> str:
        loc = f"{lat:.4f}_{lng:.4f}" if lat is not None and lng is not None else "noloc"
        return f"{name}|{loc}"

    def _get_cached(self, name: str, lat: float | None, lng: float | None) -> list[str] | None:
        if not self.cache_path.exists():
            return None
        try:
            payload: dict = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        entry = payload.get(self._cache_key(name, lat, lng))
        if not entry:
            return None
        if int(time.time()) - int(entry.get("cached_at", 0)) > self.cache_ttl_seconds:
            return None
        return entry.get("data", [])

    def _put_cached(self, name: str, lat: float | None, lng: float | None, posts: list[str]) -> None:
        payload: dict = {}
        if self.cache_path.exists():
            try:
                payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        payload[self._cache_key(name, lat, lng)] = {
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
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_hashtag(name: str) -> str:
        """Strip whitespace and non-word characters, preserving CJK."""
        return re.sub(r"\W", "", name, flags=re.UNICODE)

    @classmethod
    def from_env(
        cls,
        *,
        session_path: str = DEFAULT_SESSION_PATH,
        cache_path: str = DEFAULT_IG_CACHE_PATH,
        usage_path: str = DEFAULT_IG_USAGE_PATH,
        cache_ttl_seconds: int = 3600,
        daily_limit: int = 100,
    ) -> "InstagramFetcher | None":
        """Return an InstagramFetcher from env vars, or None if no credentials found.

        Priority: INSTAGRAM_SESSIONID > INSTAGRAM_USERNAME + INSTAGRAM_PASSWORD
        """
        if os.environ.get("INSTAGRAM_ENABLED", "").lower() != "true":
            return None
        username = os.environ.get("INSTAGRAM_USERNAME", "")
        password = os.environ.get("INSTAGRAM_PASSWORD", "")
        if not (username and password):
            return None
        return cls(
            username=username,
            password=password,
            session_path=session_path,
            cache_path=cache_path,
            usage_path=usage_path,
            cache_ttl_seconds=cache_ttl_seconds,
            daily_limit=daily_limit,
        )
