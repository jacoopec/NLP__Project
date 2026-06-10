from typing import Any, Dict, List, Optional

import chromadb
from chromadb.utils import embedding_functions

from app.config import get_settings
from app.schemas import Destination, Review


class ServiceConfigurationError(RuntimeError):
    pass


class RAGService:
    """ChromaDB retrieval over local user-review documents."""

    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.openai_api_key:
            raise ServiceConfigurationError(
                "OPENAI_API_KEY is missing. It is required for ChromaDB OpenAI embeddings."
            )

        self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
            api_key=self.settings.openai_api_key,
            model_name=self.settings.openai_embedding_model,
        )
        self.client = chromadb.PersistentClient(path=self.settings.chroma_dir)
        self.collection = self.client.get_or_create_collection(
            name=self.settings.chroma_collection,
            embedding_function=self.embedding_function,
        )

    def search(self, query: str, n_results: int = 6) -> List[Destination]:
        if self.collection.count() == 0:
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        destinations: List[Destination] = []
        for document, metadata, distance in zip(documents, metadatas, distances):
            if distance is not None and distance > self.settings.rag_max_distance:
                continue

            name = metadata.get("place_name") or metadata.get("title")
            if not name:
                continue

            destinations.append(
                Destination(
                    name=name,
                    description=document,
                    source="rag",
                    address=metadata.get("address"),
                    latitude=_safe_float(metadata.get("latitude")),
                    longitude=_safe_float(metadata.get("longitude")),
                    travel_notes=metadata.get("travel_notes"),
                    reviews=[
                        Review(
                            text=document,
                            author=metadata.get("author", "local user review"),
                            rating=_safe_float(metadata.get("rating")),
                            source="local_rag",
                        )
                    ],
                    evidence_urls=[metadata.get("source_url")] if metadata.get("source_url") else [],
                )
            )
        return destinations


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
