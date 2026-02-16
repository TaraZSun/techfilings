"""
TechFilings - Searcher 模块
处理用户查询，在向量数据库中检索相关内容
"""

import os
from typing import List, Dict, Optional

from dotenv import load_dotenv
load_dotenv()

import chromadb
from openai import OpenAI

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CHROMA_PERSIST_DIR, OPENAI_EMBEDDING_MODEL


class DocumentSearcher:
    """在向量数据库中搜索相关内容"""
    
    def __init__(self, collection_name: str = "techfilings"):
        """
        初始化searcher
        
        Args:
            collection_name: Chroma collection名称
        """
        self.collection_name = collection_name
        self.embedding_model = OPENAI_EMBEDDING_MODEL
        
        # 初始化OpenAI client
        self.openai_client = OpenAI()
        
        # 连接Chroma
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        self.collection = self.chroma_client.get_collection(name=collection_name)
    
    def get_query_embedding(self, query: str) -> List[float]:
        """
        获取查询文本的embedding
        
        Args:
            query: 用户查询
            
        Returns:
            embedding向量
        """
        response = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=query
        )
        return response.data[0].embedding
    
    def search(
        self, 
        query: str, 
        top_k: int = 5,
        filter_ticker: Optional[str] = None,
        filter_filing_type: Optional[str] = None
    ) -> List[Dict]:
        """
        搜索与query最相关的文档块
        
        Args:
            query: 用户的查询
            top_k: 返回结果数量
            filter_ticker: 按公司筛选 (如 "NVDA")
            filter_filing_type: 按文件类型筛选 (如 "10-K")
            
        Returns:
            相关文档块列表
        """
        # 获取query的embedding
        query_embedding = self.get_query_embedding(query)
        
        # 构建筛选条件
        where_filter = None
        if filter_ticker or filter_filing_type:
            conditions = []
            if filter_ticker:
                conditions.append({"ticker": filter_ticker})
            if filter_filing_type:
                conditions.append({"filing_type": filter_filing_type})
            
            if len(conditions) == 1:
                where_filter = conditions[0]
            else:
                where_filter = {"$and": conditions}
        
        # 在Chroma中搜索
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        # 整理返回结果
        search_results = []
        
        if results and results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                result = {
                    "chunk_id": results["ids"][0][i],
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i],
                    # 将distance转换为相似度分数 (越高越相似)
                    "similarity": 1 / (1 + results["distances"][0][i])
                }
                search_results.append(result)
        
        return search_results
    
    def search_by_company(self, query: str, ticker: str, top_k: int = 5) -> List[Dict]:
        """按公司搜索"""
        return self.search(query, top_k=top_k, filter_ticker=ticker)
    
    def search_10k_only(self, query: str, top_k: int = 5) -> List[Dict]:
        """只搜索10-K文件"""
        return self.search(query, top_k=top_k, filter_filing_type="10-K")
    
    def search_10q_only(self, query: str, top_k: int = 5) -> List[Dict]:
        """只搜索10-Q文件"""
        return self.search(query, top_k=top_k, filter_filing_type="10-Q")


def main():
    """测试搜索功能"""
    print("TechFilings - 搜索测试")
    print("=" * 50)
    
    searcher = DocumentSearcher()
    
    # 测试查询
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
            print(f"  公司: {metadata['ticker']}")
            print(f"  文件: {metadata['filing_type']} ({metadata['filing_date']})")
            print(f"  章节: {metadata['section_item']} - {metadata['section_title']}")
            print(f"  相似度: {result['similarity']:.3f}")
            print(f"  内容预览: {result['text'][:200]}...")
    
    print(f"\n{'=' * 50}")
    print("搜索测试完成!")


if __name__ == "__main__":
    main()