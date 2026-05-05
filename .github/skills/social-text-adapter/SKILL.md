---
name: social-text-adapter
description: 將社群貼文資料附加到各候選店家。支援本地檔案、inline 文字、Instagram（instagrapi）、以及 Threads.net（Playwright 無登入爬取）四種來源，自動合併去重。
---

## 介面規格

**Input**
- `candidates: list[Candidate]` — 來自 review-fetcher 的清單
- `social_file: string | null` — 本地檔案路徑（選填）
- `inline_posts: list[str] | null` — 直接傳入的文字片段（選填）
- `ig_fetcher: InstagramFetcher | null` — Instagram 爬蟲實例（選填，由 orchestrator 傳入）
- `ig_max_posts: int` — 每間店最多抓幾則 IG 貼文，預設 10
- `threads_scraper: ThreadsScraper | null` — Threads 爬蟲實例（選填，由 orchestrator 傳入）
- `threads_max_posts: int` — 每間店最多抓幾則 Threads 貼文，預設 10

**Output**
- `candidates: list[Candidate]` — 同清單，social_posts 已填入
- `meta: dict`
  - `stores_with_social_posts: int`
  - `global_posts: int`
  - `ig_fetched: int` — 成功抓到 IG 貼文的店家數
  - `threads_fetched: int` — 成功抓到 Threads 貼文的店家數

**Tool**: `tools/social_text_adapter.py — SocialTextAdapterSkill.run()`

---

## 資料來源（四種，自動合併去重）

### 1. 本地檔案（`social_file`）

支援兩種格式：

**JSON**
```json
{"韓味豆腐鍋": ["裝潢很韓系", "晚餐要排隊但很值得"]}
```

**純文字（`店名|貼文內容`）**
```
韓味豆腐鍋|裝潢很韓系，很多人打卡
韓式小館|價格平價，份量大
拍照很出片，朋友都說氛圍好      ← 無 | 視為全域貼文（附加到所有店家）
```

範例檔案：`.claude/resources/social_posts_by_store.txt`

### 2. Inline 文字（`inline_posts`）

直接從程式傳入字串清單，視為全域貼文。

### 3. Instagram 即時爬取（`ig_fetcher`）

由 `tools/instagram_fetcher.py` 的 `InstagramFetcher` 提供，每間候選店家執行：

1. **Hashtag 搜尋**：`#{store_name}` 取 top posts 的 caption
2. **Location 搜尋**：用候選店家的 lat/lng 搜尋最近的 IG 地點，取近期貼文

預設關閉（需在 `.env` 設定 `INSTAGRAM_ENABLED=true`）。

### 4. Threads.net 即時爬取（`threads_scraper`）

由 `tools/threads_scraper.py` 的 `ThreadsScraper` 提供，使用 **Playwright 無頭 Chromium**，**無需登入**。

搜尋網址：`https://www.threads.net/search?q={store_name}&serp_type=keyword`

擷取流程：
1. **API 攔截（主要）**：監聽 GraphQL / JSON 回應，遞迴提取 `text`/`caption`/`body` 欄位
2. **DOM 回退（備用）**：若 API 回應不足，從 `article span`、`div[dir='auto']` 等元素取文字

預設開啟，設定 `THREADS_ENABLED=false` 可停用。

## 環境變數

```
# Instagram（預設關閉）
INSTAGRAM_ENABLED=true
INSTAGRAM_USERNAME=your_username
INSTAGRAM_PASSWORD=your_password
IG_DAILY_CALL_LIMIT=100         # 選填，預設 100
IG_CACHE_TTL_SECONDS=3600       # 選填，預設 3600

# Threads（預設開啟）
THREADS_ENABLED=true            # 設為 false 可關閉
THREADS_DAILY_CALL_LIMIT=50     # 選填，預設 50
THREADS_CACHE_TTL_SECONDS=3600  # 選填，預設 3600
```

Cache 路徑：
- IG session：`.cache/instagram_session.json`
- IG 貼文：`.cache/instagram_cache.json`
- Threads 貼文：`.cache/threads_cache.json`
- Threads 用量：`.cache/threads_daily_usage.json`

## CLI 使用

```bash
# 預設：Threads 開啟，IG 關閉（除非 .env 有 INSTAGRAM_ENABLED=true）
restaurant-agent agent --query "韓式，有豆腐鍋"

# 停用 Threads
restaurant-agent agent --query "韓式" --no-threads

# 停用 IG
restaurant-agent agent --query "韓式" --no-instagram

# 調整每間店最多抓幾則貼文
restaurant-agent agent --query "韓式" --threads-max-posts 15 --ig-max-posts 20

# Threads 每日預算與 cache TTL
restaurant-agent agent --query "韓式" --threads-daily-limit 30 --threads-cache-ttl-seconds 7200
```

## 程式調用

```python
from tools.instagram_fetcher import InstagramFetcher
from tools.threads_scraper import ThreadsScraper
from tools.social_text_adapter import SocialTextAdapterSkill

ig = InstagramFetcher.from_env()       # None unless INSTAGRAM_ENABLED=true
threads = ThreadsScraper.from_env()    # None only if THREADS_ENABLED=false

candidates, meta = SocialTextAdapterSkill().run(
    candidates=candidates,
    social_file=".claude/resources/social_posts_by_store.txt",
    ig_fetcher=ig,
    ig_max_posts=10,
    threads_scraper=threads,
    threads_max_posts=10,
)
# meta["threads_fetched"] → 成功抓到 Threads 貼文的店家數
```

## 注意事項

- 任一來源失敗（超預算、爬取錯誤）只記錄到 `candidate.risks`，不中斷流程
- 每日用量超過限制時跳過該店（不報錯）
- 店名匹配（本地檔案）用包含關係（`store_name in candidate.name` 或反向）
- 無任何社群資料時 `social_posts` 為空清單，vibe-summarizer 會回傳 fallback tags
