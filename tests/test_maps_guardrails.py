from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.google_maps_parser import GoogleMapsParser, PlaceRecord
from tools.maps_guardrails import lookup_place_with_guardrails


class _FakeParser:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def lookup(self, store_name: str, *, region_code: str, language_code: str, safe_mode: bool) -> PlaceRecord:
        self.calls.append(
            {
                "store_name": store_name,
                "region_code": region_code,
                "language_code": language_code,
                "safe_mode": safe_mode,
            }
        )
        return PlaceRecord(
            name=store_name,
            rating=4.8,
            address="台北市中山區",
            lat=25.05,
            lng=121.53,
            user_rating_count=321,
        )


class MapsGuardrailsTests(unittest.TestCase):
    def test_cache_hit_avoids_second_api_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = str(Path(tmp) / "cache.json")
            usage_path = str(Path(tmp) / "usage.json")
            parser = _FakeParser()

            first, first_meta = lookup_place_with_guardrails(
                parser=parser,
                store_name="A店",
                region_code="TW",
                language_code="zh-TW",
                safe_mode=False,
                daily_limit=10,
                cache_ttl_seconds=3600,
                cache_path=cache_path,
                usage_path=usage_path,
                use_cache=True,
            )
            second, second_meta = lookup_place_with_guardrails(
                parser=parser,
                store_name="A店",
                region_code="TW",
                language_code="zh-TW",
                safe_mode=False,
                daily_limit=10,
                cache_ttl_seconds=3600,
                cache_path=cache_path,
                usage_path=usage_path,
                use_cache=True,
            )

            self.assertEqual(first.name, "A店")
            self.assertEqual(second.name, "A店")
            self.assertEqual(first_meta["source"], "live_api")
            self.assertEqual(second_meta["source"], "cache")
            self.assertEqual(len(parser.calls), 1)

    def test_daily_limit_returns_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = str(Path(tmp) / "cache.json")
            usage_path = str(Path(tmp) / "usage.json")
            parser = _FakeParser()

            _, first_meta = lookup_place_with_guardrails(
                parser=parser,
                store_name="A店",
                region_code="TW",
                language_code="zh-TW",
                safe_mode=False,
                daily_limit=1,
                cache_ttl_seconds=3600,
                cache_path=cache_path,
                usage_path=usage_path,
                use_cache=False,
            )
            second, second_meta = lookup_place_with_guardrails(
                parser=parser,
                store_name="B店",
                region_code="TW",
                language_code="zh-TW",
                safe_mode=False,
                daily_limit=1,
                cache_ttl_seconds=3600,
                cache_path=cache_path,
                usage_path=usage_path,
                use_cache=False,
            )

            self.assertEqual(first_meta["source"], "live_api")
            self.assertEqual(second_meta["source"], "fallback_daily_limit")
            self.assertIsNone(second.rating)
            self.assertIsNone(second.address)
            self.assertEqual(len(parser.calls), 1)

    def test_safe_mode_field_mask(self) -> None:
        self.assertIn("places.rating", GoogleMapsParser.field_mask(safe_mode=False))
        self.assertNotIn("places.rating", GoogleMapsParser.field_mask(safe_mode=True))


if __name__ == "__main__":
    unittest.main()
