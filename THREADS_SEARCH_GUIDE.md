# Threads 搜尋設定指南

本 agent 透過 **Google Custom Search API** 搜尋 `site:threads.net` 來取得 Threads 餐廳貼文，不需要 Threads 帳號或登入。

---

## 前置需求

- Google Cloud 專案（與 Maps API 同一個即可）
- 已啟用計費（Billing）

---

## 設定步驟

### Step 1：在 Google Cloud 啟用 Custom Search API

打開以下連結，點 **Enable**：

```
https://console.cloud.google.com/apis/api/customsearch.googleapis.com
```

### Step 2：把 Custom Search API 加入 API Key 的允許清單

你的 Google Maps API Key 預設只允許 Maps 相關 API，需要手動加上 Custom Search：

1. 前往 **APIs & Services → Credentials**
2. 點選你的 API Key 進入編輯
3. 找到 **API restrictions** 區塊
4. 在清單中加入 **Custom Search API**
5. 點 **Save**

> **注意：** 變更生效需要約 5 分鐘。

### Step 3：建立 Programmable Search Engine

1. 前往 https://programmablesearch.google.com/create
2. 搜尋範圍選 **Search the entire web**
3. 建立後，進入設定頁面複製 **Search engine ID**（格式類似 `a1b2c3:abc123def`）

### Step 4：設定 .env

在專案根目錄的 `.env` 加入：

```env
GOOGLE_SEARCH_CX=your_search_engine_id_here
```

**關於 API Key：** agent 預設沿用 `GOOGLE_MAPS_API_KEY`。若你的 Maps Key 是透過 Maps Platform 建立的（在 Cloud Console Credentials 顯示為 "Maps Platform API Key"），即使已在 API restrictions 加上 Custom Search，仍可能回傳 403。

此時建議另建一把普通 API Key（不選 Maps Platform）並設定：

```env
GOOGLE_SEARCH_API_KEY=your_new_key_here
```

agent 會優先使用 `GOOGLE_SEARCH_API_KEY`，沒設定才 fallback 到 `GOOGLE_MAPS_API_KEY`。

---

## 驗證設定

```bash
uv run python -c "
from tools.env_loader import load_local_env; load_local_env()
import os
print('GOOGLE_SEARCH_API_KEY:', os.environ.get('GOOGLE_SEARCH_API_KEY', '(未設定)')[:16] + '...')
print('GOOGLE_SEARCH_CX:', os.environ.get('GOOGLE_SEARCH_CX', '(未設定)'))
from tools.threads_scraper import ThreadsScraper
s = ThreadsScraper.from_env()
posts, errors = s.fetch_for_candidate(name='建一食堂', max_posts=5)
print('errors:', errors)
print('posts:', len(posts))
for p in posts: print(' -', p[:100])
"
```

成功輸出範例：

```
errors: {}
posts: 3
 - 建一食堂真的超好吃！生魚片新鮮，服務也很親切，下次還要來 ...
 - 台北中山區必吃！建一食堂的套餐超值，強烈推薦 ...
 - 建一食堂訂位要趁早，假日超難訂 ...
```

---

## 常見錯誤排查

| 錯誤訊息 | 原因 | 解法 |
|----------|------|------|
| `GOOGLE_SEARCH_CX not configured` | 未設定 env var | 在 `.env` 加上 `GOOGLE_SEARCH_CX` |
| `Google Custom Search failed: HTTP Error 403` + `API_KEY_SERVICE_BLOCKED` | API Key 沒開放 Custom Search | Step 2：在 API restrictions 加上 Custom Search API |
| `Google Custom Search failed: HTTP Error 403` + `accessNotConfigured` | Custom Search API 未啟用 | Step 1：在 Cloud Console 啟用 API |
| `no Threads results found on Google` | Google 尚未索引該餐廳的 Threads 貼文 | 正常現象，不影響其他推薦邏輯 |

---

## 運作方式

```
fetch_posts_with_engagement("建一食堂")
    │
    ▼
Google Custom Search API
  query: site:threads.net "建一食堂"
    │
    ▼
解析 snippet / title → list[{"text": str, "like_count": 0}]
    │
    ▼
依長度過濾（>= 15 字）、去 UI 雜訊
    │
    ▼
存入 .cache/threads_cache.json（TTL 1 小時）
    │
    ▼
social_text_adapter 整合進候選店家
    │
    ▼
vibe_summarizer → reason_composer 輸出 social_highlights
```

---

## 使用限制

| 項目 | 限制 |
|------|------|
| 免費額度 | 每日 100 次查詢 |
| 付費方案 | $5 / 1,000 次查詢 |
| 每次最多結果數 | 10 筆 |
| 每日查詢上限（agent 內部） | 50 次（可透過 `THREADS_DAILY_CALL_LIMIT` 調整） |

每日 100 次免費額度在正常使用情境（每次查詢 3 間餐廳）下約可支撐 33 次完整推薦請求。

---

## 停用 Threads 搜尋

```bash
# 單次停用
uv run restaurant-agent agent --query "韓式" --no-threads

# 永久停用（.env）
THREADS_ENABLED=false
```
