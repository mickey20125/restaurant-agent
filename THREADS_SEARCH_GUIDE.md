# Threads 搜尋設定指南

本 agent 透過 **Brave Search API** 搜尋 `site:threads.net` 來取得 Threads 餐廳貼文，不需要 Threads 帳號或登入。

---

## 前置需求

- Brave Search API 帳號（免費方案：2000 次/月）

---

## 設定步驟

### Step 1：申請 Brave Search API Key

1. 前往 [api.search.brave.com](https://api.search.brave.com)
2. 點 **Get started for free** 註冊帳號
3. 建立 Subscription → 選 **Free** 方案（2000 queries/month）
4. 複製 API Key

### Step 2：設定 .env

在專案根目錄的 `.env` 加入：

```env
BRAVE_SEARCH_API_KEY=BSA...your_key_here...
```

---

## 驗證設定

```bash
uv run python -c "
from tools.env_loader import load_local_env; load_local_env()
from tools.threads_scraper import ThreadsScraper
s = ThreadsScraper.from_env()
print(f'本月已用: {s.get_monthly_usage()} / {s.monthly_limit} 次')
posts, errors = s.fetch_for_candidate(name='鼎泰豐', max_posts=5)
print('errors:', errors)
print('posts:', len(posts))
for p in posts: print(' -', p[:100])
"
```

成功輸出範例：

```
本月已用: 1 / 2000 次
errors: {}
posts: 5
 - 今天帶著家人中午吃新竹大遠百的鼎泰豐想說在百貨公司11 ...
 - 鼎泰豐外場服務員面試心得一面（一次就上✨） 目前狀況 ...
```

---

## 查詢本月用量

```bash
uv run python -c "
from tools.env_loader import load_local_env; load_local_env()
from tools.threads_scraper import ThreadsScraper
s = ThreadsScraper.from_env()
print(f'本月已用: {s.get_monthly_usage()} / {s.monthly_limit} 次')
"
```

用量記錄存於 `.cache/threads_daily_usage.json`，按日期記錄。

---

## 使用限制與保護機制

| 項目 | 預設值 | 調整方式 |
|------|--------|----------|
| 月上限 | 2000 次 | `.env` 設 `BRAVE_MONTHLY_LIMIT=2000` |
| 日上限 | 50 次 | CLI `--threads-daily-limit` 或 `THREADS_DAILY_CALL_LIMIT` |
| Cache TTL | 1 小時 | `THREADS_CACHE_TTL_SECONDS` |

每次查詢會先檢查 cache，cache 命中不消耗 API 額度。

月上限（2000 次）在正常使用情境下（每次查詢 3 間餐廳，有 cache）實際消耗遠低於上限。

---

## 運作方式

```
候選店家（Google Maps 全名，例如「比比拌韓式拌飯 部隊/豆腐鍋/法式甜點/會議餐盒」）
    │
    ▼
_short_name() 截短為可搜名稱（例如「比比拌韓式拌飯」）
  - 在 - / （ 等分隔符號前截斷
  - 移除結尾的地點後綴（店/路/區/館/場）
  - 最長 20 字
    │
    ▼
fetch_posts_with_engagement("<short_name>")
    │
    ▼
Brave Search API
  query: site:threads.net "<short_name>"
    │
    ▼
解析 title（description 為 Threads 通用登入文案時改用 title）
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

## 常見錯誤排查

| 錯誤訊息 | 原因 | 解法 |
|----------|------|------|
| `BRAVE_SEARCH_API_KEY not configured` | 未設定 env var | 在 `.env` 加上 `BRAVE_SEARCH_API_KEY` |
| `Brave Search failed: HTTP Error 401` | API Key 無效 | 確認 key 是否正確貼入 |
| `Brave Search failed: HTTP Error 429` | 超過速率限制 | 稍等後重試，或降低 `--threads-daily-limit` |
| `no Threads results found on Brave Search` | 該餐廳尚無 Threads 索引 | 正常現象，不影響其他推薦邏輯 |
| `monthly limit reached` | 本月用量已達上限 | 等下月重置，或調高 `BRAVE_MONTHLY_LIMIT` |

---

## 停用 Threads 搜尋

```bash
# 單次停用
uv run restaurant-agent agent --query "韓式" --no-threads

# 永久停用（.env）
THREADS_ENABLED=false
```
