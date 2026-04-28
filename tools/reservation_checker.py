from __future__ import annotations

import re

from tools.types import Candidate

# Known Taiwanese / international reservation platforms, checked in order.
# First match wins and is used as reservation_url.
_BOOKING_PLATFORMS: list[tuple[str, str]] = [
    ("inline.app", "Inline"),
    ("eztable.com.tw", "EZTable"),
    ("ichoose.com.tw", "iCHEF Reserve"),
    ("opentable.com", "OpenTable"),
    ("tablecheck.com", "TableCheck"),
    ("jresv.com", "J-Resv"),
]

# Phone number pattern for Taiwan (landline + mobile)
_TW_PHONE_RE = re.compile(r"(\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4})")


class ReservationCheckerSkill:
    """Enrich candidates with reservation URL and phone number.

    Uses the website and phone already fetched by ReviewFetcherSkill.
    Checks the website against known booking platforms; if the website
    itself is a booking page, that URL is used directly. Otherwise falls
    back to the Google Places phone number.
    """

    def run(self, *, candidates: list[Candidate]) -> tuple[list[Candidate], dict]:
        reservable_count = 0
        has_booking_url = 0
        has_phone_only = 0

        for candidate in candidates:
            booking_url = self._extract_booking_url(candidate.website)

            if booking_url:
                candidate.reservation_url = booking_url
                has_booking_url += 1
            elif candidate.reservable and candidate.website:
                # reservable=True but website isn't a known platform → use website as-is
                candidate.reservation_url = candidate.website
                has_booking_url += 1
            elif candidate.phone:
                has_phone_only += 1

            if candidate.reservable or candidate.reservation_url or candidate.phone:
                reservable_count += 1

        return candidates, {
            "reservable_count": reservable_count,
            "has_booking_url": has_booking_url,
            "has_phone_only": has_phone_only,
        }

    @staticmethod
    def _extract_booking_url(website: str | None) -> str | None:
        if not website:
            return None
        for domain, _ in _BOOKING_PLATFORMS:
            if domain in website:
                return website
        return None
