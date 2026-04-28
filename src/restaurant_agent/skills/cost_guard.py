from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Any


class CostGuardSkill:
    def __init__(
        self,
        *,
        daily_limit: int,
        usage_path: str = ".cache/agent_daily_usage.json",
        cache_path: str = ".cache/agent_skill_cache.json",
    ) -> None:
        if daily_limit <= 0:
            raise ValueError("daily_limit must be positive.")
        self.daily_limit = daily_limit
        self.usage_path = Path(usage_path)
        self.cache_path = Path(cache_path)

    def allow_api_calls(self, units: int = 1) -> tuple[bool, dict[str, int]]:
        if units <= 0:
            raise ValueError("units must be positive.")
        usage = self._read_json(self.usage_path)
        today = date.today().isoformat()
        current = int(usage.get(today, 0))
        if current + units > self.daily_limit:
            return False, {"daily_count": current, "daily_limit": self.daily_limit}
        usage[today] = current + units
        self._write_json(self.usage_path, usage)
        return True, {"daily_count": current + units, "daily_limit": self.daily_limit}

    def get_cached(self, *, namespace: str, key: str, ttl_seconds: int) -> dict[str, Any] | None:
        if ttl_seconds < 0:
            raise ValueError("ttl_seconds must be >= 0.")
        payload = self._read_json(self.cache_path)
        ns = payload.get(namespace) or {}
        item = ns.get(key)
        if not item:
            return None
        if (int(time.time()) - int(item.get("cached_at", 0))) > ttl_seconds:
            return None
        return item.get("data")

    def put_cached(self, *, namespace: str, key: str, data: dict[str, Any]) -> None:
        payload = self._read_json(self.cache_path)
        ns = payload.get(namespace) or {}
        ns[key] = {
            "cached_at": int(time.time()),
            "data": data,
        }
        payload[namespace] = ns
        self._write_json(self.cache_path, payload)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

