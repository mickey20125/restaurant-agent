---
name: vibe-summarizer
description: 將每間店的社群貼文與評論合併，透過關鍵字比對轉換成 top-k 風格標籤（vibe tags）。
---

## 介面規格

**Input**
- `candidates: list[Candidate]` — 含 social_posts + reviews 的清單
- `top_k: int` — 每間店最多幾個 tag，預設 3

**Output**
- `candidates: list[Candidate]` — 同清單，vibe_tags 已填入
- `meta: dict` — processed 數量、top_k

**Tool**: `tools/vibe_skill.py — VibeSummarizerSkill.run()` → `tools/vibe_summarizer.py — summarize_vibes()`

---

## 說明

關鍵字規則定義在 `tools/vibe_summarizer.py` 的 `DEFAULT_TAG_RULES`，
非工程師可參考 `.claude/resources/vibe_tag_rules.md` 查閱或新增規則。

**fallback**：若無任何關鍵字命中，回傳 `["#資訊不足", "#待補社群資料", "#先看地圖評價"]`。

## 調用方式

```python
from tools.vibe_skill import VibeSummarizerSkill

candidates, meta = VibeSummarizerSkill().run(candidates=candidates, top_k=3)
```

## 目前支援的 Tags

| Tag | 範例觸發文字 |
|-----|------------|
| `#出片` | 好拍、打卡、網美、文青 |
| `#排隊` | 排隊、候位、客滿、熱門 |
| `#老字號` | 古早味、在地、祖傳 |
| `#CP值` | 平價、便宜、划算 |
| `#辣感` | 辣、麻辣、重口味 |
| `#豆腐鍋專門` | 豆腐鍋、嫩豆腐、순두부 |
