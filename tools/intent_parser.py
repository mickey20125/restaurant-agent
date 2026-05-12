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

# Ordered longest-first so "南勢角站" matches before "南勢角"
KNOWN_LOCATIONS: tuple[tuple[str, str, float, float], ...] = (
    # (surface, canonical, lat, lng)
    # 捷運站
    ("頂溪站",       "頂溪",   25.0104, 121.5186),
    ("南勢角站",     "南勢角", 24.9935, 121.5145),
    ("景安站",       "景安",   25.0016, 121.5138),
    ("永安市場站",   "永安市場", 25.0062, 121.5145),
    ("中和站",       "中和",   25.0003, 121.5004),
    ("板橋站",       "板橋",   25.0143, 121.4627),
    ("新埔站",       "新埔",   25.0149, 121.4706),
    ("江子翠站",     "江子翠", 25.0209, 121.4745),
    ("新店站",       "新店",   24.9696, 121.5377),
    ("公館站",       "公館",   25.0176, 121.5340),
    ("古亭站",       "古亭",   25.0206, 121.5296),
    ("東門站",       "東門",   25.0329, 121.5300),
    ("西門站",       "西門",   25.0420, 121.5079),
    ("龍山寺站",     "龍山寺", 25.0375, 121.4998),
    ("師大路",       "師大",   25.0224, 121.5279),
    # 行政區
    ("永和區",       "永和",   25.0095, 121.5181),
    ("中和區",       "中和",   24.9994, 121.5131),
    ("板橋區",       "板橋",   25.0143, 121.4627),
    ("新店區",       "新店",   24.9696, 121.5377),
    ("新莊區",       "新莊",   25.0302, 121.4417),
    ("三重區",       "三重",   25.0619, 121.4885),
    ("蘆洲區",       "蘆洲",   25.0853, 121.4741),
    ("土城區",       "土城",   24.9744, 121.4461),
    ("汐止區",       "汐止",   25.0673, 121.6612),
    ("淡水區",       "淡水",   25.1693, 121.4418),
    ("信義區",       "信義區", 25.0340, 121.5646),
    ("大安區",       "大安區", 25.0270, 121.5436),
    ("中正區",       "中正區", 25.0427, 121.5099),
    ("松山區",       "松山區", 25.0500, 121.5779),
    ("內湖區",       "內湖區", 25.0832, 121.5861),
    ("士林區",       "士林區", 25.0931, 121.5239),
    ("北投區",       "北投區", 25.1319, 121.4985),
    ("南港區",       "南港區", 25.0547, 121.6078),
    ("萬華區",       "萬華區", 25.0372, 121.4996),
    ("文山區",       "文山區", 24.9993, 121.5716),
    ("中山區",       "中山區", 25.0637, 121.5293),
    ("大同區",       "大同區", 25.0630, 121.5131),
    # 無 "區"/"站" 後綴的常見地名
    ("永和",         "永和",   25.0095, 121.5181),
    ("中和",         "中和",   24.9994, 121.5131),
    ("板橋",         "板橋",   25.0143, 121.4627),
    ("新店",         "新店",   24.9696, 121.5377),
    ("新莊",         "新莊",   25.0302, 121.4417),
    ("三重",         "三重",   25.0619, 121.4885),
    ("蘆洲",         "蘆洲",   25.0853, 121.4741),
    ("土城",         "土城",   24.9744, 121.4461),
    ("汐止",         "汐止",   25.0673, 121.6612),
    ("淡水",         "淡水",   25.1693, 121.4418),
    ("頂溪",         "頂溪",   25.0104, 121.5186),
    ("公館",         "公館",   25.0176, 121.5340),
    ("古亭",         "古亭",   25.0206, 121.5296),
    ("師大",         "師大",   25.0224, 121.5279),
    ("西門",         "西門",   25.0420, 121.5079),
    ("信義",         "信義",   25.0340, 121.5646),
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
        location = self._extract_location(query)
        return AgentIntent(
            raw_query=query,
            cuisine=cuisine,
            must_have=must_have,
            max_walk_minutes=max_walk_minutes,
            min_rating=min_rating,
            needs_high_rating=needs_high_rating,
            non_engineer_logic=non_engineer_logic.strip(),
            location=location,
        )

    @staticmethod
    def _extract_location(query: str) -> str | None:
        for surface, canonical, _lat, _lng in KNOWN_LOCATIONS:
            if surface in query:
                return canonical
        return None

    @staticmethod
    def get_location_coords(location: str) -> tuple[float, float] | None:
        for _surface, canonical, lat, lng in KNOWN_LOCATIONS:
            if canonical == location:
                return lat, lng
        return None

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
