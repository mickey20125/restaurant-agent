---
name: Hard Constraint Filter
description: 依硬性條件過濾候選店家：必點菜色名稱不符者直接踢除，步行時間超過上限者踢除。同時計算並寫入每間店的 walk_minutes。
input:
  candidates: list[Candidate]   # 來自 candidate-search 的候選清單
  intent: AgentIntent           # 含 must_have、max_walk_minutes
  user_lat: float | null        # 使用者位置（緯度）
  user_lng: float | null        # 使用者位置（經度）
output:
  kept: list[Candidate]         # 通過過濾的候選清單（walk_minutes 已填入）
  meta: dict                    # input、kept、dropped 數量
tool: tools/hard_constraint_filter.py — HardConstraintFilterSkill.run()
---

## 說明

**步行時間計算**：Haversine 公式，預設步速 4.5 km/h。

**過濾邏輯**：
1. `must_have` 有值時 → 店名中不含關鍵字者踢除
2. 步行時間 > `max_walk_minutes` → 踢除
3. 無法計算距離（缺 lat/lng）→ 保留但加入 risk 警示

## 調用方式

```python
from tools.hard_constraint_filter import HardConstraintFilterSkill

kept, meta = HardConstraintFilterSkill().run(
    candidates=candidates,
    intent=intent,
    user_lat=25.04,
    user_lng=121.54,
)
```

## 注意事項

- 未提供 `user_lat` / `user_lng` 時無法計算距離，所有店家都保留（加 risk）
- `must_have` 為 None 時跳過菜色過濾
