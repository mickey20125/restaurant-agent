# Restaurant Agent

餐廳推薦工具鏈，由 9 個主要 stage 組成完整 agent pipeline（每個 stage 由對應 skill / 模組實作），支援 Google Maps 評論、Threads 社群熱度、線上訂位資訊，以及四種角色模式輸出（美食 KOL / 健身教練 / 在地老饕 / 約會顧問）。

---

## Quick Start

```bash
uv lock && uv sync
uv run restaurant-agent --help
```

---

## 環境設定

```bash
cp .env.example .env
```

`.env` 範例：

```env
# Google Maps（必填）
GOOGLE_MAPS_API_KEY=YOUR_MAPS_KEY

# Brave Search API（Threads 搜尋用，必填）
# 詳細設定步驟：THREADS_SEARCH_GUIDE.md
BRAVE_SEARCH_API_KEY=YOUR_BRAVE_KEY

# 預設出發地（選填，--user-lat / --user-lng 可覆蓋）
DEFAULT_USER_LAT=25.047094
DEFAULT_USER_LNG=121.542698

# Maps API 保護（選填）
MAPS_DAILY_CALL_LIMIT=100
MAPS_CACHE_TTL_SECONDS=86400

# Threads（選填）
THREADS_ENABLED=true
THREADS_DAILY_CALL_LIMIT=50
THREADS_CACHE_TTL_SECONDS=3600

# Instagram（預設關閉）
# INSTAGRAM_ENABLED=true
# INSTAGRAM_USERNAME=your_username
# INSTAGRAM_PASSWORD=your_password
```

> Threads 搜尋透過 Brave Search API（免費 2000 次/月），申請 key 及詳細設定見 [THREADS_SEARCH_GUIDE.md](THREADS_SEARCH_GUIDE.md)。

---

## Foodie Agent（主要入口）

### 角色模式

使用 Foodie Agent 時，可以選擇以不同角色視角輸出推薦，也可以不選（預設情境分析模式）：

| 模式 | 觸發方式 | 核心特色 |
|------|---------|----------|
| 🔥 美食 KOL | 「用 KOL 模式」「話題熱度」 | 社群聲量排序，強調「為什麼現在去」 |
| 💪 健身教練 | 「健康」「卡路里」「減脂」 | 健康路線 + 罪惡路線雙軌，附卡路里換算 |
| 📍 在地老饕 | 「在地人推薦」「隱藏餐廳」 | 外地人不知道、在地人才懂的選擇 |
| ✨ 約會顧問 | 「約會」「帶另一半」 | 依感情狀態給不同方向，環境對話友好度優先 |
| — 預設 | 未指定 | 情境分析 + 調性展開，`--markdown` 格式輸出 |

角色模式詳細規格：[.claude/skills/character-simulation.md](.claude/skills/character-simulation.md)

### Agent 工作流程

```
Step 0：開場選單（先查 demo list）
    ├─ 有預存 demo → 顯示 D1–Dn + 1–5 混合選單
    │       └─ 選 Dn → Step 0-D（載入 demo，選角色 → Step 3）
    └─ 無 demo → 純角色選單 1–5
           ↓
Step 1：情境判斷（場合識別 / 模糊指令解碼 / 調性展開）
           ↓
Step 2：呼叫 pipeline CLI
    ├─ 有角色模式 → 取 JSON → Step 3 套入角色模板
    └─ 無角色模式 → 加 --markdown → 直接貼輸出
           ↓
Step 3：角色模式格式化（含 phone / reservation_url / social_highlights）
```

### Demo 模式

Demo 模式讓你事先預跑查詢、存檔，demo 當天直接載入結果不消耗 API 額度。

```bash
# 預跑並存為 demo case
uv run python -m tools.cli agent \
  --query "帶外國朋友吃台灣味，步行25分鐘內" \
  --user-lat 25.047094 --user-lng 121.542698 \
  --logic "有台灣特色，非觀光客店" \
  --top-k 3 --save-demo "情境2-帶外國朋友私房台味"

# 列出所有 demo case
uv run python -m tools.cli demo list

# 取出特定 case（供 Foodie Agent 呼叫）
uv run python -m tools.cli demo show 情境2-帶外國朋友私房台味
```

Demo 檔案存於 `.demo/`，格式為 JSON，包含 `demo_name`、`query`、`logic`、`saved_at`、`recommendations` 等欄位。

---

## Skill Pipeline（9 Stages）

此處的「9」指 pipeline 的 9 個主要 stage（不是 repository 內所有技能描述檔數量）。

### 架構圖

```
使用者查詢
    │
    ▼
┌─────────────────┐
│  intent-parser  │  自然語言 → 結構化意圖
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
│                 │  評論 + 電話 + 網站 + reservable 旗標
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
│ social-text-adapter  │  整合本地檔 / IG / Threads 貼文
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
│                 │  基底權重：評分(50%) + 人氣(15%) + 距離(15%)
│                 │  額外調整：must_have(+0.20/-0.30) + vibe(+0.10)
└────────┬────────┘
         │
         ▼
┌──────────────────┐
│ reason-composer  │  組合推薦理由、風格標籤、風險提醒
│  + cost-guard    │  Threads 金句、訂位連結 / 電話
└──────────────────┘
```

