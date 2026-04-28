import unittest

from tools.google_maps_parser import GoogleMapsParser


class GoogleMapsReviewsTests(unittest.TestCase):
    def test_parse_reviews_respects_max_reviews(self) -> None:
        payload = {
            "reviews": [
                {
                    "rating": 5,
                    "relativePublishTimeDescription": "1 個月前",
                    "publishTime": "2026-04-01T00:00:00Z",
                    "googleMapsUri": "https://maps.google.com/review/1",
                    "authorAttribution": {"displayName": "Alice"},
                    "text": {"text": "豆腐鍋很順口，會再來"},
                },
                {
                    "rating": 4,
                    "relativePublishTimeDescription": "2 個月前",
                    "publishTime": "2026-03-01T00:00:00Z",
                    "googleMapsUri": "https://maps.google.com/review/2",
                    "authorAttribution": {"displayName": "Bob"},
                    "text": {"text": "平價但要排隊"},
                },
            ]
        }
        reviews = GoogleMapsParser.parse_reviews(payload, max_reviews=1)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].author_name, "Alice")
        self.assertEqual(reviews[0].rating, 5)
        self.assertIn("豆腐鍋", reviews[0].text or "")


if __name__ == "__main__":
    unittest.main()
