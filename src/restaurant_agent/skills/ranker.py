from __future__ import annotations

from restaurant_agent.skills.types import AgentIntent, Candidate


class RankerSkill:
    def run(self, *, candidates: list[Candidate], intent: AgentIntent) -> list[Candidate]:
        for candidate in candidates:
            text_blob = " ".join([candidate.name] + candidate.reviews + candidate.social_posts).lower()
            if intent.must_have:
                candidate.must_have_match = intent.must_have.lower() in text_blob

            rating = candidate.rating if candidate.rating is not None else 3.8
            rating_score = max(0.0, min(1.0, rating / 5.0))
            popularity_score = max(0.0, min(1.0, (candidate.user_rating_count or 0) / 1500.0))
            distance_score = self._distance_score(candidate.walk_minutes, intent.max_walk_minutes)
            must_have_score = self._must_have_score(intent, candidate.must_have_match)
            vibe_score = 0.1 if candidate.vibe_tags and candidate.vibe_tags[0] != "#資訊不足" else 0.0

            total = (
                rating_score * 0.5
                + popularity_score * 0.15
                + distance_score * 0.15
                + must_have_score
                + vibe_score
            )
            if intent.min_rating is not None and candidate.rating is not None and candidate.rating < intent.min_rating:
                total -= 0.25
                candidate.risks.append(f"評分低於偏好門檻（{intent.min_rating}）")
            candidate.score = round(total, 4)

        return sorted(candidates, key=lambda item: item.score, reverse=True)

    @staticmethod
    def _distance_score(walk_minutes: float | None, max_walk_minutes: int) -> float:
        if max_walk_minutes <= 0:
            return 0.5
        if walk_minutes is None:
            return 0.35
        return max(0.0, min(1.0, 1.0 - (walk_minutes / max_walk_minutes)))

    @staticmethod
    def _must_have_score(intent: AgentIntent, matched: bool) -> float:
        if not intent.must_have:
            return 0.0
        if matched:
            return 0.2
        return -0.3

