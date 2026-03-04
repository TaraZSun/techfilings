"""
TechFilings - Retriever 模块
使用本地 llama3.2 生成回答
"""

import os
import requests # type: ignore
from typing import List, Dict
import sys
from modules.searcher import DocumentSearcher
from modules.prompt import system_prompt
from config import OLLAMA_URL, CHAT_MODEL
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DocumentRetriever:
    def __init__(self):
        self.chat_model = CHAT_MODEL
        self.searcher = DocumentSearcher()
        self._check_ollama()

    def _check_ollama(self):
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            if not any(self.chat_model in m for m in models):
                print(f"[警告] 未找到模型 {self.chat_model}")
            else:
                print(f"[✓] {self.chat_model} 连接正常")
        except Exception:
            print("[警告] Ollama 未运行，请先执行: ollama serve")

    def format_sources_for_prompt(self, search_results: List[Dict]) -> str:
        context_parts = []
        for i, result in enumerate(search_results):
            metadata = result["metadata"]
            source_info = (
                f"[Source {i+1}] "
                f"{metadata.get('company', metadata.get('ticker', ''))} "
                f"{metadata.get('form_type', metadata.get('filing_type', ''))} "
                f"({metadata.get('period', metadata.get('filing_date', ''))}) "
                f"- {metadata.get('section', metadata.get('section_title', ''))}"
            )
            context_parts.append(f"{source_info}\n{result['text']}")
        return "\n\n---\n\n".join(context_parts)

    def generate_answer(self, query: str, search_results: List[Dict]) -> str:
        if not search_results:
            return "No relevant information found in the filings."

        context = self.format_sources_for_prompt(search_results)
        prompt = system_prompt.ANSWER_PROMPT.format(context=context, query=query)

        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": self.chat_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 1000}
                },
                timeout=120
            )
            return response.json().get("response", "").strip()
        except Exception as e:
            return f"[Generation failed: {e}]"

    def format_citations(self, search_results: List[Dict]) -> List[Dict]:
        citations = []
        for i, result in enumerate(search_results):
            metadata = result["metadata"]
            text = result["text"]
            citations.append({
                "index": i + 1,
                "company": metadata.get("company", metadata.get("ticker", "")),
                "form_type": metadata.get("form_type", metadata.get("filing_type", "")),
                "period": metadata.get("period", metadata.get("filing_date", "")),
                "section": metadata.get("section", metadata.get("section_title", "")),
                "type": metadata.get("type", ""),
                "text": text,
                "text_preview": text[:300] + "..." if len(text) > 300 else text,
                "similarity": result.get("similarity", 0),
            })
        return citations

    def retrieve_and_answer(
        self,
        query: str,
        top_k: int = 5,
        filter_company: str = None,
        filter_form_type: str = None,
    ) -> Dict:
        search_results = self.searcher.search(
            query=query,
            top_k=top_k,
            filter_ticker=filter_company,
            filter_filing_type=filter_form_type,
        )

        answer = self.generate_answer(query, search_results)
        citations = self.format_citations(search_results)

        return {
            "query": query,
            "answer": answer,
            "citations": citations,
            "num_sources": len(citations),
        }


def main():
    print("TechFilings - 检索回答测试")
    print("=" * 60)

    retriever = DocumentRetriever()

    test_query = "What is NVIDIA's data center revenue and how has it grown?"
    print(f"\n查询: {test_query}")
    print("-" * 60)

    result = retriever.retrieve_and_answer(test_query, top_k=5)

    print(f"\n【AI回答】\n{result['answer']}")
    print(f"\n【引用来源】({result['num_sources']}个)")
    print("-" * 60)

    for citation in result["citations"]:
        print(f"\n引用 {citation['index']}:")
        print(f"  {citation['company']} | {citation['form_type']} | {citation['period']}")
        print(f"  章节: {citation['section']}")
        print(f"  类型: {citation['type']}")
        print(f"  相似度: {citation['similarity']:.3f}")
        print(f"  预览: {citation['text_preview'][:150]}")

    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    main()