from __future__ import annotations

import re

from tools.types import AgentIntent

KNOWN_CUISINES = (
    "韓式",
    "日式",
    "台式",
    "美式",
    "義式",
    "泰式",
    "越式",
    "火鍋",
    "拉麵",
)


class IntentParserSkill:
    def run(self, *, query: str, non_engineer_logic: str = "") -> AgentIntent:
        max_walk_minutes = self._extract_walk_minutes(query) or 20
        min_rating = self._extract_min_rating(query)
        needs_high_rating = "評價高" in query or "高評價" in query
        if needs_high_rating and (min_rating is None or min_rating < 4.2):
            min_rating = 4.2

        must_have = self._extract_must_have(query)
        cuisine = self._extract_cuisine(query)
        return AgentIntent(
            raw_query=query,
            cuisine=cuisine,
            must_have=must_have,
            max_walk_minutes=max_walk_minutes,
            min_rating=min_rating,
            needs_high_rating=needs_high_rating,
            non_engineer_logic=non_engineer_logic.strip(),
        )

    @staticmethod
    def _extract_walk_minutes(query: str) -> int | None:
        match = re.search(r"(\d+)\s*分(?:鐘)?", query)
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _extract_min_rating(query: str) -> float | None:
        match = re.search(r"(?<!\d)([0-5](?:\.\d)?)\s*分(?:以上|up|UP)?", query)
        if not match:
            return None
        return float(match.group(1))

    @staticmethod
    def _extract_must_have(query: str) -> str | None:
        match = re.search(r"(?:有|要有|一定要有)\s*([^，,。.；;]+)", query)
        if match:
            return match.group(1).strip()

        for keyword in ("豆腐鍋", "海鮮煎餅", "韓式炸雞", "拉麵", "火鍋"):
            if keyword in query:
                return keyword
        return None

    @staticmethod
    def _extract_cuisine(query: str) -> str | None:
        for cuisine in KNOWN_CUISINES:
            if cuisine in query:
                return cuisine
        return None
