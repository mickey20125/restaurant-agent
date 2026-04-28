from __future__ import annotations

from dataclasses import asdict, is_dataclass

from restaurant_agent.google_maps_parser import GoogleMapsParser
from restaurant_agent.skills.cost_guard import CostGuardSkill
from restaurant_agent.skills.types import Candidate


class ReviewFetcherSkill:
    def __init__(self, maps_parser: GoogleMapsParser, cost_guard: CostGuardSkill) -> None:
        self.maps_parser = maps_parser
        self.cost_guard = cost_guard

    def run(
        self,
        *,
        candidates: list[Candidate],
        language_code: str,
        max_reviews_per_place: int,
        cache_ttl_seconds: int = 7200,
    ) -> tuple[list[Candidate], dict]:
        live_calls = 0
        cache_hits = 0
        blocked = 0
        for candidate in candidates:
            cache_key = f"{candidate.place_id}|{language_code}|{max_reviews_per_place}"
            cached = self.cost_guard.get_cached(
                namespace="reviews",
                key=cache_key,
                ttl_seconds=cache_ttl_seconds,
            )
            if cached:
                cache_hits += 1
                self._hydrate_candidate(candidate, cached)
                continue

            allowed, usage_meta = self.cost_guard.allow_api_calls(units=1)
            if not allowed:
                blocked += 1
                candidate.risks.append(
                    f"已達每日 API 上限（{usage_meta['daily_count']}/{usage_meta['daily_limit']}），評論資料可能不足"
                )
                continue

            place, review_records = self.maps_parser.get_place_details_with_reviews(
                candidate.place_id,
                language_code=language_code,
                max_reviews=max_reviews_per_place,
            )
            candidate.rating = place.rating if place.rating is not None else candidate.rating
            candidate.address = place.address or candidate.address
            candidate.lat = place.lat if place.lat is not None else candidate.lat
            candidate.lng = place.lng if place.lng is not None else candidate.lng
            candidate.user_rating_count = (
                place.user_rating_count if place.user_rating_count is not None else candidate.user_rating_count
            )
            candidate.review_records = self._to_review_records(review_records)
            candidate.reviews = [item.text for item in review_records if item.text]
            self.cost_guard.put_cached(
                namespace="reviews",
                key=cache_key,
                data={
                    "rating": candidate.rating,
                    "address": candidate.address,
                    "lat": candidate.lat,
                    "lng": candidate.lng,
                    "user_rating_count": candidate.user_rating_count,
                    "review_records": candidate.review_records,
                    "reviews": candidate.reviews,
                },
            )
            live_calls += 1

        return candidates, {"live_calls": live_calls, "cache_hits": cache_hits, "blocked": blocked}

    @staticmethod
    def _hydrate_candidate(candidate: Candidate, payload: dict) -> None:
        candidate.rating = payload.get("rating")
        candidate.address = payload.get("address")
        candidate.lat = payload.get("lat")
        candidate.lng = payload.get("lng")
        candidate.user_rating_count = payload.get("user_rating_count")
        candidate.review_records = payload.get("review_records", [])
        candidate.reviews = payload.get("reviews", [])

    @staticmethod
    def _to_review_records(review_records: list) -> list[dict]:
        normalized: list[dict] = []
        for item in review_records:
            if isinstance(item, dict):
                normalized.append(item)
                continue
            if is_dataclass(item):
                normalized.append(asdict(item))
                continue
            normalized.append({"text": str(item)})
        return normalized
