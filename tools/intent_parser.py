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

    _KNOWN_DISHES: tuple[str, ...] = ("豆腐鍋", "海鮮煎餅", "韓式炸雞", "拉麵", "火鍋")

    # Person/quantity/adverb words that indicate the regex captured a constraint phrase,
    # not a dish name — used to reject false-positive must_have matches.
    _MUST_HAVE_REJECT: re.Pattern = re.compile(
        r"^(?:人|大家|我們|朋友|同事|長輩|只吃|不吃|不要|太|很|也|都|一定|可以|需要)"
    )

    @staticmethod
    def _extract_must_have(query: str) -> str | None:
        # Check known dishes first (highest precision)
        for keyword in IntentParserSkill._KNOWN_DISHES:
            if keyword in query:
                return keyword

        # Regex: only accept short captured terms (≤5 chars) that don't start with
        # person/constraint words — avoids capturing "人只吃健康食物", "素食者" etc.
        match = re.search(r"(?:一定要有|要有)\s*([^，,。.；;\s]{2,5})", query)
        if match:
            term = match.group(1).strip()
            if not IntentParserSkill._MUST_HAVE_REJECT.search(term):
                return term

        return None

    @staticmethod
    def _extract_cuisine(query: str) -> str | None:
        for cuisine in KNOWN_CUISINES:
            if cuisine in query:
                return cuisine
        return None
