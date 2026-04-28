---
name: Review Fetcher
description: 批量抓取各候選店家的 Google Maps 評論詳情，並更新評分、地址等欄位。內建 cache 與每日用量保護。
input:
  candidates: list[Candidate]   # 來自 hard-constraint-filter 的清單
  language_code: string         # 評論語言，預設 "zh-TW"
  max_reviews_per_place: int    # 每家最多抓幾則，預設 3
output:
  candidates: list[Candidate]   # 同清單，reviews / review_records 已填入
  meta: dict                    # live_calls、cache_hits、blocked 數量
tool: tools/review_fetcher.py — ReviewFetcherSkill.run()
---

## 說明

每間店呼叫 `GoogleMapsParser.get_place_details_with_reviews(place_id)`，會同時更新：
- `rating`、`address`、`lat`、`lng`、`user_rating_count`（以最新值覆蓋）
- `reviews`（純文字清單）
- `review_records`（完整 dict，含作者、時間、評分）

**成本控制**：
- 每間店先查 cache（TTL 7200 秒）
- 每次 live 呼叫消耗 1 單位每日配額
- 配額耗盡時跳過該店，加入 risk 警示

## 調用方式

```python
from tools.review_fetcher import ReviewFetcherSkill

candidates, meta = ReviewFetcherSkill(maps_parser, cost_guard).run(
    candidates=filtered_candidates,
    language_code="zh-TW",
    max_reviews_per_place=3,
)
```
