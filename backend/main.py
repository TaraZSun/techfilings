"""
backend/main.py
FastAPI backend for TechFilings.
Exposes /api/query endpoint for the frontend.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sys
import os
import threading
import traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from modules.retriever import DocumentRetriever
from modules.data_storage import save_query, save_feedback
from bootstrap_index import ensure_index, index_status


# ── Warm-up state ──────────────────────────────────────────────────────────
# The retriever is NOT built at import time. On a fresh Railway volume the
# index has to be embedded first (minutes of OpenAI calls), and constructing
# the searcher also loads the whole corpus into memory for BM25. Doing that
# inline would either crash the worker on boot or blow the healthcheck
# timeout, so it happens in a background thread and /api/query reports 503
# until it finishes.
_retriever: Optional["DocumentRetriever"] = None
_warmup_error: Optional[str] = None
_warmup_done = threading.Event()


def _warmup():
    global _retriever, _warmup_error
    try:
        ensure_index()
        _retriever = DocumentRetriever()
        print("[startup] retriever ready")
    except Exception as e:
        _warmup_error = f"{type(e).__name__}: {e}"
        print(f"[startup] warm-up FAILED: {_warmup_error}")
        traceback.print_exc()
    finally:
        _warmup_done.set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_warmup, name="index-warmup", daemon=True).start()
    yield


def get_retriever() -> "DocumentRetriever":
    if _retriever is not None:
        return _retriever
    if _warmup_error:
        raise HTTPException(
            status_code=503,
            detail=f"Search index unavailable: {_warmup_error}",
        )
    raise HTTPException(
        status_code=503,
        detail="Search index is still being built, please retry shortly.",
    )


app = FastAPI(title="TechFilings API", version="1.0.0", lifespan=lifespan)

# ── CORS ───────────────────────────────────────────────────────────────────
# Allow frontend (Vercel) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "https://techfilings.vercel.app",   
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request / Response models ──────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str
    chat_id: Optional[str] = None
    cookie_accepted: Optional[bool] = False


class Citation(BaseModel):
    index: int
    company: str
    form_type: str
    period: str
    section: str
    text: str
    similarity: float


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]


class FeedbackRequest(BaseModel):
    chat_id: Optional[str] = None
    feedback_text: str
    after_question_num: int


# ── Routes ─────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "ok", "service": "TechFilings API"}


@app.get("/health")
def health():
    """Always 200 so Railway does not kill the container while the index builds."""
    return {
        "status": "healthy",
        "index_ready": _retriever is not None,
        "warmup_done": _warmup_done.is_set(),
        "warmup_error": _warmup_error,
    }


@app.get("/health/index")
def health_index():
    """Detailed index state — path actually in use, record count, vector dimension."""
    return index_status()


@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    retriever = get_retriever()

    try:
        result = retriever.retrieve_and_answer(query=req.question, top_k=5)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")

    answer = result["answer"]
    citations = result.get("citations", [])

    # Save to Supabase only if user accepted cookie
    if req.cookie_accepted:
        save_query(
            chat_id=req.chat_id or "",
            question=req.question,
            answer=answer,
            cookie_accepted=True,
        )

    return QueryResponse(answer=answer, citations=citations)


@app.post("/api/feedback")
def feedback(req: FeedbackRequest):
    if not req.feedback_text.strip():
        raise HTTPException(status_code=400, detail="Feedback cannot be empty")

    save_feedback(
        chat_id=req.chat_id or "",
        feedback_text=req.feedback_text,
        after_question_num=req.after_question_num,
    )
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)