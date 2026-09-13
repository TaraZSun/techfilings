"""
backend/bootstrap_index.py

Makes the Chroma index at CHROMA_PERSIST_DIR usable, building it from
data/processed/chunks.json if it isn't.

Needed because CHROMA_PERSIST_DIR points at a mounted volume in production:
the volume starts empty, and the index cannot be shipped in the image (the
HNSW segment files are gitignored, and Railway's container filesystem is
ephemeral anyway). Safe to call on every boot — it is a no-op once the
volume holds a complete, dimension-matching index.

Run standalone to inspect or force a rebuild:
    python -m bootstrap_index            # build only if needed
    python -m bootstrap_index --force    # rebuild from scratch
"""

import os
import sys

import chromadb

from config import CHROMA_PERSIST_DIR, CHUNKS_PATH, EMBEDDING_DIM

COLLECTION_NAME = "techfilings"


def index_status(collection_name: str = COLLECTION_NAME) -> dict:
    """Report whether the persisted index is present, populated and the right shape."""
    status = {
        "path": CHROMA_PERSIST_DIR,
        "exists": False,
        "count": 0,
        "dim": None,
        "expected_dim": EMBEDDING_DIM,
        "usable": False,
        "reason": "",
    }

    if not os.path.isdir(CHROMA_PERSIST_DIR):
        status["reason"] = "persist dir does not exist"
        return status

    try:
        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        collection = client.get_collection(name=collection_name)
    except Exception as e:
        status["reason"] = f"cannot open collection: {e}"
        return status

    status["exists"] = True
    status["count"] = collection.count()
    if status["count"] == 0:
        status["reason"] = "collection is empty"
        return status

    # Chroma does not expose the collection dimension directly; read one vector.
    # This also catches the 768-vs-1536 mismatch after USE_LOCAL_MODEL flips.
    try:
        probe = collection.get(limit=1, include=["embeddings"])
        vectors = probe.get("embeddings")
        if vectors is not None and len(vectors) > 0:
            status["dim"] = len(vectors[0])
    except Exception as e:
        status["reason"] = f"cannot read vectors: {e}"
        return status

    if status["dim"] is None:
        status["reason"] = "metadata rows present but no vectors readable"
        return status

    if status["dim"] != EMBEDDING_DIM:
        status["reason"] = (
            f"dimension mismatch: index is {status['dim']}, "
            f"current embedding model produces {EMBEDDING_DIM}"
        )
        return status

    status["usable"] = True
    status["reason"] = "ok"
    return status


def ensure_index(force: bool = False, collection_name: str = COLLECTION_NAME) -> dict:
    status = index_status(collection_name)

    if status["usable"] and not force:
        print(f"[bootstrap] index ready: {status['count']} records, "
              f"dim={status['dim']}, path={status['path']}")
        return status

    if force:
        print("[bootstrap] --force given, rebuilding")
    else:
        print(f"[bootstrap] index not usable ({status['reason']}), rebuilding")

    if not os.path.exists(CHUNKS_PATH):
        raise RuntimeError(
            f"cannot build index: {CHUNKS_PATH} is missing. "
            "Run the parse/chunk pipeline, or make sure chunks.json ships with the deploy."
        )

    os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)

    # Imported lazily: DocumentEmbedder pings Ollama on construction, which is
    # pointless when the index is already fine.
    from modules.embedder import DocumentEmbedder

    DocumentEmbedder(collection_name=collection_name).build_index()

    status = index_status(collection_name)
    if not status["usable"]:
        raise RuntimeError(f"index still not usable after rebuild: {status['reason']}")

    print(f"[bootstrap] index built: {status['count']} records, dim={status['dim']}")
    return status


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    ensure_index(force="--force" in sys.argv)
