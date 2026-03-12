"""
TechFilings - Retriever Module
Uses OpenAI's GPT-4 to generate answers based on retrieved document sections. 
Retrieves relevant sections from filings and formats them for the prompt. 
Also formats citations for frontend display.
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.searcher import DocumentSearcher
import openai
import yaml
from config import OPENAI_CHAT_MODEL, TOP_K
_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt", "retrieval_prompts.yaml")
with open(_path) as f:
    _prompts = yaml.safe_load(f)
ANSWER_PROMPT = _prompts["answer_prompt"]


class DocumentRetriever:
    def __init__(self):
        self.searcher = DocumentSearcher()


    def format_sources_for_prompt(self, search_results: list[dict]) -> str:
        context_parts = []
        for i, result in enumerate(search_results):
            metadata = result["metadata"]      
            source_info = (
                f"[Source {i+1} | Company: {metadata.get('company', metadata.get('ticker', '')) } | "
                f"Filing: {metadata.get('form_type', metadata.get('filing_type', ''))} | "
                f"Period: {metadata.get('period', metadata.get('filing_date', ''))} | "
                f"Section: {metadata.get('section', metadata.get('section_title', ''))}]"
            )
            context_parts.append(f"{source_info}\n{result['text']}")
        return "\n\n---\n\n".join(context_parts)

    def generate_answer(self, query: str, search_results: list[dict]) -> str:
        if not search_results:
            return "No relevant information found in the filings."

        context = self.format_sources_for_prompt(search_results)
        prompt = ANSWER_PROMPT.format(context=context, query=query)

        try:
            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model=OPENAI_CHAT_MODEL,
                messages=[
                    {"role": "system", "content": "You are a financial analyst assistant. Answer ONLY based on the provided sources. Do not infer, extrapolate, or add information not explicitly stated in the context. If the context is insufficient, say so."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=1000,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"[Generation failed: {e}]"

    def format_citations(self, search_results: list[dict]) -> list[dict]:
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
        top_k: int = TOP_K,
        filter_company: str = None,
        filter_form_type: str = None,
    ) -> dict:
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
    def retrieve_multi_company(self, query, companies, top_k_per_company=3):
        all_results = []
        for company in companies:
            results = self.searcher.search(
                query=query,
                top_k=top_k_per_company,
                filter_ticker=company,
            )
            all_results.extend(results)
        return all_results