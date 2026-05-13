from __future__ import annotations

from tools.types import AgentIntent, Candidate, Recommendation


class ReasonComposerSkill:
    def run(self, *, ranked_candidates: list[Candidate], intent: AgentIntent, top_k: int = 3) -> list[Recommendation]:
        output: list[Recommendation] = []
        for candidate in ranked_candidates[:top_k]:
            reason_parts: list[str] = []
            if candidate.rating is not None:
                reason_parts.append(f"Google 評分 {candidate.rating:.1f}")
            if candidate.user_rating_count:
                reason_parts.append(f"{candidate.user_rating_count} 則地圖評價")
            if candidate.walk_minutes is not None:
                reason_parts.append(f"預估步行 {candidate.walk_minutes:.0f} 分鐘")
            if intent.must_have and candidate.must_have_match:
                reason_parts.append(f"內容訊號符合「{intent.must_have}」")
            if intent.non_engineer_logic:
                reason_parts.append(f"符合設定邏輯：{intent.non_engineer_logic}")
            if not reason_parts:
                reason_parts.append("符合基礎搜尋條件")

            evidence: list[str] = []
            if candidate.reviews:
                evidence.append(f"評論摘錄：{candidate.reviews[0][:80]}")
            if candidate.vibe_tags:
                evidence.append("風格標籤：" + " ".join(candidate.vibe_tags))
            if candidate.social_highlights:
                for quote in candidate.social_highlights[:2]:
                    evidence.append(f"Threads 金句：{quote[:80]}")

            risks = list(candidate.risks)
            if not candidate.reviews:
                risks.append("評論樣本不足")
            if candidate.walk_minutes is None and intent.max_walk_minutes > 0:
                risks.append("步行時間估算不完整")

            output.append(
                Recommendation(
                    place_id=candidate.place_id,
                    name=candidate.name,
                    address=candidate.address,
                    score=round(candidate.score, 4),
                    reason="；".join(reason_parts),
                    vibe_tags=candidate.vibe_tags,
                    risks=sorted(set(risks)),
                    evidence=evidence,
                    metrics={
                        "rating": candidate.rating,
                        "user_rating_count": candidate.user_rating_count,
                        "walk_minutes": candidate.walk_minutes,
                        "must_have_match": candidate.must_have_match,
                    },
                    phone=candidate.phone,
                    reservation_url=candidate.reservation_url,
                    social_highlights=candidate.social_highlights,
                    review_records=candidate.review_records,
                )
            )
        return output
