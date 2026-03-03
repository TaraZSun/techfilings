"""
TechFilings 配置文件
"""
from datetime import datetime

# SEC EDGAR API 设置
SEC_BASE_URL = "https://www.sec.gov"
SEC_EDGAR_API = "https://data.sec.gov"
USER_AGENT = "TechFilings Research Project (sunzhiying321@gmail.com)" # SEC要求提供联系方式

# 目标公司的CIK代码（SEC用来识别公司的唯一ID）
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

OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "nomic-embed-text"
CHAT_MODEL = "llama3.2:latest"

# 要下载的文件类型
FILING_TYPES = ["10-K", "10-Q"]

# 每种文件类型下载的数量（最近几份）
FILINGS_PER_TYPE = 3

# 数据存储路径
DATA_DIR = "data"
RAW_DIR = f"{DATA_DIR}/raw"
PROCESSED_DIR = f"{DATA_DIR}/processed"
CHUNKS_PATH = f"{PROCESSED_DIR}/chunks.json"
CHATS_DIR = "data/chats"

INPUT_CSV = "data/samples/sample_qa_v2.csv"
OUTPUT_CSV = f"output/eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# OpenAI 设置
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_CHAT_MODEL = "gpt-4o-mini"

# Chroma 设置
CHROMA_PERSIST_DIR = f"{DATA_DIR}/chroma_db"


CHUNK_SIZE = 1024
CHUNK_OVERLAP = 64

TOP_K = 5
