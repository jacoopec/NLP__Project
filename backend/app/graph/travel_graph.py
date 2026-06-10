from typing import Any, Dict, List, Literal, TypedDict

from langgraph.graph import END, StateGraph

from app.config import get_settings
from app.schemas import Destination, ExtractedTravelInfo
from app.services.nlp_service import NLPService
from app.services.rag_service import RAGService, ServiceConfigurationError
from app.services.serpapi_service import SerpApiService
from app.services.travel_pipeline import (
    build_rag_query,
    merge_destinations,
    missing_required_fields,
    validation_messages,
)


class TravelAgentState(TypedDict, total=False):
    raw_prompt: str
    extracted: ExtractedTravelInfo
    status: Literal["ok", "needs_input", "error"]
    messages: List[str]
    rag_candidates: List[Destination]
    web_candidates: List[Destination]
    destinations: List[Destination]
    debug: Dict[str, Any]


settings = get_settings()
nlp_service = NLPService()


def nlp_node(state: TravelAgentState) -> TravelAgentState:
    extracted = nlp_service.extract(state["raw_prompt"])
    return {
        **state,
        "extracted": extracted,
        "messages": [],
        "debug": {"cleaned_text": extracted.cleaned_text},
    }


def validation_node(state: TravelAgentState) -> TravelAgentState:
    extracted = state["extracted"]
    missing = missing_required_fields(extracted)
    if missing:
        return {
            **state,
            "status": "needs_input",
            "messages": validation_messages(missing),
            "destinations": [],
            "debug": {**state.get("debug", {}), "missing_fields": missing},
        }
    return {**state, "status": "ok"}


def rag_node(state: TravelAgentState) -> TravelAgentState:
    try:
        rag_service = RAGService()
        query = build_rag_query(state["extracted"])
        rag_candidates = rag_service.search(query, n_results=8)
        return {
            **state,
            "rag_candidates": rag_candidates,
            "destinations": rag_candidates,
            "debug": {**state.get("debug", {}), "rag_query": query, "rag_count": len(rag_candidates)},
        }
    except ServiceConfigurationError as exc:
        return {
            **state,
            "status": "error",
            "messages": [str(exc)],
            "destinations": [],
        }


def web_search_node(state: TravelAgentState) -> TravelAgentState:
    try:
        web_service = SerpApiService()
        existing = state.get("destinations", [])
        extracted_dict = state["extracted"].model_dump()
        web_candidates = web_service.search_destinations(extracted_dict, existing=existing)
        merged = merge_destinations(existing, web_candidates)
        return {
            **state,
            "web_candidates": web_candidates,
            "destinations": merged,
            "debug": {**state.get("debug", {}), "web_count": len(web_candidates)},
        }
    except Exception as exc:
        return {
            **state,
            "status": "error",
            "messages": [f"Real web search failed: {exc}"],
            "destinations": [],
        }


def enrich_node(state: TravelAgentState) -> TravelAgentState:
    try:
        web_service = SerpApiService()
        start_location = state["extracted"].start_location
        enriched: List[Destination] = []
        rejected: List[str] = []

        for destination in state.get("destinations", []):
            enriched_destination = web_service.enrich(destination, start_location=start_location)
            if enriched_destination:
                enriched.append(enriched_destination)
            else:
                rejected.append(destination.name)

        if len(enriched) < settings.min_results:
            return {
                **state,
                "status": "error",
                "messages": [
                    "The pipeline could not collect at least 3 complete real destinations with web photos and reviews. "
                    "Try a broader distance, broader preferences, or check the external search provider response."
                ],
                "destinations": enriched,
                "debug": {**state.get("debug", {}), "rejected_without_web_evidence": rejected},
            }

        return {
            **state,
            "status": "ok",
            "destinations": enriched[: settings.min_results],
            "messages": [],
            "debug": {**state.get("debug", {}), "rejected_without_web_evidence": rejected},
        }
    except Exception as exc:
        return {
            **state,
            "status": "error",
            "messages": [f"Web enrichment failed: {exc}"],
            "destinations": [],
        }


def route_after_validation(state: TravelAgentState) -> str:
    if state.get("status") == "needs_input":
        return "stop"
    if state.get("status") == "error":
        return "stop"
    return "rag"


def route_after_rag(state: TravelAgentState) -> str:
    if state.get("status") == "error":
        return "stop"
    # Web is always reached after RAG because every final card must be enriched
    # with real web photos and web reviews, and web search can fill missing candidates.
    return "web_search"


def build_graph():
    graph = StateGraph(TravelAgentState)
    graph.set_entry_point("nlp")

    graph.add_node("nlp", nlp_node)
    graph.add_node("validate", validation_node)
    graph.add_node("rag", rag_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("enrich", enrich_node)

    graph.add_edge("nlp", "validate")
    graph.add_conditional_edges(
        "validate",
        route_after_validation,
        {"rag": "rag", "stop": END},
    )
    graph.add_conditional_edges(
        "rag",
        route_after_rag,
        {"web_search": "web_search", "stop": END},
    )
    graph.add_edge("web_search", "enrich")
    graph.add_edge("enrich", END)

    return graph.compile()


travel_graph = build_graph()
