---
name: reservation-checker
description: 為每間候選店家查詢預約方式，偵測已知訂位平台連結（Inline、EZTable、iCHEF 等），填入 reservation_url 或電話號碼。
---

## 介面規格

**Input**
- `candidates: list[Candidate]` — 已經過 review-fetcher 的清單（含 phone、website、reservable）

**Output**
- `candidates: list[Candidate]` — 同清單，reservation_url / phone 已填入
- `meta: dict`
  - `reservable_count: int` — 有任何預約資訊（電話或網址）的店家數
  - `has_booking_url: int` — 成功找到線上訂位網址的店家數
  - `has_phone_only: int` — 只有電話、無線上訂位的店家數

**Tool**: `tools/reservation_checker.py — ReservationCheckerSkill.run()`

---

## 資料來源

Google Places API 的 `nationalPhoneNumber`、`websiteUri`、`reservable` 三個欄位（由 `review-fetcher` 在 Details 呼叫時一併取得）。

## 偵測邏輯

1. **線上訂位平台比對**：對 `websiteUri` 做 substring 比對，依序檢查：
   - `inline.app` → Inline
   - `eztable.com.tw` → EZTable
   - `ichoose.com.tw` → iCHEF Reserve
   - `opentable.com` → OpenTable
   - `tablecheck.com` → TableCheck
   - `jresv.com` → J-Resv

2. **reservable=True 降級**：若 Google 標記可預約但 website 不是已知平台，直接以 `websiteUri` 作為 `reservation_url`。

3. **電話 fallback**：無線上訂位網址時，`reservation_url` 為 `None`，但 `phone` 仍填入（若有）。

## 輸出欄位說明

| 欄位 | 說明 |
|------|------|
| `candidate.phone` | 電話號碼（本地格式，例如 `02 1234 5678`） |
| `candidate.reservation_url` | 訂位網址（已知平台 or websiteUri）；無則 `None` |
| `candidate.reservable` | Google 標記是否可預約（`True/False/None`） |

## 調用方式

```python
from tools.reservation_checker import ReservationCheckerSkill

candidates, meta = ReservationCheckerSkill().run(candidates=candidates)
# meta["has_booking_url"] → 找到線上訂位網址的店家數
```
