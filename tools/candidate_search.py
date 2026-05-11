from __future__ import annotations

from tools.google_maps_parser import GoogleMapsParser
from tools.cost_guard import CostGuardSkill
from tools.types import AgentIntent, Candidate


class CandidateSearchSkill:
    def __init__(self, maps_parser: GoogleMapsParser, cost_guard: CostGuardSkill) -> None:
        self.maps_parser = maps_parser
        self.cost_guard = cost_guard

    def run(
        self,
        *,
        intent: AgentIntent,
        region_code: str,
        language_code: str,
        safe_mode: bool,
        candidate_limit: int,
        cache_ttl_seconds: int = 3600,
    ) -> tuple[list[Candidate], dict]:
        query = self._build_query(intent)
        cache_key = f"{query}|{region_code}|{language_code}|safe={int(safe_mode)}|limit={candidate_limit}"
        cached = self.cost_guard.get_cached(
            namespace="candidate_search",
            key=cache_key,
            ttl_seconds=cache_ttl_seconds,
        )
        if cached:
            return (
                [Candidate(**item) for item in cached.get("candidates", [])],
                {"source": "cache", "query": query},
            )

        allowed, usage_meta = self.cost_guard.allow_api_calls(units=1)
        if not allowed:
            return [], {"source": "budget_blocked", "query": query, **usage_meta}

        records = self.maps_parser.search_places(
            query,
            region_code=region_code,
            language_code=language_code,
            safe_mode=safe_mode,
            max_results=candidate_limit,
        )
        candidates = [
            Candidate(
                place_id=item.place_id,
                name=item.name,
                rating=item.rating,
                address=item.address,
                lat=item.lat,
                lng=item.lng,
                user_rating_count=item.user_rating_count,
            )
            for item in records
        ]
        self.cost_guard.put_cached(
            namespace="candidate_search",
            key=cache_key,
            data={"candidates": [item.to_dict() for item in candidates]},
        )
        return candidates, {"source": "live_api", "query": query, **usage_meta}

    # Maps surface-form keywords (found in raw_query / logic) to canonical
    # Google Maps search terms.  Longer strings must come first so that
    # "台灣料理" is matched before the substring "料理".
    _VENUE_KEYWORD_MAP: tuple[tuple[str, str], ...] = (
        ("餐酒館", "餐酒館"),
        ("小酒館", "餐酒館"),
        ("居酒屋", "居酒屋"),
        ("熱炒",   "熱炒"),
        ("快炒",   "熱炒"),
        ("台灣料理", "台菜"),
        ("台式料理", "台菜"),
        ("台灣味",  "台菜"),
        ("台味",   "台菜"),
        ("台菜",   "台菜"),
        ("燒肉",   "燒肉"),
        ("燒烤",   "燒烤"),
        ("烤肉",   "燒烤"),
        ("丼飯",   "丼飯"),
        ("咖哩",   "咖哩"),
        ("壽司",   "壽司"),
        ("和食",   "和食"),
        ("懷石",   "和食"),
    )

    @staticmethod
    def _build_query(intent: AgentIntent) -> str:
        parts: list[str] = []
        if intent.cuisine:
            parts.append(intent.cuisine)
        if intent.must_have:
            parts.append(intent.must_have)

        # When no structured cuisine, scan raw_query + logic for venue/food keywords
        if not intent.cuisine:
            text = f"{intent.raw_query} {intent.non_engineer_logic}"
            for surface, canonical in CandidateSearchSkill._VENUE_KEYWORD_MAP:
                if surface in text:
                    parts.append(canonical)
                    break

        parts.append("餐廳")
        # deduplicate while preserving order (e.g. cuisine == canonical)
        seen: set[str] = set()
        deduped = [p for p in parts if not (p in seen or seen.add(p))]  # type: ignore[func-returns-value]
        return " ".join(deduped)
