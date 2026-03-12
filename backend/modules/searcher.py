"""
TechFilings - Searcher module
"""

import os
import requests
from typing import List, Dict, Optional
import chromadb
import sys
from rank_bm25 import BM25Okapi
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from openai import OpenAI
from config import (EMBEDDING_MODEL,OLLAMA_URL,
                            CHROMA_PERSIST_DIR, TOP_K,
                            USE_LOCAL_EMBEDDING, 
                            OPENAI_EMBEDDING_MODEL)

from dotenv import load_dotenv
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class DocumentSearcher:
    def __init__(self, collection_name: str = "techfilings"):
        self.collection_name = collection_name
        self.embedding_model = EMBEDDING_MODEL
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        self.collection = self.chroma_client.get_collection(name=collection_name)
        
        # Preload all documents for BM25 search
        all_data = self.collection.get(include=["documents", "metadatas"])
        self.bm25_ids = all_data["ids"]
        self.bm25_docs = all_data["documents"]
        self.bm25_metadatas = all_data["metadatas"]
        corpus = [doc.lower().split() for doc in self.bm25_docs]
        self.bm25 = BM25Okapi(corpus)

    def get_query_embedding(self, query: str) -> list[float]:
        if USE_LOCAL_EMBEDDING:
            response = requests.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMBEDDING_MODEL, "prompt": query},
                timeout=30
            )
            return response.json()["embedding"]
        else:
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.embeddings.create(
                model=OPENAI_EMBEDDING_MODEL,
                input=query
            )
            return response.data[0].embedding

    def search(self, query, top_k=TOP_K, filter_ticker=None,
           filter_filing_type=None, filter_period=None):

        # 1. embedding dense search
        query_embedding = self.get_query_embedding(query)

        where_filter = None
        if filter_ticker or filter_filing_type or filter_period:
            conditions = []
            if filter_ticker:
                conditions.append({"company": {"$eq": filter_ticker}})
            if filter_filing_type:
                conditions.append({"form_type": {"$eq": filter_filing_type}})
            if filter_period:
                conditions.append({"period": {"$eq": filter_period}})
            where_filter = conditions[0] if len(conditions) == 1 else {"$and": conditions}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k * 2,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        dense_results = []
        if results and results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                dense_results.append({
                    "chunk_id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                    "similarity": 1 / (1 + results["distances"][0][i])
                })

        # 2. BM25 sparse search
        tokens = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokens)
        top_sparse_idx = sorted(range(len(bm25_scores)),
                                key=lambda i: bm25_scores[i], reverse=True)[:top_k * 2]

        sparse_results = []
        for idx in top_sparse_idx:
            meta = self.bm25_metadatas[idx]
            if filter_ticker and meta.get("company") != filter_ticker:
                continue
            if filter_filing_type and meta.get("form_type") != filter_filing_type:
                continue
            if filter_period and meta.get("period") != filter_period:
                continue
            sparse_results.append({
                "chunk_id": self.bm25_ids[idx],
                "text": self.bm25_docs[idx],
                "metadata": meta,
                "similarity": float(bm25_scores[idx])
            })

        # 3. RRF fusion
        rrf_scores = {}
        id_to_result = {}
        for rank, r in enumerate(dense_results):
            cid = r["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0) + 1 / (60 + rank + 1)
            id_to_result[cid] = r
        for rank, r in enumerate(sparse_results):
            cid = r["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0) + 1 / (60 + rank + 1)
            id_to_result[cid] = r

        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
        return [id_to_result[cid] for cid in sorted_ids[:top_k]]
    def search_by_company(self, query: str, company: str, top_k: int = TOP_K) -> List[Dict]:
        return self.search(query, top_k=top_k, filter_ticker=company)

    def search_10k_only(self, query: str, top_k: int = TOP_K) -> List[Dict]:
        return self.search(query, top_k=top_k, filter_filing_type="10-K")

    def search_10q_only(self, query: str, top_k: int = TOP_K) -> List[Dict]:
        return self.search(query, top_k=top_k, filter_filing_type="10-Q")

