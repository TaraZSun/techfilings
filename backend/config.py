"""
TechFilings Configurations
"""
from datetime import datetime
import os
# SEC EDGAR API config
SEC_BASE_URL = "https://www.sec.gov"
SEC_EDGAR_API = "https://data.sec.gov"
USER_AGENT = "TechFilings Research Project (sunzhiying321@gmail.com)" 

COMPANIES = {
    "NVIDIA": {
        "cik": "0001045810",
        "ticker": "NVDA"
    },
    "AMD": {
        "cik": "0000002488",
        "ticker": "AMD"
    },
    "Palantir": {
        "cik": "0001321655",
        "ticker": "PLTR"
    }
}

OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_CHAT_MODEL = "gpt-4o-mini"
# local
OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "nomic-embed-text"
CHAT_MODEL = "llama3.2:latest"

USE_LOCAL_EMBEDDING = False  # True = nomic-embed-text, False = OpenAI

FILING_TYPES = ["10-K", "10-Q"]

FILINGS_PER_TYPE = 3

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RAW_DIR = f"{DATA_DIR}/raw"
PROCESSED_DIR = f"{DATA_DIR}/processed"
CHUNKS_PATH = f"{PROCESSED_DIR}/chunks.json"
CHATS_DIR = "data/chats"

INPUT_CSV = "data/qa_samples/sample_qa_v2.csv"
OUTPUT_CSV = f"output/eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "embeddings", "chroma_db")

CHUNK_SIZE = 1024
CHUNK_OVERLAP = 64
BATCH_SIZE = 32
TOP_K = 5
