from __future__ import annotations

import math

from restaurant_agent.skills.types import AgentIntent, Candidate


class HardConstraintFilterSkill:
    def __init__(self, walking_speed_kmh: float = 4.5) -> None:
        self.walking_speed_kmh = walking_speed_kmh

    def run(
        self,
        *,
        candidates: list[Candidate],
        intent: AgentIntent,
        user_lat: float | None,
        user_lng: float | None,
    ) -> tuple[list[Candidate], dict]:
        kept: list[Candidate] = []
        dropped = 0
        for candidate in candidates:
            walk_minutes = self._estimate_walk_minutes(
                user_lat=user_lat,
                user_lng=user_lng,
                lat=candidate.lat,
                lng=candidate.lng,
            )
            candidate.walk_minutes = walk_minutes

            if intent.must_have:
                candidate.must_have_match = intent.must_have in candidate.name
                if not candidate.must_have_match:
                    dropped += 1
                    continue

            if intent.max_walk_minutes > 0 and walk_minutes is not None and walk_minutes > intent.max_walk_minutes:
                dropped += 1
                continue

            if walk_minutes is None and intent.max_walk_minutes > 0:
                candidate.risks.append("無法估算步行距離，可能超出限制")
            kept.append(candidate)

        return kept, {"input": len(candidates), "kept": len(kept), "dropped": dropped}

    def _estimate_walk_minutes(
        self,
        *,
        user_lat: float | None,
        user_lng: float | None,
        lat: float | None,
        lng: float | None,
    ) -> float | None:
        if None in (user_lat, user_lng, lat, lng):
            return None
        distance_km = self._haversine_km(user_lat, user_lng, lat, lng)
        return (distance_km / self.walking_speed_kmh) * 60

    @staticmethod
    def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        r = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lng = math.radians(lng2 - lng1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return r * c

