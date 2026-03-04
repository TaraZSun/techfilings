"""
modules/data_storage.py
Saves user queries and feedback to Supabase.

Setup:
1. Create a free project at https://supabase.com
2. Run the SQL below in Supabase SQL Editor to create tables
3. Add SUPABASE_URL and SUPABASE_KEY to Streamlit secrets or .env

-- SQL to run in Supabase:
CREATE TABLE queries (
    id          BIGSERIAL PRIMARY KEY,
    chat_id     TEXT,
    question    TEXT,
    answer      TEXT,
    timestamp   TIMESTAMPTZ DEFAULT NOW(),
    cookie_accepted BOOLEAN
);

CREATE TABLE feedbacks (
    id                  BIGSERIAL PRIMARY KEY,
    chat_id             TEXT,
    feedback_text       TEXT,
    after_question_num  INT,
    timestamp           TIMESTAMPTZ DEFAULT NOW()
);
"""

import os
from datetime import datetime, timezone

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


def _get_client():
    url = os.environ.get("SUPABASE_URL") or ""
    key = os.environ.get("SUPABASE_KEY") or ""
    if not url or not key:
        return None
    if not SUPABASE_AVAILABLE:
        return None
    return create_client(url, key)


def save_query(chat_id: str, question: str, answer: str, cookie_accepted: bool = False):
    """Save a user question + answer pair."""
    client = _get_client()
    if client is None:
        return  # Silently skip if Supabase not configured

    try:
        client.table("queries").insert({
            "chat_id": chat_id,
            "question": question,
            "answer": answer,
            "cookie_accepted": cookie_accepted,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        print(f"[data_storage] Failed to save query: {e}")


def save_feedback(chat_id: str, feedback_text: str, after_question_num: int):
    """Save a user feedback submission."""
    client = _get_client()
    if client is None:
        return

    try:
        client.table("feedbacks").insert({
            "chat_id": chat_id,
            "feedback_text": feedback_text,
            "after_question_num": after_question_num,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        print(f"[data_storage] Failed to save feedback: {e}")