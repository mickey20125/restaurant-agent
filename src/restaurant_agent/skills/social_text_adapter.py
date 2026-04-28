from __future__ import annotations

import json
from pathlib import Path

from restaurant_agent.skills.types import Candidate


class SocialTextAdapterSkill:
    """Attach social text snippets to candidates.

    Supported local file formats:
    1) JSON object: {"店名": ["貼文1", "貼文2"]}
    2) Text lines: "店名|貼文內容"
    3) Text lines without "|": treated as global snippets for all candidates
    """

    def run(
        self,
        *,
        candidates: list[Candidate],
        social_file: str | None,
        inline_posts: list[str] | None = None,
    ) -> tuple[list[Candidate], dict]:
        by_store, global_posts = self._load_social_posts(social_file)
        if inline_posts:
            global_posts.extend([item for item in inline_posts if item.strip()])

        attached = 0
        for candidate in candidates:
            matched = list(global_posts)
            for store_name, posts in by_store.items():
                if store_name and (store_name in candidate.name or candidate.name in store_name):
                    matched.extend(posts)
            candidate.social_posts = matched
            if matched:
                attached += 1
        return candidates, {"stores_with_social_posts": attached, "global_posts": len(global_posts)}

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

        by_store: dict[str, list[str]] = {}
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

