# Restaurant Agent

這個 repo 是一個可直接執行的餐廳推薦工具鏈，由 9 個 skills 組成完整的 agent pipeline，支援 Google Maps 評論、Threads 社群熱度與線上訂位資訊整合。

## Quick Start (uv)

```bash
uv lock
uv sync
```

執行指令時使用 `uv run`：

```bash
uv run restaurant-agent --help
```

## 環境設定

複製範本並填入金鑰：

```bash
cp .env.example .env
```

`.env` 範例：

```env
# Google Maps（必填）
GOOGLE_MAPS_API_KEY=YOUR_KEY

# 預設出發地（選填，也可每次用 --user-lat / --user-lng 傳入）
DEFAULT_USER_LAT=25.047094
DEFAULT_USER_LNG=121.542698

# Maps API 保護（選填）
MAPS_DAILY_CALL_LIMIT=100
MAPS_CACHE_TTL_SECONDS=86400
AGENT_DAILY_USAGE_PATH=.cache/agent_daily_usage.json
AGENT_SKILL_CACHE_PATH=.cache/agent_skill_cache.json

# Threads 爬蟲（預設開啟，設 false 可關閉）
THREADS_ENABLED=true
THREADS_DAILY_CALL_LIMIT=50
THREADS_CACHE_TTL_SECONDS=3600

# Instagram（預設關閉，帳號驗證後設 true）
# INSTAGRAM_ENABLED=true
# INSTAGRAM_USERNAME=your_username
# INSTAGRAM_PASSWORD=your_password
# IG_DAILY_CALL_LIMIT=100
# IG_CACHE_TTL_SECONDS=3600
```

---

## Skill Pipeline（9 Skills）

### Workflow

```
使用者查詢
    │
    ▼
┌─────────────────┐
│  intent-parser  │  解析自然語言 → 結構化意圖
│                 │  （料理類型、步行時間、必點菜色、評分需求）
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ candidate-search│  Google Maps Text Search → 候選店家清單
└────────┬────────┘
         │
         ▼
┌──────────────────────┐
│ hard-constraint-     │  過濾超出步行距離、缺少必點菜色的店家
│ filter               │
└────────┬─────────────┘
         │
         ▼
┌─────────────────┐
│ review-fetcher  │  Google Maps Place Details →
│                 │  評論文字 + 電話 + 網站 + reservable 旗標
└────────┬────────┘
         │
         ▼
┌──────────────────────┐
│ reservation-checker  │  比對已知訂位平台（Inline / EZTable /
│                      │  iCHEF / OpenTable）→ reservation_url
│                      │  無線上訂位則保留電話號碼
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ social-text-adapter  │  整合本地檔案 / IG / Threads 貼文文字
│                      │  Threads 貼文依 like_count 排序
│                      │  → social_posts + social_highlights
└────────┬─────────────┘
         │
         ▼
┌─────────────────┐
│ vibe-summarizer │  關鍵字比對 → vibe tags
│                 │  （#出片 #排隊 #豆腐鍋專門 等）
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     ranker      │  多因子計分排序
│                 │  評分(50%) + 人氣(15%) + 距離(15%)
│                 │  + 必點符合度(20%) + vibe(10%)
└────────┬────────┘
         │
         ▼
┌──────────────────┐
│ reason-composer  │  組合推薦理由、風格標籤、風險提醒
│  + cost-guard    │  Threads 金句、訂位連結 / 電話
└──────────────────┘
         │
         ▼
    top-3 推薦
```

### 一次執行整條 pipeline

```bash
uv run restaurant-agent agent \
  --query "走路 30 分鐘內，韓式，評價高" \
  --user-lat 25.047094 \
  --user-lng 121.542698 \
  --social-file .claude/resources/social_posts_by_store.txt \
  --show-debug
```

### 常用 CLI 選項

| 選項 | 說明 | 預設 |
|------|------|------|
| `--query` | 自然語言查詢（必填） | — |
| `--user-lat` / `--user-lng` | 出發地座標 | 讀 `.env` |
| `--logic` | 非工程師邏輯補充 | `""` |
| `--top-k` | 最終推薦數 | `3` |
| `--candidate-limit` | 搜尋候選上限 | `8` |
| `--max-reviews-per-place` | 每店最多評論數 | `3` |
| `--social-file` | 本地貼文文字檔路徑 | — |
| `--social-text` | 直接傳入貼文文字（可重複） | — |
| `--no-threads` | 停用 Threads 爬蟲 | 預設開啟 |
| `--threads-max-posts` | 每店最多抓幾則 Threads 貼文 | `10` |
| `--threads-daily-limit` | Threads 每日爬取上限 | `50` |
| `--no-instagram` | 停用 Instagram 爬蟲 | 預設關閉 |
| `--ig-max-posts` | 每店最多抓幾則 IG 貼文 | `10` |
| `--daily-limit` | Maps API 每日呼叫上限 | `100` |
| `--show-debug` | 顯示各 skill 中間結果 | `false` |

### 輸出欄位（每間推薦店）

