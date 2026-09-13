"""
TechFilings Configurations
"""
from datetime import datetime
import os

from dotenv import load_dotenv

# Loaded here (not just in main.py) so standalone scripts such as
# `python -m modules.chunker` see the same env-driven config.
load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")

# ── API ────────────────────────────────────────────────────────────────────
SEC_BASE_URL = "https://www.sec.gov"
SEC_EDGAR_API = "https://data.sec.gov"
USER_AGENT = "TechFilings Research Project (sunzhiying321@gmail.com)"

# ── Companies ──────────────────────────────────────────────────────────────
COMPANIES = {
    "NVIDIA":     {"cik": "0001045810", "ticker": "NVDA"},
    "AMD":        {"cik": "0000002488", "ticker": "AMD"},
    "Palantir":   {"cik": "0001321655", "ticker": "PLTR"},
    "Microsoft":  {"cik": "0000789019", "ticker": "MSFT"},
}

# ── Filing Settings ────────────────────────────────────────────────────────
FILING_TYPES = ["10-K", "10-Q"]
START_YEAR = 2025
END_YEAR = 2026

# ── Embedding & LLM ───────────────────────────────────────────────────────
# Local (Ollama) by default for dev; set USE_LOCAL_MODEL=false on Railway,
# where there is no Ollama to talk to. Changing this changes the embedding
# dimension (nomic-embed-text 768 vs text-embedding-3-small 1536), so the
# Chroma index must be rebuilt whenever it flips.
USE_LOCAL_MODEL = _env_bool("USE_LOCAL_MODEL", True)
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_CHAT_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "nomic-embed-text"
CHAT_MODEL = "llama3.2:latest"
OLLAMA_CHAT_URL = os.environ.get("OLLAMA_CHAT_URL", "http://localhost:11434")
EMBEDDING_DIM = 1536 if not USE_LOCAL_MODEL else 768

# ── Paths ──────────────────────────────────────────────────────────────────
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR       = os.path.join(_BASE, "data")
RAW_DIR        = os.path.join(DATA_DIR, "raw", "classified_raw_filings")
PROCESSED_DIR  = os.path.join(DATA_DIR, "processed")
CHUNKS_PATH    = os.path.join(PROCESSED_DIR, "chunks.json")
# The index must NOT live inside the repo/image on Railway: that filesystem is
# ephemeral and the vector segment files are gitignored. Point this at a
# mounted volume in production (CHROMA_PERSIST_DIR=/data/chroma_db).
_BACKEND = os.path.dirname(os.path.abspath(__file__))
CHROMA_PERSIST_DIR = os.environ.get("CHROMA_PERSIST_DIR") or os.path.join(
    os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or _BACKEND,
    "embeddings",
    "chroma_db",
)
INPUT_CSV  = os.path.join(DATA_DIR, "qa_samples", "sample_qa_v2.csv")
OUTPUT_CSV = os.path.join(_BASE, "output", f"eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
CLASSIFED_RAW_FILINGS= os.path.join(_BASE, "data", "classified_raw_filings")

# ── Chunking & Retrieval ───────────────────────────────────────────────────
CHUNK_SIZE    = 1024
CHUNK_OVERLAP = 64
BATCH_SIZE    = 32
TOP_K         = 5