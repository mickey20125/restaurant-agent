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

    @staticmethod
    def _build_query(intent: AgentIntent) -> str:
        parts = [intent.cuisine or "", intent.must_have or "", "餐廳"]
        return " ".join([part for part in parts if part]).strip() or intent.raw_query
