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

    def _make_scraper(self, *, daily_limit: int = 50, monthly_limit: int = 2000) -> ThreadsScraper:
        return ThreadsScraper(
            cache_path=self.cache_path,
            usage_path=self.usage_path,
            daily_limit=daily_limit,
            monthly_limit=monthly_limit,
        )

    def test_within_limit_allows_usage(self) -> None:
        scraper = self._make_scraper(daily_limit=3)
        allowed, _ = scraper._allow_usage()
        self.assertTrue(allowed)
        allowed, _ = scraper._allow_usage()
        self.assertTrue(allowed)
        allowed, _ = scraper._allow_usage()
        self.assertTrue(allowed)

    def test_over_daily_limit_blocks_usage(self) -> None:
        scraper = self._make_scraper(daily_limit=2)
        scraper._allow_usage()
        scraper._allow_usage()
        allowed, msg = scraper._allow_usage()
        self.assertFalse(allowed)
        self.assertIn("daily limit", msg)

    def test_over_monthly_limit_blocks_usage(self) -> None:
        scraper = self._make_scraper(daily_limit=100, monthly_limit=2)
        scraper._allow_usage()
        scraper._allow_usage()
        allowed, msg = scraper._allow_usage()
        self.assertFalse(allowed)
        self.assertIn("monthly limit", msg)

    def test_over_limit_returns_budget_error(self) -> None:
        scraper = self._make_scraper(daily_limit=0)
        _, errors = scraper.fetch_for_candidate(name="X餐廳", max_posts=5)
        self.assertIn("budget", errors)

    def test_scrape_exception_returns_error(self) -> None:
        scraper = self._make_scraper()
        with patch.object(scraper, "_scrape", side_effect=RuntimeError("api error")):
            result, errors = scraper.fetch_for_candidate(name="X餐廳", max_posts=5)
        self.assertEqual(result, [])
        self.assertIn("scrape", errors)

    def test_get_monthly_usage_counts_current_month(self) -> None:
        scraper = self._make_scraper(daily_limit=10, monthly_limit=100)
        scraper._allow_usage()
        scraper._allow_usage()
        scraper._allow_usage()
        self.assertEqual(scraper.get_monthly_usage(), 3)

    def test_get_monthly_usage_empty(self) -> None:
        scraper = self._make_scraper()
        self.assertEqual(scraper.get_monthly_usage(), 0)


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

    def test_brave_monthly_limit_from_env(self) -> None:
        with patch.dict(os.environ, {"BRAVE_MONTHLY_LIMIT": "500"}):
            scraper = ThreadsScraper.from_env()
        self.assertIsNotNone(scraper)
        assert scraper is not None
        self.assertEqual(scraper.monthly_limit, 500)


if __name__ == "__main__":
    unittest.main()