備註：`must_have` 與 `vibe` 為額外 bonus/penalty；最終 `score` 會做 normalization（限制在 `0–1` 範圍）。

Pipeline stage ↔ 實作檔案：`intent-parser→tools/intent_parser.py | candidate-search→tools/candidate_search.py | hard-constraint-filter→tools/hard_constraint_filter.py | review-fetcher→tools/review_fetcher.py | reservation-checker→tools/reservation_checker.py | social-text-adapter→tools/social_text_adapter.py | vibe-summarizer→tools/vibe_summarizer.py | ranker→tools/ranker.py | reason-composer→tools/reason_composer.py`

### 一次執行整條 pipeline

```bash
uv run restaurant-agent agent \
  --query "走路 30 分鐘內，韓式，評價高" \
  --user-lat 25.047094 \
  --user-lng 121.542698 \
  --markdown
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
| `--markdown` | 輸出格式化 markdown（含電話/訂位/金句） | `false` |
| `--no-threads` | 停用 Threads 搜尋 | 預設開啟 |
| `--threads-max-posts` | 每店最多抓幾則 Threads 貼文 | `10` |
| `--threads-daily-limit` | Threads 每日查詢上限 | `50` |
| `--daily-limit` | Maps API 每日呼叫上限 | `100` |
| `--show-debug` | 顯示各 skill 中間結果 | `false` |
| `--save-demo NAME` | 儲存結果為 demo case（存入 `.demo/`） | — |
| `--demo-dir` | demo case 存放目錄 | `.demo` |

### 輸出欄位（每間推薦店）

```json
{
  "name": "韓蒔 HAN SHIH",
  "address": "台北市大安區四維路 180 號",
  "score": 0.71,
  "reason": "Google 評分 4.6；1056 則地圖評價；預估步行 21 分鐘",
  "vibe_tags": ["#豆腐鍋專門", "#辣感"],
  "social_highlights": ["超好吃的豆腐鍋，湯頭濃郁", "氣氛很韓系推薦給朋友"],
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

## Tool 0: Demo Case 管理

```bash
# 列出所有預存 case（JSON 陣列，含 demo_name / query / rec_count / saved_at）
uv run python -m tools.cli demo list

# 取出完整 JSON（Foodie Agent 在 Step 0-D 呼叫）
uv run python -m tools.cli demo show 情境1-久別重逢長聊
```

---

## Tool 1: Google Maps Parser

```bash
# 查詢基本資料
uv run restaurant-agent maps --name "涓豆腐 台北復興店"

# 抓評論
uv run restaurant-agent reviews --name "涓豆腐 台北復興店" --max-reviews 5

# 查看 API 來源（live / cache / fallback）
uv run restaurant-agent maps --name "涓豆腐 台北復興店" --show-meta

# 無 API key 的 demo mock
uv run restaurant-agent maps --name "涓豆腐 台北復興店" --mock
```

Details API field mask：

```
id, displayName, formattedAddress, location,
rating, userRatingCount, reviews,
nationalPhoneNumber, websiteUri, reservable
```

---

## Tool 2: Vibe Summarizer

```bash
uv run restaurant-agent vibe \
  --text "這家豆腐鍋超辣超下飯，平價但要排隊" \
  --text "裝潢好拍，很多人打卡"

# 或讀檔
uv run restaurant-agent vibe --file .claude/resources/sample_posts.txt
```

目前支援 tags：`#出片` `#排隊` `#老字號` `#CP值` `#辣感` `#豆腐鍋專門`

規則定義：[.claude/resources/vibe_tag_rules.md](.claude/resources/vibe_tag_rules.md)

---

## Tool 3: Expert Prompt Template

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
拍照很出片，氛圍好        ← 無 | 視為全域貼文

# JSON
{"韓味豆腐鍋": ["裝潢很韓系", "晚餐要排隊"]}
```

### Threads 搜尋（預設開啟）

透過 **Brave Search API** 搜尋 `site:threads.net`，無需 Threads 帳號。免費 2000 次/月。

需設定 `BRAVE_SEARCH_API_KEY`，詳細設定：[THREADS_SEARCH_GUIDE.md](THREADS_SEARCH_GUIDE.md)

Threads 貼文依 `like_count` 降序排序後取前 N 則為金句（`social_highlights`），已過濾 Threads 頁面 UI 字串。

```bash
# 停用 Threads
uv run restaurant-agent agent --query "韓式" --no-threads

# 調整每店最多抓幾則
uv run restaurant-agent agent --query "韓式" --threads-max-posts 15
```

Cache：`.cache/threads_cache.json` | 每日用量：`.cache/threads_daily_usage.json`

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
3. `Reservation Checker` 擴充：若 website 不是已知平台，抓頁面內容自動偵測。
4. 角色模式加上使用者偏好記憶，跨對話累積排除條件。
