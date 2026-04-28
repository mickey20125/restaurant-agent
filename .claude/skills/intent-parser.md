---
name: Intent Parser
description: 解析使用者的繁中自然語言查詢，提取結構化意圖欄位，供後續 skills 使用。
input:
  query: string          # 使用者原始查詢（必填）
  non_engineer_logic: string  # 非工程師補充邏輯（選填）
output:
  cuisine: string | null       # 料理類型（韓式/日式/台式…）
  must_have: string | null     # 必點菜色（如「豆腐鍋」）
  max_walk_minutes: int        # 最大步行時間，預設 20
  min_rating: float | null     # 最低評分門檻
  needs_high_rating: bool      # 是否要求高評價
  non_engineer_logic: string   # 原樣傳遞的邏輯字串
tool: tools/intent_parser.py — IntentParserSkill.run()
---

## 說明

用 regex 從繁中查詢中萃取：

- **步行時間**：`(\d+)\s*分(?:鐘)?` → `max_walk_minutes`
- **料理類型**：比對 `KNOWN_CUISINES`（韓式、日式、台式…）
- **必點菜色**：`有xxx`、`要有xxx`、`一定要有xxx` 或關鍵字直接命中
- **評分需求**：`評價高` / `高評價` → `needs_high_rating=True`，`min_rating` 至少 4.2

## 調用方式

```python
from tools.intent_parser import IntentParserSkill

intent = IntentParserSkill().run(
    query="走路 20 分鐘內，韓式，評價高，有豆腐鍋",
    non_engineer_logic="週末優先人氣店",
)
```

## 注意事項

- 若查詢無步行時間，預設 `max_walk_minutes = 20`
- 非工程師邏輯不做解析，原樣存入 `non_engineer_logic`，由後段 skills 引用
