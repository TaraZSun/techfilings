"""
TechFilings - Retriever 模块
根据搜索结果获取完整内容和出处，调用LLM生成回答
"""

import os
from typing import List, Dict

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENAI_CHAT_MODEL
from modules.searcher import DocumentSearcher


class DocumentRetriever:
    """检索文档并生成回答"""
    
    def __init__(self):
        """初始化retriever"""
        self.openai_client = OpenAI()
        self.chat_model = OPENAI_CHAT_MODEL
        self.searcher = DocumentSearcher()
    
    def format_sources_for_prompt(self, search_results: List[Dict]) -> str:
        """
        将搜索结果格式化为prompt中的上下文
        
        Args:
            search_results: 搜索返回的结果列表
            
        Returns:
            格式化的上下文字符串
        """
        context_parts = []
        
        for i, result in enumerate(search_results):
            metadata = result["metadata"]
            source_info = f"[Source {i+1}] {metadata['ticker']} {metadata['filing_type']} ({metadata['filing_date']}) - {metadata['section_item']}: {metadata['section_title']}"
            content = result["text"]
            
            context_parts.append(f"{source_info}\n{content}")
        
        return "\n\n---\n\n".join(context_parts)
    
    def generate_answer(self, query: str, search_results: List[Dict]) -> str:
        """
        根据搜索结果生成回答
        
        Args:
            query: 用户查询
            search_results: 搜索返回的结果列表
            
        Returns:
            AI生成的回答
        """
        if not search_results:
            return "抱歉，没有找到相关信息。"
        
        # 构建上下文
        context = self.format_sources_for_prompt(search_results)
        
        # 构建prompt
        system_prompt = """You are a financial analyst assistant that helps users understand SEC filings (10-K and 10-Q reports).

Your job is to:
1. Answer the user's question based ONLY on the provided source documents
2. Be specific and cite which source you're using (e.g., "According to Source 1...")
3. If the information is not in the sources, say so clearly
4. Keep your answer concise but comprehensive
5. Use numbers and specific data when available

Answer in the same language as the user's question."""

        user_prompt = f"""Based on the following SEC filing excerpts, please answer this question:

Question: {query}

Sources:
{context}

Please provide a clear, well-structured answer with citations to the sources."""

        # 调用OpenAI
        response = self.openai_client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    
    def format_citations(self, search_results: List[Dict]) -> List[Dict]:
        """
        格式化引用信息供前端展示
        
        Args:
            search_results: 搜索结果
            
        Returns:
            格式化的引用列表
        """
        citations = []
        
        for i, result in enumerate(search_results):
            metadata = result["metadata"]
            
            citation = {
                "index": i + 1,
                "ticker": metadata["ticker"],
                "filing_type": metadata["filing_type"],
                "filing_date": metadata["filing_date"],
                "section": f"{metadata['section_item']}: {metadata['section_title']}",
                "text": result["text"],
                "text_preview": result["text"][:300] + "..." if len(result["text"]) > 300 else result["text"],
                "similarity": result["similarity"]
            }
            citations.append(citation)
        
        return citations
    
    def retrieve_and_answer(
        self, 
        query: str, 
        top_k: int = 5,
        filter_ticker: str = None,
        filter_filing_type: str = None
    ) -> Dict:
        """
        完整的检索和回答流程
        
        Args:
            query: 用户查询
            top_k: 返回结果数量
            filter_ticker: 按公司筛选
            filter_filing_type: 按文件类型筛选
            
        Returns:
            包含AI回答和原文引用的结果
        """
        # 搜索相关文档
        search_results = self.searcher.search(
            query=query,
            top_k=top_k,
            filter_ticker=filter_ticker,
            filter_filing_type=filter_filing_type
        )
        
        # 生成回答
        answer = self.generate_answer(query, search_results)
        
        # 格式化引用
        citations = self.format_citations(search_results)
        
        return {
            "query": query,
            "answer": answer,
            "citations": citations,
            "num_sources": len(citations)
        }


def main():
    """测试检索和回答功能"""
    print("TechFilings - 检索回答测试")
    print("=" * 60)
    
    retriever = DocumentRetriever()
    
    # 测试查询
    test_query = "What is NVIDIA's data center revenue and how has it grown?"
    
    print(f"\n查询: {test_query}")
    print("-" * 60)
    
    result = retriever.retrieve_and_answer(test_query, top_k=5)
    
    print(f"\n【AI回答】\n{result['answer']}")
    
    print(f"\n【引用来源】({result['num_sources']}个)")
    print("-" * 60)
    
    for citation in result["citations"]:
        print(f"\n引用 {citation['index']}:")
        print(f"  {citation['ticker']} | {citation['filing_type']} | {citation['filing_date']}")
        print(f"  章节: {citation['section']}")
        print(f"  相似度: {citation['similarity']:.3f}")
        print(f"  预览: {citation['text_preview'][:150]}...")
    
    print(f"\n{'=' * 60}")
    print("测试完成!")


if __name__ == "__main__":
    main()