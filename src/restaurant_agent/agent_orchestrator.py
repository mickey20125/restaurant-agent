from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

from restaurant_agent.google_maps_parser import GoogleMapsParser
from restaurant_agent.skills.candidate_search import CandidateSearchSkill
from restaurant_agent.skills.cost_guard import CostGuardSkill
from restaurant_agent.skills.hard_constraint_filter import HardConstraintFilterSkill
from restaurant_agent.skills.intent_parser import IntentParserSkill
from restaurant_agent.skills.ranker import RankerSkill
from restaurant_agent.skills.reason_composer import ReasonComposerSkill
from restaurant_agent.skills.review_fetcher import ReviewFetcherSkill
from restaurant_agent.skills.social_text_adapter import SocialTextAdapterSkill
from restaurant_agent.skills.types import AgentIntent, Candidate
from restaurant_agent.skills.vibe_skill import VibeSummarizerSkill


class FoodieAgentOrchestrator:
    """Run a skill-based foodie recommendation pipeline."""

    def __init__(self, maps_parser: GoogleMapsParser | None = None) -> None:
        self.maps_parser = maps_parser or GoogleMapsParser()

    def run(
        self,
        *,
        query: str,
        non_engineer_logic: str = "",
        user_lat: float | None = None,
        user_lng: float | None = None,
        region_code: str = "TW",
        language_code: str = "zh-TW",
        safe_mode: bool = True,
        candidate_limit: int = 8,
        top_k: int = 3,
        max_reviews_per_place: int = 3,
        social_file: str | None = None,
        inline_social_posts: list[str] | None = None,
        daily_limit: int | None = None,
        usage_path: str | None = None,
        cache_path: str | None = None,
    ) -> dict[str, Any]:
        usage_limit = daily_limit or int(os.environ.get("MAPS_DAILY_CALL_LIMIT", "100"))
        effective_usage_path = usage_path or os.environ.get("AGENT_DAILY_USAGE_PATH", ".cache/agent_daily_usage.json")
        effective_cache_path = cache_path or os.environ.get("AGENT_SKILL_CACHE_PATH", ".cache/agent_skill_cache.json")
        cost_guard = CostGuardSkill(
            daily_limit=usage_limit,
            usage_path=effective_usage_path,
            cache_path=effective_cache_path,
        )

        intent_skill = IntentParserSkill()
        candidate_skill = CandidateSearchSkill(self.maps_parser, cost_guard)
        filter_skill = HardConstraintFilterSkill()
        review_skill = ReviewFetcherSkill(self.maps_parser, cost_guard)
        social_skill = SocialTextAdapterSkill()
        vibe_skill = VibeSummarizerSkill()
        ranker_skill = RankerSkill()
        reason_skill = ReasonComposerSkill()

        debug_steps: dict[str, Any] = {}
        intent = intent_skill.run(query=query, non_engineer_logic=non_engineer_logic)
        debug_steps["intent"] = asdict(intent)

        candidates, search_meta = candidate_skill.run(
            intent=intent,
            region_code=region_code,
            language_code=language_code,
            safe_mode=safe_mode,
            candidate_limit=candidate_limit,
        )
        debug_steps["candidate_search"] = search_meta

        filtered_candidates, filter_meta = filter_skill.run(
            candidates=candidates,
            intent=intent,
            user_lat=user_lat,
            user_lng=user_lng,
        )
        debug_steps["hard_filter"] = filter_meta

        reviewed_candidates, review_meta = review_skill.run(
            candidates=filtered_candidates,
            language_code=language_code,
            max_reviews_per_place=max_reviews_per_place,
        )
        debug_steps["review_fetcher"] = review_meta

        socialized_candidates, social_meta = social_skill.run(
            candidates=reviewed_candidates,
            social_file=social_file,
            inline_posts=inline_social_posts,
        )
        debug_steps["social_adapter"] = social_meta

        vibed_candidates, vibe_meta = vibe_skill.run(candidates=socialized_candidates, top_k=3)
        debug_steps["vibe_summarizer"] = vibe_meta

        ranked_candidates = ranker_skill.run(candidates=vibed_candidates, intent=intent)
        recommendations = reason_skill.run(ranked_candidates=ranked_candidates, intent=intent, top_k=top_k)

        return {
            "intent": asdict(intent),
            "recommendations": [item.to_dict() for item in recommendations],
            "debug": {
                **debug_steps,
                "ranked_preview": [self._candidate_preview(item) for item in ranked_candidates[: min(5, len(ranked_candidates))]],
            },
        }

    @staticmethod
    def _candidate_preview(candidate: Candidate) -> dict[str, Any]:
        return {
            "place_id": candidate.place_id,
            "name": candidate.name,
            "score": candidate.score,
            "rating": candidate.rating,
            "walk_minutes": candidate.walk_minutes,
            "vibe_tags": candidate.vibe_tags,
            "must_have_match": candidate.must_have_match,
        }

    @staticmethod
    def empty_result(query: str) -> dict[str, Any]:
        default_intent = AgentIntent(
            raw_query=query,
            cuisine=None,
            must_have=None,
            max_walk_minutes=20,
            min_rating=None,
            needs_high_rating=False,
            non_engineer_logic="",
        )
        return {"intent": asdict(default_intent), "recommendations": [], "debug": {}}
