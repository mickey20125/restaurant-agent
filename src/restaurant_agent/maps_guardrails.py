from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path

from restaurant_agent.google_maps_parser import GoogleMapsParser, PlaceRecord

DEFAULT_CACHE_PATH = ".cache/maps_cache.json"
DEFAULT_USAGE_PATH = ".cache/maps_daily_usage.json"


def fallback_place_record(store_name: str) -> PlaceRecord:
    return PlaceRecord(
        name=store_name,
        rating=None,
        address=None,
        lat=None,
        lng=None,
        user_rating_count=None,
    )


class JsonFileStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def read(self) -> dict:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


class PlaceCache:
    def __init__(self, path: str = DEFAULT_CACHE_PATH) -> None:
        self.store = JsonFileStore(path)

    @staticmethod
    def _key(*, store_name: str, region_code: str, language_code: str, safe_mode: bool) -> str:
        normalized_name = store_name.strip().lower()
        return f"{region_code}|{language_code}|safe={int(safe_mode)}|{normalized_name}"

    def read_hit(
        self,
        *,
        store_name: str,
        region_code: str,
        language_code: str,
        safe_mode: bool,
        ttl_seconds: int,
    ) -> tuple[PlaceRecord | None, bool]:
        payload = self.store.read()
        key = self._key(
            store_name=store_name,
            region_code=region_code,
            language_code=language_code,
            safe_mode=safe_mode,
        )
        entry = payload.get(key)
        if not entry:
            return None, False

        now = int(time.time())
        cached_at = int(entry.get("cached_at", 0))
        is_fresh = (now - cached_at) <= ttl_seconds
        record = PlaceRecord(**entry["record"])
        return record, is_fresh

    def write_hit(
        self,
        *,
        store_name: str,
        region_code: str,
        language_code: str,
        safe_mode: bool,
        record: PlaceRecord,
    ) -> None:
        payload = self.store.read()
        key = self._key(
            store_name=store_name,
            region_code=region_code,
            language_code=language_code,
            safe_mode=safe_mode,
        )
        payload[key] = {
            "cached_at": int(time.time()),
            "record": asdict(record),
        }
        self.store.write(payload)


class DailyUsageLimiter:
    def __init__(self, path: str = DEFAULT_USAGE_PATH) -> None:
        self.store = JsonFileStore(path)

    def check_and_consume(self, *, daily_limit: int) -> tuple[bool, int]:
        if daily_limit <= 0:
            raise ValueError("daily_limit must be a positive integer.")
        payload = self.store.read()
        today = date.today().isoformat()
        today_count = int(payload.get(today, 0))
        if today_count >= daily_limit:
            return False, today_count

        today_count += 1
        payload[today] = today_count
        self.store.write(payload)
        return True, today_count


def lookup_place_with_guardrails(
    *,
    parser: GoogleMapsParser,
    store_name: str,
    region_code: str,
    language_code: str,
    safe_mode: bool,
    daily_limit: int,
    cache_ttl_seconds: int,
    cache_path: str = DEFAULT_CACHE_PATH,
    usage_path: str = DEFAULT_USAGE_PATH,
    use_cache: bool = True,
) -> tuple[PlaceRecord, dict]:
    if cache_ttl_seconds < 0:
        raise ValueError("cache_ttl_seconds must be >= 0.")

    cache = PlaceCache(path=cache_path)
    limiter = DailyUsageLimiter(path=usage_path)

    if use_cache:
        cached_record, is_fresh = cache.read_hit(
            store_name=store_name,
            region_code=region_code,
            language_code=language_code,
            safe_mode=safe_mode,
            ttl_seconds=cache_ttl_seconds,
        )
        if cached_record and is_fresh:
            return cached_record, {
                "source": "cache",
                "safe_mode": safe_mode,
                "daily_limit": daily_limit,
                "daily_count": None,
            }

    allowed, daily_count = limiter.check_and_consume(daily_limit=daily_limit)
    if not allowed:
        return fallback_place_record(store_name), {
            "source": "fallback_daily_limit",
            "safe_mode": safe_mode,
            "daily_limit": daily_limit,
            "daily_count": daily_count,
        }

    try:
        record = parser.lookup(
            store_name,
            region_code=region_code,
            language_code=language_code,
            safe_mode=safe_mode,
        )
    except Exception:
        if use_cache:
            cached_record, is_fresh = cache.read_hit(
                store_name=store_name,
                region_code=region_code,
                language_code=language_code,
                safe_mode=safe_mode,
                ttl_seconds=10**9,
            )
            if cached_record and not is_fresh:
                return cached_record, {
                    "source": "stale_cache_on_error",
                    "safe_mode": safe_mode,
                    "daily_limit": daily_limit,
                    "daily_count": daily_count,
                }
        raise

    if use_cache:
        cache.write_hit(
            store_name=store_name,
            region_code=region_code,
            language_code=language_code,
            safe_mode=safe_mode,
            record=record,
        )
    return record, {
        "source": "live_api",
        "safe_mode": safe_mode,
        "daily_limit": daily_limit,
        "daily_count": daily_count,
    }
