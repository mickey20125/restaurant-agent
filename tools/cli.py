from __future__ import annotations

import argparse
import json
import os
import sys

from tools.agent_orchestrator import FoodieAgentOrchestrator
from tools.env_loader import load_local_env
from tools.expert_prompt import render_expert_prompt
from tools.google_maps_parser import GoogleMapsParser, mock_lookup
from tools.maps_guardrails import (
    DEFAULT_CACHE_PATH,
    DEFAULT_USAGE_PATH,
    lookup_place_with_guardrails,
)
from tools.vibe_summarizer import summarize_vibes


def _cmd_maps(args: argparse.Namespace) -> int:
    if args.mock:
        record = mock_lookup(args.name)
        meta = {"source": "mock", "safe_mode": False}
    else:
        parser = GoogleMapsParser(api_key=args.api_key)
        record, meta = lookup_place_with_guardrails(
            parser=parser,
            store_name=args.name,
            region_code=args.region,
            language_code=args.language,
            safe_mode=args.safe_mode,
            daily_limit=args.daily_limit,
            cache_ttl_seconds=args.cache_ttl_seconds,
            cache_path=args.cache_path,
            usage_path=args.usage_path,
            use_cache=(not args.no_cache),
        )

    if meta["source"] == "fallback_daily_limit":
        print(
            f"Daily API limit reached ({meta.get('daily_count')}/{meta.get('daily_limit')}). "
            "Return fallback result without calling Google API.",
            file=sys.stderr,
        )
    elif meta["source"] == "cache":
        print("Cache hit: return cached result without calling Google API.", file=sys.stderr)
    elif meta["source"] == "stale_cache_on_error":
        print("API request failed. Returning stale cached result.", file=sys.stderr)

    response = record.__dict__.copy()
    if args.show_meta:
        response["_meta"] = meta
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0


def _cmd_vibe(args: argparse.Namespace) -> int:
    posts: list[str] = []
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            posts.extend([line.strip() for line in f.readlines() if line.strip()])
    posts.extend(args.text)
    if not posts:
        print("No input text found. Use --text or --file.", file=sys.stderr)
        return 1

    result = summarize_vibes(posts, top_k=args.top_k)
    print(json.dumps({"tags": result}, ensure_ascii=False, indent=2))
    return 0


