"""
TechFilings - Embedder 模块
使用 nomic-embed-text (本地 Ollama) 生成文本向量，存入 Chroma
"""

import os
import json
from typing import List, Dict
from openai import OpenAI
import chromadb
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

import sys
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (USE_LOCAL_EMBEDDING,  # noqa: E402
                    OPENAI_EMBEDDING_MODEL, 
                    EMBEDDING_MODEL, 
                    OLLAMA_URL,
                    BATCH_SIZE, 
                    CHUNKS_PATH,
                    CHROMA_PERSIST_DIR)




class DocumentEmbedder:
    def __init__(self, collection_name: str = "techfilings"):
        self.collection_name = collection_name
        self.embedding_model = OPENAI_EMBEDDING_MODEL if not USE_LOCAL_EMBEDDING else EMBEDDING_MODEL

        # check Ollama if using local embedding
        self._check_ollama()

        # initialize Chroma client and collection
        os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "TechFilings SEC fillings embedding collection"}
        )

    def _check_ollama(self):
        if not USE_LOCAL_EMBEDDING:
            print(f"[✓] Use OpenAI embedding: {OPENAI_EMBEDDING_MODEL}")
            return
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            if not any(EMBEDDING_MODEL in m for m in models):
                print(f"{EMBEDDING_MODEL} not founs, please run ollama pull {EMBEDDING_MODEL}")
        except Exception:
            print("Warning: Ollama is not working, please run 'ollama serve' and ensure it's accessible at the configured URL.")

    def get_embedding(self, text: str) -> list[float]:
        if USE_LOCAL_EMBEDDING:
            response = requests.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": text},
                timeout=30
            )
            return response.json()["embedding"]
        else:
            
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.embeddings.create(
                model=OPENAI_EMBEDDING_MODEL,
                input=text
            )
            return response.data[0].embedding
        

    def get_embeddings_batch(self, texts: List[str], batch_size: int = BATCH_SIZE) -> List[List[float]]:
        all_embeddings = [None] * len(texts)
        
        def embed_one(args):
            idx, text = args
            return idx, self.get_embedding(text)
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(embed_one, (i, text)): i for i, text in enumerate(texts)}
            completed = 0
            for future in as_completed(futures):
                idx, embedding = future.result()
                all_embeddings[idx] = embedding
                completed += 1
                if completed % 100 == 0:
                    print(f"Processed {completed}/{len(texts)} chunks")
        
        return all_embeddings

    def embed_chunks(self, chunks: List[Dict]) -> None:
        if not chunks:
            print("No chunks to embed.")
            return

        print(f"{len(chunks)} chunks to embed.")
        print(f"Embedding model used: {self.embedding_model}")
        print("-" * 50)

        ids = [chunk["chunk_id"] for chunk in chunks]
        texts = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]

        embeddings = self.get_embeddings_batch(texts)

        # Save to Chroma in batches to avoid memory issues
        batch_size = 500

        for i in range(0, len(chunks), batch_size):
            end_idx = min(i + batch_size, len(chunks))
            self.collection.add(
                ids=ids[i:end_idx],
                embeddings=embeddings[i:end_idx],
                documents=texts[i:end_idx],
                metadatas=metadatas[i:end_idx]
            )

        print(f"\nEmbeddings are saved to {CHROMA_PERSIST_DIR}")

    def build_index(self, chunks: List[Dict] = None) -> None:
        if chunks is None:
            if not os.path.exists(CHUNKS_PATH):
                print(f"Error: no chunks found {CHUNKS_PATH}")
                return

            with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
                chunks = json.load(f)

        # Empty existing collection before rebuilding
        try:
            self.chroma_client.delete_collection(self.collection_name)
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "TechFilings SEC fillings embedding collection"}
            )
            print("Existing collection cleared.")
        except Exception:
            pass

        self.embed_chunks(chunks)

    def get_collection_info(self) -> Dict:
        return {
            "name": self.collection_name,
            "count": self.collection.count(),
            "persist_dir": CHROMA_PERSIST_DIR
        }


def main():

    embedder = DocumentEmbedder()
    embedder.build_index()

    info=embedder.get_collection_info()
    print(f"\n The info is {info}")

if __name__ == "__main__":
    main()