```json
{
  "name": "韓蒔 HAN SHIH",
  "address": "台北市大安區四維路 180 號",
  "score": 0.71,
  "reason": "Google 評分 4.6；1056 則地圖評價；預估步行 21 分鐘",
  "vibe_tags": ["#豆腐鍋專門", "#辣感"],
  "social_highlights": ["超好吃的豆腐鍋，湯頭濃郁", "氣氛很韓系，推薦給朋友"],
  "phone": "02 2700 6868",
  "reservation_url": "https://inline.app/booking/xxx",
  "risks": ["部分菜色有辣，點餐時請說明"],
  "evidence": [
    "評論摘錄：小菜可以續，有麥茶",
    "風格標籤：#豆腐鍋專門 #辣感",
    "Threads 金句：超好吃的豆腐鍋，湯頭濃郁"
  ],
  "metrics": {
    "rating": 4.6,
    "user_rating_count": 1056,
    "walk_minutes": 21.1,
    "must_have_match": true
  }
}
```

---

## Tool 1: Google Maps Parser

```bash
# 查詢店家基本資料
uv run restaurant-agent maps --name "涓豆腐 台北復興店"

# 抓評論
uv run restaurant-agent reviews --name "涓豆腐 台北復興店" --max-reviews 5

# 查看 API 來源（live / cache / fallback）
uv run restaurant-agent maps --name "涓豆腐 台北復興店" --show-meta

# 無 API key 的 demo mock
uv run restaurant-agent maps --name "涓豆腐 台北復興店" --mock
```

### Google Maps API 設定

1. 在 Google Cloud 建立專案並開啟計費。
2. 啟用 **Places API（New）**。
3. 建立 API Key，建議限制只允許 Places API。

Details API 使用的 field mask（含最新欄位）：

```
id, displayName, formattedAddress, location,
rating, userRatingCount, reviews,
nationalPhoneNumber, websiteUri, reservable
```

常見錯誤：
- `Missing Google Maps API key`：未設定 `GOOGLE_MAPS_API_KEY`
- `Google Places API error: 403`：未開啟 Places API 或 Billing 未啟用

---

## Tool 2: Vibe Summarizer

關鍵字比對將貼文/評論轉為風格標籤。

```bash
uv run restaurant-agent vibe \
  --text "這家豆腐鍋超辣超下飯，平價但要排隊" \
  --text "裝潢好拍，很多人打卡"

# 或讀檔
uv run restaurant-agent vibe --file .claude/resources/sample_posts.txt
```

目前支援 tags：`#出片` `#排隊` `#老字號` `#CP值` `#辣感` `#豆腐鍋專門`

規則定義：`.claude/resources/vibe_tag_rules.md`

---

## Tool 3: Expert Prompt Template

將非工程師定義的邏輯套入 prompt：

```bash
uv run restaurant-agent prompt \
  --logic "優先推薦有韓國人留言、且湯頭被稱讚的店" \
  --query "走路 20 分鐘內，韓式，評價高，有豆腐鍋"
```

---

## IG / Threads 社群資料

### 快速 demo（本地檔案）

```bash
uv run restaurant-agent agent \
  --query "韓式，有豆腐鍋" \
  --social-file .claude/resources/social_posts_by_store.txt
```

格式（pipe-delimited 或 JSON）：

```
# pipe-delimited
韓味豆腐鍋|裝潢很韓系，很多人打卡
韓味豆腐鍋|晚餐要排隊但很值得
拍照很出片，氛圍好   ← 無 | 視為全域貼文

# JSON
{"韓味豆腐鍋": ["裝潢很韓系", "晚餐要排隊"]}
```

### Threads 即時爬取（預設開啟）

Playwright 無頭 Chromium，無需登入：
- 主路徑：GraphQL API 攔截（含 `like_count` → 金句排序）
- 備用路徑：DOM 文字擷取

```bash
# 停用 Threads
uv run restaurant-agent agent --query "韓式" --no-threads

# 調整每店抓幾則
uv run restaurant-agent agent --query "韓式" --threads-max-posts 15
```

Threads cache 路徑：`.cache/threads_cache.json`
每日用量紀錄：`.cache/threads_daily_usage.json`

### Instagram（預設關閉）

需在 `.env` 設定帳號：

```env
INSTAGRAM_ENABLED=true
INSTAGRAM_USERNAME=your_username
INSTAGRAM_PASSWORD=your_password
```

---

## Test

```bash
uv run python -m unittest discover -s tests
```

目前覆蓋：`agent_orchestrator` / `social_text_adapter` / `threads_scraper` / `maps_guardrails` / `vibe_summarizer` / `expert_prompt` / `google_maps_reviews`

---

## Suggest Next Build

1. `Ranker` 改成可配置權重檔，讓不同場景（聚餐 vs 快食）可調策略。
2. `Reason Composer` 加上 LLM 版本，A/B test 規則式 vs 生成式推薦文案。
3. `Reservation Checker` 擴充：若 website 不是已知平台，抓頁面內容做自動偵測。
4. Threads 金句加上語言過濾（中文優先）與雜訊清理（去純 hashtag 行）。
