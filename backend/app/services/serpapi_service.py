from typing import Any, Dict, Iterable, List, Optional

import httpx

from app.config import get_settings
from app.schemas import Destination, Review
from app.services.rag_service import ServiceConfigurationError
from app.utils.geo import haversine_km
from app.utils.text import normalize_key


class SerpApiService:
    """Real web-search, photo and review retrieval through SerpApi."""

    BASE_URL = "https://serpapi.com/search.json"

    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.serpapi_api_key:
            raise ServiceConfigurationError(
                "SERPAPI_API_KEY is missing. Real web search, photos and reviews require SerpApi."
            )

    def build_queries(self, extracted: Dict[str, Any]) -> List[str]:
        start = extracted.get("start_location")
        max_distance = extracted.get("max_distance_km")
        max_time = extracted.get("max_travel_time_minutes")
        preferences = extracted.get("preferences") or []
        avoided_transport = extracted.get("avoided_transport") or []
        preferred_transport = extracted.get("preferred_transport")
        duration = extracted.get("trip_duration")

        preference_text = " ".join(preferences) if preferences else "places to visit"
        distance_text = f"within {max_distance:g} km" if max_distance else ""
        time_text = f"within {max_time} minutes" if max_time else ""
        transport_text = ""
        if preferred_transport:
            transport_text = f"by {preferred_transport}"
        elif "car" in avoided_transport:
            transport_text = "reachable by train or public transport"

        queries = [
            " ".join(part for part in [preference_text, "near", start, distance_text, time_text, transport_text] if part),
            " ".join(part for part in ["best day trips from", start, distance_text, time_text, transport_text] if part),
            " ".join(part for part in ["interesting places around", start, duration or "", transport_text] if part),
        ]
        return list(dict.fromkeys(query.strip() for query in queries if query.strip()))

    def geocode_place(self, place_name: str) -> Optional[Dict[str, float]]:
        data = self._get(
            {
                "engine": "google_maps",
                "q": place_name,
                "type": "search",
                "hl": self.settings.serpapi_hl,
                "gl": self.settings.serpapi_gl,
            }
        )
        for item in self._iter_map_items(data):
            coords = item.get("gps_coordinates") or {}
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            if lat is not None and lon is not None:
                return {"latitude": float(lat), "longitude": float(lon)}
        return None

    def search_destinations(self, extracted: Dict[str, Any], existing: List[Destination]) -> List[Destination]:
        origin_coords = None
        if extracted.get("start_location"):
            origin_coords = self.geocode_place(extracted["start_location"])

        max_distance_km = extracted.get("max_distance_km")
        seen = {normalize_key(destination.name) for destination in existing}
        candidates: List[Destination] = []

        for query in self.build_queries(extracted):
            data = self._get(
                {
                    "engine": "google_maps",
                    "q": query,
                    "type": "search",
                    "hl": self.settings.serpapi_hl,
                    "gl": self.settings.serpapi_gl,
                }
            )
            for item in self._iter_map_items(data):
                destination = self._map_item_to_destination(item, origin_coords)
                if not destination:
                    continue
                if max_distance_km and destination.distance_km and destination.distance_km > max_distance_km:
                    continue
                key = normalize_key(destination.name)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(destination)

                # Keep searching enough to survive enrichment filtering, but avoid excessive API calls.
                if len(candidates) >= self.settings.min_results * 3:
                    return candidates

        # If Google Maps is too sparse, use regular Google organic results from the same real web provider.
        if len(candidates) < self.settings.min_results:
            for query in self.build_queries(extracted):
                data = self._get(
                    {
                        "engine": "google",
                        "q": query,
                        "hl": self.settings.serpapi_hl,
                        "gl": self.settings.serpapi_gl,
                        "num": 10,
                    }
                )
                for item in data.get("organic_results", []) or []:
                    title = item.get("title")
                    link = item.get("link")
                    if not title or not link:
                        continue
                    key = normalize_key(title)
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(
                        Destination(
                            name=title,
                            description=item.get("snippet"),
                            source="web",
                            url=link,
                            evidence_urls=[link],
                        )
                    )
                    if len(candidates) >= self.settings.min_results * 3:
                        return candidates
        return candidates

    def enrich(self, destination: Destination, start_location: Optional[str]) -> Optional[Destination]:
        """Attach real web photo and reviews. Returns None if required evidence is missing."""
        enriched = destination.model_copy(deep=True)

        if not enriched.photo_url:
            enriched.photo_url = self.find_photo(enriched.name, start_location)

        web_reviews = self.find_reviews(enriched)
        existing_reviews = enriched.reviews or []
        # Keep local RAG review and append real web reviews.
        enriched.reviews = [*existing_reviews, *web_reviews]

        if not enriched.photo_url:
            return None
        # Each returned card must have at least one review retrieved from the web.
        # Local RAG reviews are kept as evidence, but they are not enough by themselves.
        if len(web_reviews) == 0:
            return None

        if destination.source == "rag" and (web_reviews or enriched.photo_url):
            enriched.source = "rag+web"
        return enriched

    def find_photo(self, name: str, start_location: Optional[str]) -> Optional[str]:
        query = " ".join(part for part in [name, start_location or "", "photo"] if part)
        data = self._get(
            {
                "engine": "google_images",
                "q": query,
                "hl": self.settings.serpapi_hl,
                "gl": self.settings.serpapi_gl,
            }
        )
        for image in data.get("images_results", []) or []:
            return image.get("original") or image.get("thumbnail")
        return None

    def find_reviews(self, destination: Destination) -> List[Review]:
        reviews: List[Review] = []

        data_id = _extract_data_id(destination.evidence_urls)
        if data_id:
            data = self._get(
                {
                    "engine": "google_maps_reviews",
                    "data_id": data_id,
                    "hl": self.settings.serpapi_hl,
                }
            )
            for item in data.get("reviews", []) or []:
                text = item.get("snippet") or item.get("extracted_snippet", {}).get("original")
                if not text:
                    continue
                reviews.append(
                    Review(
                        text=text,
                        author=item.get("user", {}).get("name"),
                        rating=_safe_float(item.get("rating")),
                        url=item.get("link"),
                        source="google_maps_reviews",
                    )
                )
                if len(reviews) >= 3:
                    return reviews

        # Use regular Google results from the real web provider when Maps reviews are unavailable.
        data = self._get(
            {
                "engine": "google",
                "q": f"{destination.name} reviews",
                "hl": self.settings.serpapi_hl,
                "gl": self.settings.serpapi_gl,
                "num": 5,
            }
        )
        for item in data.get("organic_results", []) or []:
            snippet = item.get("snippet")
            link = item.get("link")
            if not snippet:
                continue
            reviews.append(
                Review(
                    text=snippet,
                    author=item.get("source"),
                    url=link,
                    source="web_search_review_snippet",
                )
            )
            if len(reviews) >= 3:
                break
        return reviews

    def _map_item_to_destination(
        self,
        item: Dict[str, Any],
        origin_coords: Optional[Dict[str, float]],
    ) -> Optional[Destination]:
        name = item.get("title")
        if not name:
            return None

        coords = item.get("gps_coordinates") or {}
        lat = _safe_float(coords.get("latitude"))
        lon = _safe_float(coords.get("longitude"))
        distance_km = None
        if origin_coords and lat is not None and lon is not None:
            distance_km = haversine_km(origin_coords.get("latitude"), origin_coords.get("longitude"), lat, lon)

        evidence_urls = []
        if item.get("place_id_search"):
            evidence_urls.append(item["place_id_search"])
        if item.get("data_id"):
            evidence_urls.append(f"serpapi:data_id:{item['data_id']}")
        website = (item.get("links") or {}).get("website") or item.get("website")
        if website:
            evidence_urls.append(website)

        return Destination(
            name=name,
            description=item.get("description") or item.get("snippet") or item.get("type"),
            source="web",
            address=item.get("address"),
            url=website or item.get("place_id_search"),
            photo_url=item.get("thumbnail"),
            rating=_safe_float(item.get("rating")),
            review_count=_safe_int(item.get("reviews")),
            latitude=lat,
            longitude=lon,
            distance_km=round(distance_km, 1) if distance_km is not None else None,
            evidence_urls=evidence_urls,
        )

    def _iter_map_items(self, data: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        place = data.get("place_results")
        if isinstance(place, dict):
            yield place
        for item in data.get("local_results", []) or []:
            yield item

    def _get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params = {**params, "api_key": self.settings.serpapi_api_key}
        with httpx.Client(timeout=self.settings.serpapi_timeout_seconds) as client:
            response = client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise RuntimeError(f"SerpApi error: {data['error']}")
            return data


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _extract_data_id(evidence_urls: List[str]) -> Optional[str]:
    for url in evidence_urls:
        if url.startswith("serpapi:data_id:"):
            return url.replace("serpapi:data_id:", "", 1)
    return None
