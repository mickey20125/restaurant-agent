from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TagRule:
    tag: str
    keywords: tuple[str, ...]


DEFAULT_TAG_RULES: tuple[TagRule, ...] = (
    TagRule("#出片", ("好拍", "拍照", "打卡", "網美", "景觀", "裝潢", "氛圍", "文青", "復古", "美照")),
    TagRule("#排隊", ("排隊", "候位", "等位", "客滿", "熱門", "爆滿", "預約", "人超多")),
    TagRule("#老字號", ("老字號", "古早味", "在地", "傳統", "開了", "祖傳", "多年")),
    TagRule("#CP值", ("平價", "便宜", "划算", "cp值", "大份", "高cp")),
    TagRule("#辣感", ("辣", "重口味", "麻辣")),
    TagRule("#豆腐鍋專門", ("豆腐鍋", "嫩豆腐", "順豆腐", "순두부", "soondubu")),
)


def summarize_vibes(posts: list[str], top_k: int = 3) -> list[str]:
    """Convert social text snippets into top-k vibe tags."""
    normalized = " ".join(posts).lower()
    scores: list[tuple[str, int]] = []
    for rule in DEFAULT_TAG_RULES:
        count = 0
        for keyword in rule.keywords:
            count += normalized.count(keyword.lower())
        scores.append((rule.tag, count))

    ranked = sorted(scores, key=lambda item: item[1], reverse=True)
    selected = [tag for tag, score in ranked if score > 0][:top_k]
    if selected:
        return selected
    return ["#資訊不足", "#待補社群資料", "#先看地圖評價"]
