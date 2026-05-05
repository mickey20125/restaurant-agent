from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.social_text_adapter import SocialTextAdapterSkill
from tools.types import Candidate


def _candidate(name: str) -> Candidate:
    return Candidate(
        place_id="p1",
        name=name,
        rating=4.5,
        address="台北市",
        lat=25.04,
        lng=121.54,
        user_rating_count=100,
    )


class FileLoadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = SocialTextAdapterSkill()
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_pipe_delimited_store_posts_attached(self) -> None:
        path = self.tmp / "s.txt"
        path.write_text("韓味豆腐鍋|裝潢好拍\n韓味豆腐鍋|晚餐要排隊\n", encoding="utf-8")
        c = _candidate("韓味豆腐鍋")
        result, meta = self.skill.run(candidates=[c], social_file=str(path))
        self.assertIn("裝潢好拍", result[0].social_posts)
        self.assertIn("晚餐要排隊", result[0].social_posts)
        self.assertEqual(meta["stores_with_social_posts"], 1)

    def test_json_file_store_posts_attached(self) -> None:
        path = self.tmp / "s.json"
        path.write_text(
            json.dumps({"韓味豆腐鍋": ["氣氛好", "必點豆腐鍋"]}, ensure_ascii=False),
            encoding="utf-8",
        )
        c = _candidate("韓味豆腐鍋")
        result, _ = self.skill.run(candidates=[c], social_file=str(path))
        self.assertIn("氣氛好", result[0].social_posts)
        self.assertIn("必點豆腐鍋", result[0].social_posts)

    def test_global_posts_attached_to_all_candidates(self) -> None:
        path = self.tmp / "s.txt"
        path.write_text("全域推薦\n", encoding="utf-8")  # no | → global
        c1 = _candidate("A餐廳")
        c2 = _candidate("B餐廳")
        result, meta = self.skill.run(candidates=[c1, c2], social_file=str(path))
        self.assertIn("全域推薦", result[0].social_posts)
        self.assertIn("全域推薦", result[1].social_posts)
        self.assertEqual(meta["global_posts"], 1)

    def test_partial_name_match_store_in_candidate(self) -> None:
        """File key is substring of candidate name."""
        path = self.tmp / "s.txt"
        path.write_text("豆腐鍋|湯頭濃郁\n", encoding="utf-8")
        c = _candidate("韓味豆腐鍋")
        result, _ = self.skill.run(candidates=[c], social_file=str(path))
        self.assertIn("湯頭濃郁", result[0].social_posts)

    def test_partial_name_match_candidate_in_store(self) -> None:
        """Candidate name is substring of file key."""
        path = self.tmp / "s.txt"
        path.write_text("韓味豆腐鍋本店|裝潢很韓系\n", encoding="utf-8")
        c = _candidate("韓味豆腐鍋")
        result, _ = self.skill.run(candidates=[c], social_file=str(path))
        self.assertIn("裝潢很韓系", result[0].social_posts)

    def test_missing_file_returns_empty(self) -> None:
        c = _candidate("A餐廳")
        result, meta = self.skill.run(candidates=[c], social_file="/no/such/file.txt")
        self.assertEqual(result[0].social_posts, [])
        self.assertEqual(meta["stores_with_social_posts"], 0)

    def test_none_social_file(self) -> None:
        c = _candidate("A餐廳")
        result, _ = self.skill.run(candidates=[c], social_file=None)
        self.assertEqual(result[0].social_posts, [])


class InlinePostsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = SocialTextAdapterSkill()

    def test_inline_posts_attached_to_all_candidates(self) -> None:
        c1 = _candidate("A餐廳")
        c2 = _candidate("B餐廳")
        result, _ = self.skill.run(
            candidates=[c1, c2],
            social_file=None,
            inline_posts=["這家很好吃", "環境不錯"],
        )
        self.assertIn("這家很好吃", result[0].social_posts)
        self.assertIn("這家很好吃", result[1].social_posts)

    def test_blank_inline_posts_are_skipped(self) -> None:
        c = _candidate("A餐廳")
        result, _ = self.skill.run(
            candidates=[c],
            social_file=None,
            inline_posts=["  ", "有效貼文", ""],
        )
        self.assertIn("有效貼文", result[0].social_posts)
        self.assertNotIn("  ", result[0].social_posts)


class MockFetcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = SocialTextAdapterSkill()

    def test_threads_scraper_posts_attached(self) -> None:
        class FakeThreads:
            def fetch_posts_with_engagement(self, *, name: str, max_posts: int):
                return [{"text": f"Threads:{name}", "like_count": 5}], {}

        c = _candidate("B餐廳")
        result, meta = self.skill.run(
            candidates=[c],
            social_file=None,
            threads_scraper=FakeThreads(),
            threads_max_posts=5,
        )
        self.assertIn("Threads:B餐廳", result[0].social_posts)
        self.assertEqual(meta["threads_fetched"], 1)

    def test_threads_scraper_error_appended_to_risks(self) -> None:
        class ErrorThreads:
            def fetch_posts_with_engagement(self, *, name: str, max_posts: int):
                return [], {"budget": "daily limit reached"}

        c = _candidate("B餐廳")
        result, meta = self.skill.run(
            candidates=[c], social_file=None, threads_scraper=ErrorThreads()
        )
        self.assertTrue(any("Threads" in r for r in result[0].risks))
        self.assertEqual(meta["threads_fetched"], 0)

    def test_meta_counts_are_accurate(self) -> None:
        class FakeThreads:
            def fetch_posts_with_engagement(self, *, name: str, max_posts: int):
                return [{"text": "Threads貼文", "like_count": 10}], {}

        candidates = [_candidate("A餐廳"), _candidate("B餐廳")]
        _, meta = self.skill.run(
            candidates=candidates,
            social_file=None,
            threads_scraper=FakeThreads(),
        )
        self.assertEqual(meta["threads_fetched"], 2)
        self.assertEqual(meta["stores_with_social_posts"], 2)


if __name__ == "__main__":
    unittest.main()
