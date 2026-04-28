import unittest

from tools.vibe_summarizer import summarize_vibes


class VibeSummarizerTests(unittest.TestCase):
    def test_returns_top_tags(self) -> None:
        posts = [
            "這家很好拍，網美都來打卡",
            "人很多要排隊，候位 30 分鐘",
            "豆腐鍋很好吃",
        ]
        tags = summarize_vibes(posts)
        self.assertEqual(tags[0], "#出片")
        self.assertIn("#排隊", tags)
        self.assertIn("#豆腐鍋專門", tags)

    def test_returns_fallback_when_no_signal(self) -> None:
        tags = summarize_vibes(["今天吃飯", "天氣很好"])
        self.assertEqual(tags, ["#資訊不足", "#待補社群資料", "#先看地圖評價"])


if __name__ == "__main__":
    unittest.main()
