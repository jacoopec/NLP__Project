from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.graph.travel_graph import travel_graph
from app.schemas import TripPlanRequest, TripPlanResponse

settings = get_settings()

app = FastAPI(title="Agentic Travel Planner", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/trips/plan", response_model=TripPlanResponse)
def plan_trip(payload: TripPlanRequest) -> TripPlanResponse:
    state = travel_graph.invoke({"raw_prompt": payload.prompt})
    return TripPlanResponse(
        status=state.get("status", "error"),
        messages=state.get("messages", []),
        extracted=state.get("extracted"),
        destinations=state.get("destinations", []),
        debug=state.get("debug", {}),
    )