def _cmd_reviews(args: argparse.Namespace) -> int:
    parser = GoogleMapsParser(api_key=args.api_key)
    place, reviews = parser.lookup_reviews(
        args.name,
        region_code=args.region,
        language_code=args.language,
        max_reviews=args.max_reviews,
    )
    payload = {
        "place": place.__dict__,
        "reviews": GoogleMapsParser.reviews_to_dict(reviews),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_prompt(args: argparse.Namespace) -> int:
    prompt = render_expert_prompt(
        non_engineer_logic=args.logic,
        user_query=args.query,
        max_walk_minutes=args.max_walk_minutes,
        must_have=args.must_have,
    )
    print(prompt)
    return 0


def _cmd_agent(args: argparse.Namespace) -> int:
    from tools.types import Recommendation as Rec
    orchestrator = FoodieAgentOrchestrator()
    payload = orchestrator.run(
        query=args.query,
        non_engineer_logic=args.logic,
        user_lat=args.user_lat,
        user_lng=args.user_lng,
        region_code=args.region,
        language_code=args.language,
        safe_mode=args.safe_mode,
        candidate_limit=args.candidate_limit,
        top_k=args.top_k,
        max_reviews_per_place=args.max_reviews_per_place,
        social_file=args.social_file,
        inline_social_posts=args.social_text,
        daily_limit=args.daily_limit,
        usage_path=args.usage_path,
        cache_path=args.cache_path,
        disable_instagram=args.no_instagram,
        ig_max_posts=args.ig_max_posts,
        ig_daily_limit=args.ig_daily_limit,
        ig_cache_ttl_seconds=args.ig_cache_ttl_seconds,
        disable_threads=args.no_threads,
        threads_max_posts=args.threads_max_posts,
        threads_daily_limit=args.threads_daily_limit,
        threads_cache_ttl_seconds=args.threads_cache_ttl_seconds,
    )
    if not args.show_debug:
        payload.pop("debug", None)

    if args.markdown:
        recs = payload.get("recommendations", [])
        if not recs:
            print("（無符合條件的推薦結果）")
            return 0
        for item in recs:
            rec = Rec(**{k: item[k] for k in Rec.__dataclass_fields__ if k in item})
            print(rec.to_markdown())
            print()
        return 0

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Restaurant agent toolchain scaffold.")
    sub = parser.add_subparsers(dest="command", required=True)

    maps = sub.add_parser("maps", help="Lookup place info by store name.")
    maps.add_argument("--name", required=True, help="Restaurant/store name.")
    maps.add_argument("--region", default="TW", help="Region code, default: TW")
    maps.add_argument("--language", default="zh-TW", help="Language code, default: zh-TW")
    maps.add_argument("--api-key", help="Google Maps API key. Overrides GOOGLE_MAPS_API_KEY.")
    maps.add_argument("--safe-mode", action="store_true", help="Use low-cost field mask (no rating fields).")
    maps.add_argument(
        "--daily-limit",
        type=int,
        default=int(os.environ.get("MAPS_DAILY_CALL_LIMIT", "100")),
        help="Max live Google API calls per day. Default from MAPS_DAILY_CALL_LIMIT or 100.",
    )
    maps.add_argument(
        "--cache-ttl-seconds",
        type=int,
        default=int(os.environ.get("MAPS_CACHE_TTL_SECONDS", "86400")),
        help="Cache TTL in seconds. Default from MAPS_CACHE_TTL_SECONDS or 86400.",
    )
    maps.add_argument("--cache-path", default=DEFAULT_CACHE_PATH)
    maps.add_argument("--usage-path", default=DEFAULT_USAGE_PATH)
    maps.add_argument("--no-cache", action="store_true", help="Disable local cache.")
    maps.add_argument("--show-meta", action="store_true", help="Include source/guardrail metadata in output.")
    maps.add_argument("--mock", action="store_true", help="Use built-in mock response.")
    maps.set_defaults(func=_cmd_maps)

    vibe = sub.add_parser("vibe", help="Summarize social text into vibe tags.")
    vibe.add_argument("--text", action="append", default=[], help="One text snippet. Can be repeated.")
    vibe.add_argument("--file", help="UTF-8 text file, one post per line.")
    vibe.add_argument("--top-k", type=int, default=3, help="Number of tags to output.")
    vibe.set_defaults(func=_cmd_vibe)

    reviews = sub.add_parser("reviews", help="Lookup Google Maps reviews by store name.")
    reviews.add_argument("--name", required=True, help="Restaurant/store name.")
    reviews.add_argument("--region", default="TW", help="Region code, default: TW")
    reviews.add_argument("--language", default="zh-TW", help="Language code, default: zh-TW")
    reviews.add_argument("--api-key", help="Google Maps API key. Overrides GOOGLE_MAPS_API_KEY.")
    reviews.add_argument("--max-reviews", type=int, default=5, help="Maximum reviews to return.")
    reviews.set_defaults(func=_cmd_reviews)

    prompt = sub.add_parser("prompt", help="Render expert prompt template.")
    prompt.add_argument("--logic", required=True, help="Logic defined by the non-engineer teammate.")
    prompt.add_argument("--query", required=True, help="User request.")
    prompt.add_argument("--max-walk-minutes", type=int, default=20)
    prompt.add_argument("--must-have", default="豆腐鍋")
    prompt.set_defaults(func=_cmd_prompt)

    agent = sub.add_parser("agent", help="Run full skill pipeline for food recommendations.")
    agent.add_argument("--query", required=True, help="User natural-language request.")
    agent.add_argument("--logic", default="", help="Non-engineer teammate logic constraints.")
    agent.add_argument("--region", default="TW", help="Region code, default: TW")
    agent.add_argument("--language", default="zh-TW", help="Language code, default: zh-TW")
    agent.add_argument(
        "--user-lat",
        type=float,
        default=float(os.environ.get("DEFAULT_USER_LAT", "0") or "0") or None,
        help="User latitude. Default from DEFAULT_USER_LAT in .env.",
    )
    agent.add_argument(
        "--user-lng",
        type=float,
        default=float(os.environ.get("DEFAULT_USER_LNG", "0") or "0") or None,
        help="User longitude. Default from DEFAULT_USER_LNG in .env.",
    )
    agent.add_argument("--candidate-limit", type=int, default=8, help="Max candidates from search stage.")
    agent.add_argument("--top-k", type=int, default=3, help="Final recommendation count.")
    agent.add_argument("--max-reviews-per-place", type=int, default=3, help="Max reviews fetched per place.")
    agent.add_argument("--social-file", help="Optional local IG/Threads text file.")
    agent.add_argument("--social-text", action="append", default=[], help="Inline social snippet. Can be repeated.")
    agent.add_argument(
        "--daily-limit",
        type=int,
        default=int(os.environ.get("MAPS_DAILY_CALL_LIMIT", "100")),
    )
    agent.add_argument(
        "--usage-path",
        default=os.environ.get("AGENT_DAILY_USAGE_PATH", ".cache/agent_daily_usage.json"),
    )
    agent.add_argument(
        "--cache-path",
        default=os.environ.get("AGENT_SKILL_CACHE_PATH", ".cache/agent_skill_cache.json"),
    )
    agent.add_argument("--safe-mode", dest="safe_mode", action="store_true")
    agent.add_argument("--no-safe-mode", dest="safe_mode", action="store_false")
    agent.set_defaults(safe_mode=True)
    agent.add_argument("--show-debug", action="store_true", help="Include skill-level debug output.")
    agent.add_argument("--markdown", action="store_true", help="Output formatted markdown instead of JSON.")
    agent.add_argument("--no-instagram", action="store_true", help="Disable Instagram fetching even if credentials are set.")
    agent.add_argument("--ig-max-posts", type=int, default=10, help="Max IG posts to fetch per candidate.")
    agent.add_argument(
        "--ig-daily-limit",
        type=int,
        default=int(os.environ.get("IG_DAILY_CALL_LIMIT", "100")),
        help="Daily Instagram API call budget. Default from IG_DAILY_CALL_LIMIT or 100.",
    )
    agent.add_argument(
        "--ig-cache-ttl-seconds",
        type=int,
        default=int(os.environ.get("IG_CACHE_TTL_SECONDS", "3600")),
        help="Instagram cache TTL in seconds. Default from IG_CACHE_TTL_SECONDS or 3600.",
    )
    agent.add_argument("--no-threads", action="store_true", help="Disable Threads.net scraping.")
    agent.add_argument("--threads-max-posts", type=int, default=10, help="Max Threads posts to fetch per candidate.")
    agent.add_argument(
        "--threads-daily-limit",
        type=int,
        default=int(os.environ.get("THREADS_DAILY_CALL_LIMIT", "50")),
        help="Daily Threads scrape budget. Default from THREADS_DAILY_CALL_LIMIT or 50.",
    )
    agent.add_argument(
        "--threads-cache-ttl-seconds",
        type=int,
        default=int(os.environ.get("THREADS_CACHE_TTL_SECONDS", "3600")),
        help="Threads cache TTL in seconds. Default from THREADS_CACHE_TTL_SECONDS or 3600.",
    )
    agent.set_defaults(func=_cmd_agent)

    return parser


def main() -> int:
    load_local_env()
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
