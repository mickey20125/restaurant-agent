from __future__ import annotations

import json
from pathlib import Path

from tools.types import Candidate

# InstagramFetcher is optional — imported lazily to avoid hard dependency at import time
_InstagramFetcherType = None


def _ig_fetcher_type() -> type | None:
    global _InstagramFetcherType
    if _InstagramFetcherType is None:
        try:
            from tools.instagram_fetcher import InstagramFetcher
            _InstagramFetcherType = InstagramFetcher
        except ImportError:
            pass
    return _InstagramFetcherType


class SocialTextAdapterSkill:
    """Attach social text snippets to candidates.

    Data sources (all optional, combined and deduplicated):
    1. Local file  — social_file path (JSON or pipe-delimited text)
    2. Inline text — inline_posts list passed directly
    3. Instagram   — ig_fetcher fetches via hashtag + location per candidate
    """

    def run(
        self,
        *,
        candidates: list[Candidate],
        social_file: str | None,
        inline_posts: list[str] | None = None,
        ig_fetcher: object | None = None,
        ig_max_posts: int = 10,
        threads_scraper: object | None = None,
        threads_max_posts: int = 10,
    ) -> tuple[list[Candidate], dict]:
        by_store, global_posts = self._load_social_posts(social_file)
        if inline_posts:
            global_posts.extend([item for item in inline_posts if item.strip()])

        ig_fetched = 0
        threads_fetched = 0
        attached = 0

        for candidate in candidates:
            matched: list[str] = list(global_posts)

            for store_name, posts in by_store.items():
                if store_name and (store_name in candidate.name or candidate.name in store_name):
                    matched.extend(posts)

            if ig_fetcher is not None:
                ig_posts, ig_errors = ig_fetcher.fetch_for_candidate(
                    name=candidate.name,
                    lat=candidate.lat,
                    lng=candidate.lng,
                    max_posts=ig_max_posts,
                )
                if ig_errors:
                    candidate.risks.extend(
                        [f"IG({k}): {v}" for k, v in ig_errors.items()]
                    )
                if ig_posts:
                    matched.extend(ig_posts)
                    ig_fetched += 1

            th_posts_with_meta: list[dict] = []
            if threads_scraper is not None:
                th_posts_with_meta, th_errors = threads_scraper.fetch_posts_with_engagement(
                    name=candidate.name,
                    max_posts=threads_max_posts,
                )
                if th_errors:
                    candidate.risks.extend(
                        [f"Threads({k}): {v}" for k, v in th_errors.items()]
                    )
                if th_posts_with_meta:
                    matched.extend([p["text"] for p in th_posts_with_meta])
                    threads_fetched += 1

            candidate.social_posts = matched
            candidate.social_highlights = self._pick_highlights(th_posts_with_meta)
            if matched:
                attached += 1

        return candidates, {
            "stores_with_social_posts": attached,
            "global_posts": len(global_posts),
            "ig_fetched": ig_fetched,
            "threads_fetched": threads_fetched,
        }

    # Threads UI strings that should never appear as highlights
    _HIGHLIGHT_NOISE: frozenset[str] = frozenset([
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

    @staticmethod
    def _pick_highlights(posts: list[dict], n: int = 3) -> list[str]:
        """Pick top N highlight quotes from Threads posts.

        Primary sort: like_count descending.
        Within same like_count, prefer sentences 15-120 chars (avoids pure-hashtag noise).
        Filters out known Threads UI strings.
        """
        if not posts:
            return []

        def _score(post: dict) -> tuple:
            text = post.get("text", "")
            likes = post.get("like_count", 0) if isinstance(post.get("like_count"), int) else 0
            length_ok = 1 if 15 <= len(text) <= 120 else 0
            return (likes, length_ok)

        ranked = sorted(posts, key=_score, reverse=True)
        seen: set[str] = set()
        highlights: list[str] = []
        for post in ranked:
            text = post.get("text", "")
            if (
                text
                and text not in seen
                and text not in SocialTextAdapterSkill._HIGHLIGHT_NOISE
                and len(text) >= 15
            ):
                seen.add(text)
                highlights.append(text)
            if len(highlights) >= n:
                break
        return highlights

    def _load_social_posts(self, social_file: str | None) -> tuple[dict[str, list[str]], list[str]]:
        if not social_file:
            return {}, []

        path = Path(social_file)
        if not path.exists():
            return {}, []
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}, []

        try:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                by_store: dict[str, list[str]] = {}
                for key, value in payload.items():
                    if isinstance(value, list):
                        by_store[str(key)] = [str(item) for item in value]
                return by_store, []
        except json.JSONDecodeError:
            pass

        by_store = {}
        global_posts: list[str] = []
        for line in raw.splitlines():
            item = line.strip()
            if not item:
                continue
            if "|" not in item:
                global_posts.append(item)
                continue
            store, text = item.split("|", 1)
            store = store.strip()
            text = text.strip()
            if not store or not text:
                continue
            by_store.setdefault(store, []).append(text)
        return by_store, global_posts
