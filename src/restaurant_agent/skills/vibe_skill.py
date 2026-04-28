from __future__ import annotations

from restaurant_agent.skills.types import Candidate
from restaurant_agent.vibe_summarizer import summarize_vibes


class VibeSummarizerSkill:
    def run(self, *, candidates: list[Candidate], top_k: int = 3) -> tuple[list[Candidate], dict]:
        for candidate in candidates:
            corpus = candidate.social_posts + candidate.reviews
            candidate.vibe_tags = summarize_vibes(corpus, top_k=top_k)
        return candidates, {"processed": len(candidates), "top_k": top_k}

