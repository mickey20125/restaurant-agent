from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AgentIntent:
    raw_query: str
    cuisine: str | None
    must_have: str | None
    max_walk_minutes: int
    min_rating: float | None
    needs_high_rating: bool
    non_engineer_logic: str
    location: str | None = None


@dataclass
class Candidate:
    place_id: str
    name: str
    rating: float | None
    address: str | None
    lat: float | None
    lng: float | None
    user_rating_count: int | None
    walk_minutes: float | None = None
    reviews: list[str] = field(default_factory=list)
    review_records: list[dict[str, Any]] = field(default_factory=list)
    social_posts: list[str] = field(default_factory=list)
    social_highlights: list[str] = field(default_factory=list)
    vibe_tags: list[str] = field(default_factory=list)
    score: float = 0.0
    must_have_match: bool = False
    risks: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    phone: str | None = None
    website: str | None = None
    reservation_url: str | None = None
    reservable: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Recommendation:
    place_id: str
    name: str
    address: str | None
    score: float
    reason: str
    vibe_tags: list[str]
    risks: list[str]
    evidence: list[str]
    metrics: dict[str, Any]
    phone: str | None = None
    reservation_url: str | None = None
    social_highlights: list[str] = field(default_factory=list)
    review_records: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        walk = self.metrics.get("walk_minutes")
        walk_str = f"{walk:.0f} 分鐘" if walk is not None else "未知"
        rating = self.metrics.get("rating")
        count = self.metrics.get("user_rating_count")
        rating_str = f"{rating:.1f}（{count} 則評價）" if rating else "未知"

        lines: list[str] = [
            f"### {self.name}",
            f"**地址：** {self.address or '未知'}",
            f"**步行：** 約 {walk_str}",
            f"**Google 評分：** {rating_str}",
            "",
            "**推薦理由**",
            self.reason,
            "",
            "**風格標籤**",
            " ".join(self.vibe_tags) if self.vibe_tags else "（暫無）",
            "",
            "**預約資訊**",
        ]
        if self.reservation_url:
            lines.append(f"線上訂位：{self.reservation_url}")
        elif self.phone:
            lines.append(f"電話預約：{self.phone}")
        else:
            lines.append("需現場或致電詢問，建議提前確認")

        lines += ["", "**Google Maps 評論**"]
        if self.review_records:
            lines.append("| 作者 | 星數 | 時間 | 內容摘要 |")
            lines.append("|------|------|------|----------|")
            for r in self.review_records:
                author = (r.get("author_name") or "匿名")[:12]
                stars = "⭐" * int(r.get("rating") or 0)
                time_str = (r.get("relative_publish_time") or "")[:10]
                text = (r.get("text") or "")[:60].replace("\n", " ").replace("|", "｜")
                lines.append(f"| {author} | {stars} | {time_str} | {text} |")
        else:
            lines.append("暫無評論資料")

        lines += ["", "**Threads 金句**"]
        if self.social_highlights:
            for quote in self.social_highlights[:2]:
                lines.append(f"「{quote[:80]}」")
        else:
            lines.append("暫無 Threads 社群貼文資料")

        lines += ["", "**風險提醒**"]
        if self.risks:
            lines.extend(f"- {r}" for r in self.risks)
        else:
            lines.append("無特別風險提醒")

        lines += ["", "**可驗證證據**"]
        if self.evidence:
            lines.extend(f"- {e}" for e in self.evidence)
        else:
            lines.append("（暫無）")

        return "\n".join(lines)
