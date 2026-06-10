import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import spacy

from app.config import get_settings
from app.schemas import ExtractedTravelInfo
from app.utils.text import clean_user_text, dedupe_keep_order


@dataclass(frozen=True)
class PreferenceRule:
    label: str
    patterns: tuple[str, ...]


PREFERENCE_RULES = [
    PreferenceRule("lakes", ("lake", "lakes", "lago", "laghi")),
    PreferenceRule("beaches", ("beach", "beaches", "sea", "seaside", "mare", "spiaggia", "spiagge")),
    PreferenceRule("hikes", ("hike", "hikes", "hiking", "trekking", "walk", "walking", "sentiero", "camminata")),
    PreferenceRule("waterfalls", ("waterfall", "waterfalls", "cascata", "cascate")),
    PreferenceRule("castles", ("castle", "castles", "castello", "castelli")),
    PreferenceRule("historic villages", ("borgo", "borghi", "village", "villages", "medieval")),
    PreferenceRule("mountains", ("mountain", "mountains", "montagna", "appennino", "alps")),
    PreferenceRule("food", ("food", "wine", "restaurant", "restaurants", "cibo", "vino", "osteria")),
    PreferenceRule("museums", ("museum", "museums", "museo", "gallery", "galleria")),
    PreferenceRule("nature", ("nature", "natural", "woods", "forest", "park", "parco", "bosco")),
    PreferenceRule("relax", ("relax", "spa", "thermal", "terme", "quiet", "calm")),
]

TRANSPORT_PATTERNS = {
    "car": ("car", "auto", "macchina", "drive", "driving"),
    "train": ("train", "treno", "rail"),
    "bus": ("bus", "coach", "pullman"),
    "bike": ("bike", "bicycle", "bici", "cycling"),
    "walking": ("walk", "walking", "a piedi"),
    "public transport": ("public transport", "transport", "mezzi", "mezzi pubblici"),
}

NEGATION_WORDS = r"don\'t|do not|without|avoid|not|no|non|senza|evitare|voglio evitare"


