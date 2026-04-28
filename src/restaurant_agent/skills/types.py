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
    vibe_tags: list[str] = field(default_factory=list)
    score: float = 0.0
    must_have_match: bool = False
    risks: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

