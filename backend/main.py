"""
backend/main.py
FastAPI backend for TechFilings.
Exposes /api/query endpoint for the frontend.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from modules.retriever import DocumentRetriever
from modules.data_storage import save_query, save_feedback

app = FastAPI(title="TechFilings API", version="1.0.0")

# ── CORS ───────────────────────────────────────────────────────────────────
# Allow frontend (Vercel) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "https://*.vercel.app",   # your Vercel frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Retriever (loaded once at startup) ────────────────────────────────────
retriever = DocumentRetriever()


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
    citations: List[Citation]


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
    return {"status": "healthy"}


@app.post("/api/query", response_model=QueryResponse)
def query(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = retriever.retrieve_and_answer(query=req.question, top_k=5)
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