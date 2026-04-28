from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.threads_scraper import ThreadsScraper


class CacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.cache_path = str(self.tmp / "threads_cache.json")
        self.usage_path = str(self.tmp / "threads_usage.json")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make_scraper(self, ttl: int = 3600) -> ThreadsScraper:
        return ThreadsScraper(
            cache_path=self.cache_path,
            usage_path=self.usage_path,
            cache_ttl_seconds=ttl,
            daily_limit=50,
        )

    def test_cache_hit_returns_stored_posts(self) -> None:
        scraper = self._make_scraper()
        scraper._put_cached("A餐廳", ["帖子1", "帖子2"])
        result, errors = scraper.fetch_for_candidate(name="A餐廳", max_posts=10)
        self.assertEqual(result, ["帖子1", "帖子2"])
        self.assertEqual(errors, {})

    def test_cache_miss_calls_scrape(self) -> None:
        scraper = self._make_scraper()
        fake_posts = [{"text": "新帖子", "like_count": 0}]
        with patch.object(scraper, "_scrape", return_value=(fake_posts, {})) as mock_scrape:
            result, errors = scraper.fetch_for_candidate(name="B餐廳", max_posts=5)
        mock_scrape.assert_called_once_with("B餐廳", 5)
        self.assertEqual(result, ["新帖子"])

    def test_cache_miss_stores_result(self) -> None:
        scraper = self._make_scraper()
        fake_posts = [{"text": "帖子", "like_count": 3}]
        with patch.object(scraper, "_scrape", return_value=(fake_posts, {})):
            scraper.fetch_for_candidate(name="C餐廳", max_posts=5)
        cached = scraper._get_cached("C餐廳")
        self.assertEqual(cached, [{"text": "帖子", "like_count": 3}])

    def test_expired_cache_triggers_rescrape(self) -> None:
        scraper = self._make_scraper(ttl=1)
        payload = {
            "A餐廳": {"cached_at": int(time.time()) - 10, "data": ["舊帖子"]}
        }
        Path(self.cache_path).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
        fake_posts = [{"text": "新帖子", "like_count": 0}]
        with patch.object(scraper, "_scrape", return_value=(fake_posts, {})):
            result, _ = scraper.fetch_for_candidate(name="A餐廳", max_posts=5)
        self.assertEqual(result, ["新帖子"])

    def test_fresh_cache_not_expired(self) -> None:
        scraper = self._make_scraper(ttl=3600)
        scraper._put_cached("A餐廳", [{"text": "新鮮帖子", "like_count": 0}])
        result = scraper._get_cached("A餐廳")
        self.assertEqual(result, [{"text": "新鮮帖子", "like_count": 0}])

    def test_missing_cache_file_returns_none(self) -> None:
        scraper = self._make_scraper()
        self.assertIsNone(scraper._get_cached("不存在"))


class DailyLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.cache_path = str(self.tmp / "cache.json")
        self.usage_path = str(self.tmp / "usage.json")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make_scraper(self, limit: int) -> ThreadsScraper:
        return ThreadsScraper(
            cache_path=self.cache_path,
            usage_path=self.usage_path,
            daily_limit=limit,
        )

    def test_within_limit_allows_usage(self) -> None:
        scraper = self._make_scraper(limit=3)
        self.assertTrue(scraper._allow_usage())
        self.assertTrue(scraper._allow_usage())
        self.assertTrue(scraper._allow_usage())

    def test_over_limit_blocks_usage(self) -> None:
        scraper = self._make_scraper(limit=2)
        scraper._allow_usage()
        scraper._allow_usage()
        self.assertFalse(scraper._allow_usage())

    def test_over_limit_returns_budget_error(self) -> None:
        scraper = self._make_scraper(limit=0)
        _, errors = scraper.fetch_for_candidate(name="X餐廳", max_posts=5)
        self.assertIn("budget", errors)

    def test_scrape_exception_returns_error(self) -> None:
        scraper = self._make_scraper(limit=10)
        with patch.object(scraper, "_scrape", side_effect=RuntimeError("playwright missing")):
            result, errors = scraper.fetch_for_candidate(name="X餐廳", max_posts=5)
        self.assertEqual(result, [])
        self.assertIn("scrape", errors)


class FromEnvTests(unittest.TestCase):
    def test_returns_none_when_disabled(self) -> None:
        with patch.dict(os.environ, {"THREADS_ENABLED": "false"}):
            self.assertIsNone(ThreadsScraper.from_env())

    def test_returns_instance_when_enabled(self) -> None:
        with patch.dict(os.environ, {"THREADS_ENABLED": "true"}):
            scraper = ThreadsScraper.from_env()
        self.assertIsInstance(scraper, ThreadsScraper)

    def test_returns_instance_when_env_unset(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "THREADS_ENABLED"}
        with patch.dict(os.environ, env, clear=True):
            scraper = ThreadsScraper.from_env()
        self.assertIsInstance(scraper, ThreadsScraper)


class ExtractTextsFromJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scraper = ThreadsScraper.__new__(ThreadsScraper)

    def test_extracts_text_key(self) -> None:
        obj = {"text": "這是一則完整的貼文內容，超過十個字元"}
        results = self.scraper._extract_texts_from_json(obj)
        self.assertIn("這是一則完整的貼文內容，超過十個字元", results)

    def test_extracts_caption_key(self) -> None:
        obj = {"caption": "美食打卡文，今天來吃韓式料理超好吃"}
        results = self.scraper._extract_texts_from_json(obj)
        self.assertIn("美食打卡文，今天來吃韓式料理超好吃", results)

    def test_ignores_short_strings(self) -> None:
        obj = {"text": "短"}
        results = self.scraper._extract_texts_from_json(obj)
        self.assertNotIn("短", results)

    def test_recurses_into_nested_dict(self) -> None:
        obj = {"data": {"node": {"text": "巢狀文字內容，已經超過十個字元了"}}}
        results = self.scraper._extract_texts_from_json(obj)
        self.assertIn("巢狀文字內容，已經超過十個字元了", results)

    def test_recurses_into_list(self) -> None:
        obj = [{"text": "列表中的貼文文字，已超過十個字元"}]
        results = self.scraper._extract_texts_from_json(obj)
        self.assertIn("列表中的貼文文字，已超過十個字元", results)

    def test_depth_limit_prevents_infinite_recursion(self) -> None:
        # Root text should be extracted; deeply nested text beyond depth 12 is skipped
        obj: dict = {"text": "根層文字，已超過十個字元可被提取"}
        node = obj
        for _ in range(15):
            node["child"] = {"text": "深層文字，已超過十個字元但超過深度限制"}
            node = node["child"]
        results = self.scraper._extract_texts_from_json(obj)
        self.assertIn("根層文字，已超過十個字元可被提取", results)


class UrlEncodingTests(unittest.TestCase):
    """Verify that Chinese store names are URL-encoded in the search URL."""

    def test_chinese_name_is_url_encoded(self) -> None:
        url = ThreadsScraper._build_search_url("韓川館")
        self.assertNotIn("韓川館", url)
        self.assertIn("%", url)

    def test_ascii_name_preserved(self) -> None:
        url = ThreadsScraper._build_search_url("RestaurantA")
        self.assertIn("RestaurantA", url)

    def test_url_contains_serp_type(self) -> None:
        url = ThreadsScraper._build_search_url("any")
        self.assertIn("serp_type=keyword", url)


if __name__ == "__main__":
    unittest.main()
