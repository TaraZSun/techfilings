import os
import requests
from openai import OpenAI
from config import (OPENAI_CHAT_MODEL, 
                    OLLAMA_CHAT_URL, 
                    USE_LOCAL_MODEL,
                    EMBEDDING_MODEL,
                    OPENAI_EMBEDDING_MODEL,
                    CHAT_MODEL)


class ModelClient:
    
    @staticmethod
    def get_embeddings(query: str) -> list[float]:
        if USE_LOCAL_MODEL:
            response = requests.post(
                f"{OLLAMA_CHAT_URL}/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": query},
                timeout=30
            )
            return response.json()["embedding"]
        else:
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            response = client.embeddings.create(
                model=OPENAI_EMBEDDING_MODEL,
                input=query
            )
            return response.data[0].embedding
        
    @staticmethod
    def chat(messages: list[dict], temperature=0.5, max_tokens=1000) -> str:
        try:
            if USE_LOCAL_MODEL:
                client = OpenAI(
                    base_url=f"{OLLAMA_CHAT_URL}/v1",
                    api_key="local-ollama-key"
                )
                model=CHAT_MODEL
            else:
                client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                model=OPENAI_CHAT_MODEL

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"[Chat failed: {e}]"