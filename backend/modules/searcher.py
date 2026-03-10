"""
TechFilings - Searcher 模块
使用本地 nomic-embed-text 在向量数据库中检索相关内容
"""

import os
import requests
from typing import List, Dict, Optional
import chromadb
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from openai import OpenAI
from techfilings.backend.config import USE_LOCAL_EMBEDDING, OPENAI_EMBEDDING_MODEL
from techfilings.backend.config import EMBEDDING_MODEL,OLLAMA_URL,CHROMA_PERSIST_DIR, TOP_K
from dotenv import load_dotenv
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class DocumentSearcher:
    def __init__(self, collection_name: str = "techfilings"):
        self.collection_name = collection_name
        self.embedding_model = EMBEDDING_MODEL

        # 连接 Chroma
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        self.collection = self.chroma_client.get_collection(name=collection_name)

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

    def search(
        self,
        query: str,
        top_k: int = TOP_K,
        filter_ticker: Optional[str] = None,
        filter_filing_type: Optional[str] = None,
        filter_period: Optional[str] = None,
    ) -> List[Dict]:
        query_embedding = self.get_query_embedding(query)

        # 构建筛选条件（兼容新旧 metadata 字段）
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
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        search_results = []
        if results and results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                search_results.append({
                    "chunk_id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                    "similarity": 1 / (1 + results["distances"][0][i])
                })

        return search_results

    def search_by_company(self, query: str, company: str, top_k: int = TOP_K) -> List[Dict]:
        return self.search(query, top_k=top_k, filter_ticker=company)

    def search_10k_only(self, query: str, top_k: int = TOP_K) -> List[Dict]:
        return self.search(query, top_k=top_k, filter_filing_type="10-K")

    def search_10q_only(self, query: str, top_k: int = TOP_K) -> List[Dict]:
        return self.search(query, top_k=top_k, filter_filing_type="10-Q")


def main():
    print("TechFilings - 搜索测试")
    print("=" * 50)

    searcher = DocumentSearcher()

    test_queries = [
        "What is NVIDIA's revenue from data center?",
        "What are the risk factors for AMD?",
        "Palantir government contracts"
    ]

    for query in test_queries:
        print(f"\n查询: {query}")
        print("-" * 50)

        results = searcher.search(query, top_k=3)

        for i, result in enumerate(results):
            metadata = result["metadata"]
            print(f"\n结果 {i+1}:")
            print(f"  公司: {metadata.get('company', '')}")
            print(f"  文件: {metadata.get('form_type', '')} ({metadata.get('period', '')})")
            print(f"  章节: {metadata.get('section', '')}")
            print(f"  类型: {metadata.get('type', '')}")
            print(f"  相似度: {result['similarity']:.3f}")
            print(f"  预览: {result['text'][:200]}...")

    print(f"\n{'=' * 50}")
    print("搜索测试完成!")


if __name__ == "__main__":
    main()