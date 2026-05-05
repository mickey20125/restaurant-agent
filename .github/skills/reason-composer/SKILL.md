---
name: reason-composer
description: 將排序後的 top-k 候選店家組合成人可閱讀的推薦理由，輸出 Recommendation 清單。
---

## 介面規格

**Input**
- `ranked_candidates: list[Candidate]` — 來自 ranker 的排序結果
- `intent: AgentIntent` — 含 must_have、non_engineer_logic
- `top_k: int` — 輸出幾間，預設 3

**Output**
- `recommendations: list[Recommendation]`
  - `place_id, name, address`
  - `score: float`
  - `reason: string` — 推薦理由（分號分隔）
  - `vibe_tags: list[str]`
  - `risks: list[str]` — 風險提醒
  - `evidence: list[str]` — 可驗證證據（評論摘錄、tag 來源）
  - `metrics: dict` — rating、user_rating_count、walk_minutes、must_have_match

**Tool**: `tools/reason_composer.py — ReasonComposerSkill.run()`

---

## 說明

**推薦理由組合**（按有無資料決定是否加入）：
- `Google 評分 X.X`
- `N 則地圖評價`
- `預估步行 N 分鐘`
- `內容訊號符合「must_have」`
- `符合設定邏輯：non_engineer_logic`

**風險來源**：
- 來自 Ranker 加入的 `risks`（評分低於門檻）
- 來自 HardConstraintFilter 加入的 `risks`（距離不確定）
- Composer 補充：無評論樣本、步行時間估算不完整

## 調用方式

```python
from tools.reason_composer import ReasonComposerSkill

recommendations = ReasonComposerSkill().run(
    ranked_candidates=ranked,
    intent=intent,
    top_k=3,
)
```
