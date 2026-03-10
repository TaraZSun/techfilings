"""
TechFilings Configurations
"""
from datetime import datetime
import os

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
USE_LOCAL_EMBEDDING = False
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_CHAT_MODEL = "gpt-4o-mini"
OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "nomic-embed-text"
CHAT_MODEL = "llama3.2:latest"

# ── Paths ──────────────────────────────────────────────────────────────────
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR       = os.path.join(_BASE, "data")
RAW_DIR        = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR  = os.path.join(DATA_DIR, "processed")
CHUNKS_PATH    = os.path.join(PROCESSED_DIR, "chunks.json")
CHROMA_PERSIST_DIR = os.path.join(_BASE, "embeddings", "chroma_db")
INPUT_CSV  = os.path.join(DATA_DIR, "qa_samples", "sample_qa_v2.csv")
OUTPUT_CSV = os.path.join(_BASE, "output", f"eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
CLASSIFED_RAW_FILINGS= os.path.join(_BASE, "data", "classified_raw_filings")

# ── Chunking & Retrieval ───────────────────────────────────────────────────
CHUNK_SIZE    = 1024
CHUNK_OVERLAP = 64
BATCH_SIZE    = 32
TOP_K         = 5