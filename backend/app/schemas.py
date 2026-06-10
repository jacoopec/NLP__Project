from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TripPlanRequest(BaseModel):
    prompt: str = Field(..., min_length=5, description="Natural language travel request")


class ExtractedTravelInfo(BaseModel):
    cleaned_text: str
    start_location: Optional[str] = None
    max_distance_km: Optional[float] = None
    max_travel_time_minutes: Optional[int] = None
    trip_duration: Optional[str] = None
    preferred_transport: Optional[str] = None
    avoided_transport: List[str] = Field(default_factory=list)
    preferences: List[str] = Field(default_factory=list)
    avoid_terms: List[str] = Field(default_factory=list)
    query_terms: List[str] = Field(default_factory=list)
    raw_entities: List[Dict[str, Any]] = Field(default_factory=list)


class Review(BaseModel):
    text: str
    author: Optional[str] = None
    rating: Optional[float] = None
    url: Optional[str] = None
    source: str = "web"


class Destination(BaseModel):
    name: str
    description: Optional[str] = None
    source: Literal["rag", "web", "rag+web"]
    address: Optional[str] = None
    url: Optional[str] = None
    photo_url: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_km: Optional[float] = None
    travel_notes: Optional[str] = None
    reviews: List[Review] = Field(default_factory=list)
    evidence_urls: List[str] = Field(default_factory=list)


class TripPlanResponse(BaseModel):
    status: Literal["ok", "needs_input", "error"]
    messages: List[str] = Field(default_factory=list)
    extracted: Optional[ExtractedTravelInfo] = None
    destinations: List[Destination] = Field(default_factory=list)
    debug: Dict[str, Any] = Field(default_factory=dict)
