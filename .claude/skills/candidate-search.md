---
name: Candidate Search
description: 依 AgentIntent 組合搜尋字串，呼叫 Google Maps Places API，回傳候選店家清單。內建 cache 與每日用量保護。
input:
  intent: AgentIntent       # 來自 intent-parser 的結構化意圖
  region_code: string       # 地區碼，預設 "TW"
  language_code: string     # 語言碼，預設 "zh-TW"
  safe_mode: bool           # true = 低成本欄位遮罩（不含評分）
  candidate_limit: int      # 最多回傳幾間，預設 8
output:
  candidates: list[Candidate]   # 候選店家清單
  meta: dict                    # source（cache/live_api/budget_blocked）、query
tool: tools/candidate_search.py — CandidateSearchSkill.run()
---

## 說明

搜尋字串組合規則：`{cuisine} {must_have} 餐廳`，例如「韓式 豆腐鍋 餐廳」。

**成本控制**：
- 先查本地 cache（TTL 3600 秒）
- cache miss 才消耗每日 API 配額（`CostGuardSkill`）
- 配額耗盡時回傳空清單 + `source: budget_blocked`

## 調用方式

```python
from tools.candidate_search import CandidateSearchSkill

candidates, meta = CandidateSearchSkill(maps_parser, cost_guard).run(
    intent=intent,
    region_code="TW",
    language_code="zh-TW",
    safe_mode=True,
    candidate_limit=8,
)
```
