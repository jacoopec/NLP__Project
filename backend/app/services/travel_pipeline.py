from typing import Dict, List

from app.schemas import Destination, ExtractedTravelInfo
from app.utils.text import normalize_key


def build_rag_query(extracted: ExtractedTravelInfo) -> str:
    pieces = [
        extracted.cleaned_text,
        " ".join(extracted.preferences),
        " ".join(extracted.avoid_terms),
        extracted.trip_duration or "",
        extracted.preferred_transport or "",
        " ".join(f"avoid {item}" for item in extracted.avoided_transport),
    ]
    return " ".join(piece for piece in pieces if piece).strip()


def missing_required_fields(extracted: ExtractedTravelInfo) -> List[str]:
    missing: List[str] = []
    if not extracted.start_location:
        missing.append("start_location")
    if extracted.max_distance_km is None and extracted.max_travel_time_minutes is None:
        missing.append("max_distance_or_travel_time")
    return missing


def validation_messages(missing: List[str]) -> List[str]:
    messages = []
    if "start_location" in missing:
        messages.append("Please tell me your starting location, for example 'I leave from Bologna'.")
    if "max_distance_or_travel_time" in missing:
        messages.append("Please tell me how far you are willing to go, for example '80 km' or '2 hours'.")
    return messages


def merge_destinations(primary: List[Destination], secondary: List[Destination]) -> List[Destination]:
    out: List[Destination] = []
    index: Dict[str, Destination] = {}

    for destination in [*primary, *secondary]:
        key = normalize_key(destination.name)
        if not key:
            continue
        if key not in index:
            index[key] = destination
            out.append(destination)
            continue

        existing = index[key]
        if existing.source == "rag" and destination.source == "web":
            existing.source = "rag+web"
        existing.photo_url = existing.photo_url or destination.photo_url
        existing.address = existing.address or destination.address
        existing.url = existing.url or destination.url
        existing.rating = existing.rating or destination.rating
        existing.review_count = existing.review_count or destination.review_count
        existing.latitude = existing.latitude or destination.latitude
        existing.longitude = existing.longitude or destination.longitude
        existing.distance_km = existing.distance_km or destination.distance_km
        existing.evidence_urls = list(dict.fromkeys([*existing.evidence_urls, *destination.evidence_urls]))
        existing.reviews = [*existing.reviews, *destination.reviews]

    return out
