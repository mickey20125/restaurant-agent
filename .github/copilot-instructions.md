# Restaurant Agent — Copilot Instructions

這是一個繁體中文的餐廳推薦 Agent，核心是 Foodie Agent，透過 `python -m tools.cli agent` 執行本地 pipeline 搜尋、篩選並推薦餐廳。

## Agent 入口

收到使用者的餐廳需求時，啟動 `.github/agents/foodie-agent.agent.md`。

## Pipeline 指令格式

```bash
python -m tools.cli agent \
  --query "<情境 + 料理類型 + 具體需求>" \
  --user-lat 25.047094 \
  --user-lng 121.542698 \
  --logic "<情境 constraints + 調性描述>" \
  --top-k 3 \
  --markdown
```

## Skills 總覽

| Skill | 說明 |
|-------|------|
| `scenario-guide` | 將自然語言翻譯成 pipeline 參數，展開 2–3 種調性 |
| `character-simulation` | 四種角色模式輸出格式（KOL／健身教練／在地老饕／約會顧問） |
| `intent-parser` | 解析繁中查詢，提取料理類型、步行時間、評分需求等 |
| `candidate-search` | 依意圖組合搜尋字串，呼叫 Google Maps Places API |
| `hard-constraint-filter` | 依硬性條件（步行距離、必點菜色）過濾候選店家 |
| `review-fetcher` | 批量抓取 Google Maps 評論，更新評分與地址 |
| `social-text-adapter` | 附加 Threads / Instagram 社群貼文到候選店家 |
| `vibe-summarizer` | 將社群文字轉換成風格標籤（vibe tags） |
| `ranker` | 多維度加權評分並排序候選店家 |
| `reason-composer` | 組合人可閱讀的推薦理由 |
| `reservation-checker` | 偵測訂位平台連結或電話號碼 |
| `cost-guard` | 每日 API 用量保護與本地 cache 管理 |
