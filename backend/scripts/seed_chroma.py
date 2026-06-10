import json
import sys
from pathlib import Path

# Allows running this script from backend/ with: python scripts/seed_chroma.py
sys.path.append(str(Path(__file__).resolve().parents[1]))

import chromadb
from chromadb.utils import embedding_functions

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required to seed ChromaDB with OpenAI embeddings.")

    data_path = Path(__file__).resolve().parents[1] / "data" / "user_reviews_seed.json"
    reviews = json.loads(data_path.read_text(encoding="utf-8"))

    embedding_function = embedding_functions.OpenAIEmbeddingFunction(
        api_key=settings.openai_api_key,
        model_name=settings.openai_embedding_model,
    )

    client = chromadb.PersistentClient(path=settings.chroma_dir)

    # Recreate collection to keep the seed deterministic during development.
    try:
        client.delete_collection(settings.chroma_collection)
    except ValueError:
        pass

    collection = client.get_or_create_collection(
        name=settings.chroma_collection,
        embedding_function=embedding_function,
    )

    ids = [item["id"] for item in reviews]
    documents = [item["document"] for item in reviews]
    metadatas = []
    for item in reviews:
        metadata = {"place_name": item["place_name"], **item.get("metadata", {})}
        metadatas.append(metadata)

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"Seeded {len(ids)} user-review documents into Chroma collection '{settings.chroma_collection}'.")


if __name__ == "__main__":
    main()
