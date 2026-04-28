from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.agent_orchestrator import FoodieAgentOrchestrator
from tools.google_maps_parser import PlaceRecord, PlaceSearchRecord, ReviewRecord
from tools.intent_parser import IntentParserSkill


class _FakeMapsParser:
    def search_places(
        self,
        text_query: str,
        *,
        region_code: str = "TW",
        language_code: str = "zh-TW",
        safe_mode: bool = True,
        max_results: int = 10,
    ) -> list[PlaceSearchRecord]:
        _ = (text_query, region_code, language_code, safe_mode, max_results)
        return [
            PlaceSearchRecord(
                place_id="p1",
                name="韓味豆腐鍋",
                rating=4.5,
                address="台北市大安區 A 路",
                lat=25.0419,
                lng=121.5434,
                user_rating_count=1200,
            ),
            PlaceSearchRecord(
                place_id="p2",
                name="韓式小館",
                rating=4.2,
                address="台北市大安區 B 路",
                lat=25.0422,
                lng=121.5440,
                user_rating_count=350,
            ),
        ]

    def get_place_details_with_reviews(
        self,
        place_id: str,
        *,
        language_code: str = "zh-TW",
        max_reviews: int = 5,
    ) -> tuple[PlaceRecord, list[ReviewRecord]]:
        _ = (language_code, max_reviews)
        if place_id == "p1":
            return (
                PlaceRecord(
                    name="韓味豆腐鍋",
                    rating=4.6,
                    address="台北市大安區 A 路",
                    lat=25.0419,
                    lng=121.5434,
                    user_rating_count=1300,
                ),
                [
                    ReviewRecord(
                        author_name="A",
                        rating=5,
                        text="豆腐鍋很濃郁，會再來",
                        relative_publish_time="1 個月前",
                        publish_time=None,
                        google_maps_uri=None,
                    )
                ],
            )
        return (
            PlaceRecord(
                name="韓式小館",
                rating=4.1,
                address="台北市大安區 B 路",
                lat=25.0422,
                lng=121.5440,
                user_rating_count=350,
            ),
            [
                ReviewRecord(
                    author_name="B",
                    rating=4,
                    text="要排隊，但平價",
                    relative_publish_time="2 個月前",
                    publish_time=None,
                    google_maps_uri=None,
                )
            ],
        )


class AgentOrchestratorTests(unittest.TestCase):
    def test_intent_parser_extracts_key_constraints(self) -> None:
        intent = IntentParserSkill().run(query="走路 20 分鐘內，韓式，評價高，有豆腐鍋")
        self.assertEqual(intent.max_walk_minutes, 20)
        self.assertEqual(intent.cuisine, "韓式")
        self.assertEqual(intent.must_have, "豆腐鍋")
        self.assertTrue(intent.needs_high_rating)

    def test_orchestrator_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            social_path = Path(tmp) / "social.txt"
            social_path.write_text("韓味豆腐鍋|裝潢好拍，排隊但值得\n", encoding="utf-8")

            orchestrator = FoodieAgentOrchestrator(maps_parser=_FakeMapsParser())
            result = orchestrator.run(
                query="走路 20 分鐘內，韓式，評價高，有豆腐鍋",
                user_lat=25.042,
                user_lng=121.543,
                social_file=str(social_path),
                daily_limit=20,
                top_k=2,
                usage_path=str(Path(tmp) / "usage.json"),
                cache_path=str(Path(tmp) / "cache.json"),
            )

            self.assertIn("intent", result)
            self.assertIn("recommendations", result)
            self.assertGreaterEqual(len(result["recommendations"]), 1)
            top = result["recommendations"][0]
            self.assertEqual(top["name"], "韓味豆腐鍋")
            self.assertTrue(len(top["vibe_tags"]) > 0)


if __name__ == "__main__":
    unittest.main()
