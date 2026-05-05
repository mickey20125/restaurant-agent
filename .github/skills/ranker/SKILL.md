---
name: ranker
description: 依多維度加權公式對候選店家打分並排序，分數高者優先推薦。
---

## 介面規格

**Input**
- `candidates: list[Candidate]` — 含 vibe_tags、reviews、walk_minutes 的清單
- `intent: AgentIntent` — 含 must_have、min_rating、max_walk_minutes

**Output**
- `candidates: list[Candidate]` — 同清單，score 已填入，按 score 降序排列

**Tool**: `tools/ranker.py — RankerSkill.run()`

---

## 評分公式

```
score = rating_score   × 0.50
      + popularity     × 0.15
      + distance_score × 0.15
      + must_have_score        (命中 +0.20，未命中 −0.30，無需求 0)
      + vibe_score             (有有效 tag +0.10)
```

**懲罰**：評分低於 `intent.min_rating` 時 `−0.25`，同時加入 risk。

**Normalization**：最終 `score` 會限制在 `0–1` 範圍（clamp）。

## 各維度說明

| 維度 | 計算方式 |
|------|---------|
| `rating_score` | `rating / 5.0`，範圍 0–1 |
| `popularity` | `user_rating_count / 1500`，上限 1 |
| `distance_score` | `1 - walk_minutes / max_walk_minutes`，無資料時 0.35 |
| `must_have_score` | 在 name + reviews + social_posts 中搜尋關鍵字 |
| `vibe_score` | 有非 fallback tag 時 +0.1 |

## 調用方式

```python
from tools.ranker import RankerSkill

ranked = RankerSkill().run(candidates=candidates, intent=intent)
```
