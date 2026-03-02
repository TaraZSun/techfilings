import json
import os
import requests
from datetime import datetime
from typing import List, Dict

from config import OLLAMA_URL, CHAT_MODEL, CHATS_DIR


def init():
    os.makedirs(CHATS_DIR, exist_ok=True)

def new_chat_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def save_chat(chat_id: str, messages: List[Dict], title: str = None):
    init()
    path = os.path.join(CHATS_DIR, f"{chat_id}.json")
    with open(path, "w") as f:
        json.dump({"id": chat_id, "title": title, "messages": messages}, f, ensure_ascii=False, indent=2)

def load_chat(chat_id: str) -> Dict:
    path = os.path.join(CHATS_DIR, f"{chat_id}.json")
    with open(path) as f:
        return json.load(f)

def list_chats() -> List[Dict]:
    init()
    chats = []
    for fname in sorted(os.listdir(CHATS_DIR), reverse=True):
        if fname.endswith(".json"):
            with open(os.path.join(CHATS_DIR, fname)) as f:
                data = json.load(f)
                chats.append({"id": data["id"], "title": data.get("title", "New Chat")})
    return chats

def generate_title(first_message: str) -> str:
    prompt = f"""Generate a short title (5 words or less) for a conversation that starts with this question:
"{first_message}"
Reply with only the title, no quotes, no punctuation."""
    
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": CHAT_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 20}
            },
            timeout=30
        )
        return response.json().get("response", "").strip()
    except Exception:
        return first_message[:30]