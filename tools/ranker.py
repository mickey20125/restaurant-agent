from __future__ import annotations

import re

from tools.types import AgentIntent, Candidate

_LOGIC_STOP: frozenset[str] = frozenset([
    "的", "了", "也", "都", "有", "是", "不", "要", "但",
    "和", "或", "與", "我", "你", "他", "我們", "一定",
    "可以", "需要", "不要", "這個", "那個", "一些", "比較",
    "不會", "不太", "不是", "不用",
])


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
            logic_score = self._logic_score(intent.non_engineer_logic, text_blob)

            total = (
                rating_score * 0.5
                + popularity_score * 0.15
                + distance_score * 0.15
                + must_have_score
                + vibe_score
                + logic_score
            )
            if intent.min_rating is not None and candidate.rating is not None and candidate.rating < intent.min_rating:
                total -= 0.25
                candidate.risks.append(f"評分低於偏好門檻（{intent.min_rating}）")
            candidate.score = round(max(0.0, min(1.0, total)), 4)

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

    @staticmethod
    def _logic_keywords(logic: str) -> list[str]:
        """Split logic string into short keyword phrases, filtering stop words.

        Two-pass split: first on punctuation delimiters, then on conjunctions
        within longer chunks so "有設計感但不是網美店" yields "有設計感".
        """
        chunks = re.split(r"[、，,。.；;\s]+", logic.strip())
        phrases: list[str] = []
        for chunk in chunks:
            if not chunk:
                continue
            # Secondary split on conjunctions for chunks that are too long
            if len(chunk) > 6:
                sub = re.split(r"[但也而或且]", chunk)
                phrases.extend(sub)
            else:
                phrases.append(chunk)

        return [
            p.strip() for p in phrases
            if 2 <= len(p.strip()) <= 8 and p.strip() not in _LOGIC_STOP
        ]

    @staticmethod
    def _logic_score(logic: str, text_blob: str, weight: float = 0.15) -> float:
        """Score 0–weight based on how many logic keywords appear in reviews/posts."""
        if not logic:
            return 0.0
        keywords = RankerSkill._logic_keywords(logic)
        if not keywords:
            return 0.0
        matched = sum(1 for kw in keywords if kw in text_blob)
        return round((matched / len(keywords)) * weight, 4)