class NLPService:
    """spaCy-based extraction for travel constraints and preferences."""

    def __init__(self) -> None:
        settings = get_settings()
        try:
            self.nlp = spacy.load(settings.spacy_model)
        except OSError as exc:
            raise RuntimeError(
                f"spaCy model '{settings.spacy_model}' is required. Run: python -m spacy download {settings.spacy_model}"
            ) from exc

    def extract(self, prompt: str) -> ExtractedTravelInfo:
        cleaned = clean_user_text(prompt)
        doc = self.nlp(cleaned)

        start_location = self._extract_start_location(cleaned, doc)
        max_distance_km = self._extract_distance_km(cleaned)
        max_travel_time_minutes = self._extract_travel_time_minutes(cleaned)
        trip_duration = self._extract_trip_duration(cleaned)
        preferred_transport, avoided_transport = self._extract_transport(cleaned)
        preferences = self._extract_preferences(cleaned)
        avoid_terms = self._extract_avoid_terms(cleaned)

        raw_entities = [
            {"text": ent.text, "label": ent.label_}
            for ent in doc.ents
            if ent.label_ in {"GPE", "LOC", "FAC", "ORG"}
        ]

        query_terms = dedupe_keep_order(
            [
                *(preferences or []),
                *(avoid_terms or []),
                preferred_transport or "",
                trip_duration or "",
            ]
        )

        return ExtractedTravelInfo(
            cleaned_text=cleaned,
            start_location=start_location,
            max_distance_km=max_distance_km,
            max_travel_time_minutes=max_travel_time_minutes,
            trip_duration=trip_duration,
            preferred_transport=preferred_transport,
            avoided_transport=avoided_transport,
            preferences=preferences,
            avoid_terms=avoid_terms,
            query_terms=query_terms,
            raw_entities=raw_entities,
        )

    def _extract_start_location(self, text: str, doc: Any) -> Optional[str]:
        patterns = [
            r"\b(?:from|leave|leaving|departing from|starting from|start from)\s+([A-ZÀ-Ý][\wÀ-ÿ' -]{1,50})",
            r"\b(?:currently in|i am in|i'm in|im in|based in|near)\s+([A-ZÀ-Ý][\wÀ-ÿ' -]{1,50})",
            r"\b(?:parto da|partire da|da)\s+([A-ZÀ-Ý][\wÀ-ÿ' -]{1,50})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                candidate = self._clean_location_candidate(match.group(1))
                if candidate:
                    return candidate

        # Use the first geopolitical entity when no explicit departure pattern is present.
        for ent in doc.ents:
            if ent.label_ in {"GPE", "LOC"}:
                return ent.text.strip()
        return None

    @staticmethod
    def _clean_location_candidate(candidate: str) -> Optional[str]:
        candidate = re.split(
            r"\b(for|with|by|and|but|to|up to|within|for a|for the|during|because)\b",
            candidate,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        candidate = candidate.strip(" ,.;:!?\"'")
        return candidate or None

    @staticmethod
    def _extract_distance_km(text: str) -> Optional[float]:
        km_match = re.search(r"\b(?:up to|within|around|about|max(?:imum)?|less than)?\s*(\d+(?:\.\d+)?)\s*(km|kilometers|kilometres)\b", text, re.I)
        if km_match:
            return float(km_match.group(1))

        miles_match = re.search(r"\b(?:up to|within|around|about|max(?:imum)?|less than)?\s*(\d+(?:\.\d+)?)\s*(miles|mile|mi)\b", text, re.I)
        if miles_match:
            return round(float(miles_match.group(1)) * 1.60934, 2)
        return None

    @staticmethod
    def _extract_travel_time_minutes(text: str) -> Optional[int]:
        hour_match = re.search(r"\b(?:up to|within|around|about|max(?:imum)?|less than)?\s*(\d+(?:\.\d+)?)\s*(hours|hour|hrs|hr|ore|ora)\b", text, re.I)
        if hour_match:
            return int(float(hour_match.group(1)) * 60)

        minute_match = re.search(r"\b(?:up to|within|around|about|max(?:imum)?|less than)?\s*(\d+)\s*(minutes|minute|min|mins|minuti)\b", text, re.I)
        if minute_match:
            return int(minute_match.group(1))
        return None

    @staticmethod
    def _extract_trip_duration(text: str) -> Optional[str]:
        lowered = text.lower()
        if "weekend" in lowered:
            return "weekend"
        if re.search(r"\bday trip\b|\bone day\b|\bgiornata\b", lowered):
            return "day trip"
        match = re.search(r"\b(\d+)\s*(days|day|nights|night|giorni|giorno|notti|notte)\b", lowered)
        if match:
            return f"{match.group(1)} {match.group(2)}"
        return None

    def _extract_transport(self, text: str) -> tuple[Optional[str], List[str]]:
        lowered = text.lower()
        avoided = []
        preferred = []

        for transport, terms in TRANSPORT_PATTERNS.items():
            joined_terms = "|".join(re.escape(term) for term in terms)
            is_present = any(term in lowered for term in terms)
            negation_pattern = rf"\b({NEGATION_WORDS})\b[^.?!]{{0,40}}\b({joined_terms})\b"
            is_negated = bool(re.search(negation_pattern, lowered, re.I))

            if is_negated:
                avoided.append(transport)
            elif is_present:
                preferred.append(transport)

        return (preferred[0] if preferred else None, dedupe_keep_order(avoided))

    @staticmethod
    def _extract_preferences(text: str) -> List[str]:
        lowered = text.lower()
        found = []
        for rule in PREFERENCE_RULES:
            if any(re.search(rf"\b{re.escape(pattern)}\b", lowered) for pattern in rule.patterns):
                found.append(rule.label)
        return dedupe_keep_order(found)

    @staticmethod
    def _extract_avoid_terms(text: str) -> List[str]:
        lowered = text.lower()
        avoid_terms = []
        patterns = [
            ("crowded places", r"\b(avoid|without|not|no|non|senza)[^.?!]{0,30}(crowd|crowded|affollat)") ,
            ("cities", r"\b(avoid|without|not|no|non|senza)[^.?!]{0,30}(city|cities|citt)") ,
            ("expensive places", r"\b(avoid|without|not|no|non|senza)[^.?!]{0,30}(expensive|costly|caro|costos)") ,
            ("touristic places", r"\b(avoid|without|not|no|non|senza)[^.?!]{0,30}(touristic|touristy|turistic)") ,
        ]
        for label, pattern in patterns:
            if re.search(pattern, lowered, re.I):
                avoid_terms.append(label)
        return dedupe_keep_order(avoid_terms)
