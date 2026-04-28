from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GOOGLE_PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FULL_FIELD_MASK = "places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount"
SAFE_FIELD_MASK = "places.displayName,places.formattedAddress,places.location"
GOOGLE_PLACES_DETAILS_URL_TEMPLATE = "https://places.googleapis.com/v1/places/{place_id}"


@dataclass
class PlaceRecord:
    name: str
    rating: float | None
    address: str | None
    lat: float | None
    lng: float | None
    user_rating_count: int | None


@dataclass
class PlaceSearchRecord:
    place_id: str
    name: str
    rating: float | None
    address: str | None
    lat: float | None
    lng: float | None
    user_rating_count: int | None


@dataclass
class ReviewRecord:
    author_name: str | None
    rating: float | None
    text: str | None
    relative_publish_time: str | None
    publish_time: str | None
    google_maps_uri: str | None


class GoogleMapsParser:
    """Resolve restaurant names to a normalized place record."""

    def __init__(self, api_key: str | None = None, timeout_seconds: int = 10) -> None:
        self.api_key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY")
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def field_mask(*, safe_mode: bool) -> str:
        if safe_mode:
            return SAFE_FIELD_MASK
        return FULL_FIELD_MASK

    @staticmethod
    def search_field_mask(*, safe_mode: bool) -> str:
        return f"places.id,{GoogleMapsParser.field_mask(safe_mode=safe_mode)}"

    def _request_json(self, *, url: str, method: str, headers: dict[str, str], payload: dict | None = None) -> dict:
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, method=method, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Google Places API error: {exc.code} {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Network error while calling Google Places API: {exc.reason}") from exc
        return json.loads(raw)

    @staticmethod
    def parse_reviews(payload: dict, *, max_reviews: int) -> list[ReviewRecord]:
        reviews = payload.get("reviews") or []
        result: list[ReviewRecord] = []
        for review in reviews[:max_reviews]:
            result.append(
                ReviewRecord(
                    author_name=((review.get("authorAttribution") or {}).get("displayName")),
                    rating=review.get("rating"),
                    text=((review.get("text") or {}).get("text")),
                    relative_publish_time=review.get("relativePublishTimeDescription"),
                    publish_time=review.get("publishTime"),
                    google_maps_uri=review.get("googleMapsUri"),
                )
            )
        return result

    @staticmethod
    def _place_from_payload(payload: dict, fallback_name: str) -> PlaceRecord:
        return PlaceRecord(
            name=((payload.get("displayName") or {}).get("text")) or fallback_name,
            rating=payload.get("rating"),
            address=payload.get("formattedAddress"),
            lat=((payload.get("location") or {}).get("latitude")),
            lng=((payload.get("location") or {}).get("longitude")),
            user_rating_count=payload.get("userRatingCount"),
        )

    @staticmethod
    def _search_record_from_payload(payload: dict, fallback_name: str) -> PlaceSearchRecord:
        place_id = payload.get("id")
        if not place_id:
            raise LookupError(f"No place_id found for: {fallback_name}")
        place = GoogleMapsParser._place_from_payload(payload, fallback_name=fallback_name)
        return PlaceSearchRecord(
            place_id=place_id,
            name=place.name,
            rating=place.rating,
            address=place.address,
            lat=place.lat,
            lng=place.lng,
            user_rating_count=place.user_rating_count,
        )

    def search_places(
        self,
        text_query: str,
        *,
        region_code: str = "TW",
        language_code: str = "zh-TW",
        safe_mode: bool = True,
        max_results: int = 10,
    ) -> list[PlaceSearchRecord]:
        if max_results <= 0:
            raise ValueError("max_results must be > 0.")
        if not self.api_key:
            raise ValueError("Missing Google Maps API key. Set GOOGLE_MAPS_API_KEY first.")

        payload = {
            "textQuery": text_query,
            "languageCode": language_code,
            "regionCode": region_code,
        }
        parsed = self._request_json(
            url=GOOGLE_PLACES_TEXT_SEARCH_URL,
            method="POST",
            payload=payload,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": self.search_field_mask(safe_mode=safe_mode),
            },
        )
        places = parsed.get("places") or []
        if not places:
            return []
        return [self._search_record_from_payload(item, fallback_name=text_query) for item in places[:max_results]]

    def get_place_details_with_reviews(
        self,
        place_id: str,
        *,
        language_code: str = "zh-TW",
        max_reviews: int = 5,
    ) -> tuple[PlaceRecord, list[ReviewRecord]]:
        if max_reviews <= 0:
            raise ValueError("max_reviews must be > 0.")
        if not self.api_key:
            raise ValueError("Missing Google Maps API key. Set GOOGLE_MAPS_API_KEY first.")

        details_payload = self._request_json(
            url=GOOGLE_PLACES_DETAILS_URL_TEMPLATE.format(place_id=place_id),
            method="GET",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": (
                    "id,displayName,formattedAddress,location,rating,userRatingCount,reviews"
                ),
                "Accept-Language": language_code,
            },
        )
        return (
            self._place_from_payload(details_payload, fallback_name=place_id),
            self.parse_reviews(details_payload, max_reviews=max_reviews),
        )

    def lookup_reviews(
        self,
        store_name: str,
        *,
        region_code: str = "TW",
        language_code: str = "zh-TW",
        max_reviews: int = 5,
    ) -> tuple[PlaceRecord, list[ReviewRecord]]:
        if max_reviews <= 0:
            raise ValueError("max_reviews must be > 0.")
        search_result = self.search_places(
            store_name,
            region_code=region_code,
            language_code=language_code,
            safe_mode=True,
            max_results=1,
        )
        if not search_result:
            raise LookupError(f"No place found for: {store_name}")
        top = search_result[0]
        place, reviews = self.get_place_details_with_reviews(
            top.place_id,
            language_code=language_code,
            max_reviews=max_reviews,
        )
        return place, reviews

    def lookup(
        self,
        store_name: str,
        *,
        region_code: str = "TW",
        language_code: str = "zh-TW",
        safe_mode: bool = False,
    ) -> PlaceRecord:
        if not self.api_key:
            raise ValueError("Missing Google Maps API key. Set GOOGLE_MAPS_API_KEY first.")

        search_result = self.search_places(
            store_name,
            region_code=region_code,
            language_code=language_code,
            safe_mode=safe_mode,
            max_results=1,
        )
        if not search_result:
            raise LookupError(f"No place found for: {store_name}")

        first = search_result[0]
        return PlaceRecord(
            name=first.name,
            rating=first.rating,
            address=first.address,
            lat=first.lat,
            lng=first.lng,
            user_rating_count=first.user_rating_count,
        )

    @staticmethod
    def to_dict(record: PlaceRecord) -> dict[str, Any]:
        return asdict(record)

    @staticmethod
    def reviews_to_dict(reviews: list[ReviewRecord]) -> list[dict[str, Any]]:
        return [asdict(review) for review in reviews]

    @staticmethod
    def search_records_to_dict(records: list[PlaceSearchRecord]) -> list[dict[str, Any]]:
        return [asdict(record) for record in records]


def mock_lookup(store_name: str) -> PlaceRecord:
    return PlaceRecord(
        name=store_name,
        rating=4.6,
        address="台北市大安區復興南路一段 000 號",
        lat=25.0419,
        lng=121.5434,
        user_rating_count=1320,
    )
