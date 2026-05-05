---
name: cost-guard
description: 跨 skill 共用的每日 API 用量保護與本地 cache 管理。由 orchestrator 初始化後注入各 skill。
---

## 介面規格

**初始化參數**（由 orchestrator 傳入，非直接調用）
- `daily_limit: int` — 每日最多幾次 live API 呼叫
- `usage_path: string` — 每日用量記錄檔路徑
- `cache_path: string` — skill 共用 cache 檔路徑

**API**
- `allow_api_calls(units) → (bool, meta)` — 是否允許本次呼叫
- `get_cached(namespace, key, ttl)` — 讀取 cache
- `put_cached(namespace, key, data)` — 寫入 cache

**Tool**: `tools/cost_guard.py — CostGuardSkill`

---

## 說明

**每日用量追蹤**：以 `.cache/agent_daily_usage.json` 記錄當天已呼叫次數，超過 `daily_limit` 時 `allow_api_calls()` 回傳 `False`。

**Namespace 隔離**：cache 用 namespace 區分不同 skill 的資料，目前使用：
- `candidate_search`（TTL 3600s）
- `reviews`（TTL 7200s）

**環境變數**：
- `MAPS_DAILY_CALL_LIMIT`：每日上限，預設 100
- `AGENT_DAILY_USAGE_PATH`：用量檔路徑
- `AGENT_SKILL_CACHE_PATH`：cache 檔路徑

## 初始化方式（由 orchestrator 處理）

```python
from tools.cost_guard import CostGuardSkill

cost_guard = CostGuardSkill(
    daily_limit=100,
    usage_path=".cache/agent_daily_usage.json",
    cache_path=".cache/agent_skill_cache.json",
)
```
