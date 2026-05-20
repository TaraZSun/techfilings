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
import yaml
from modules import model_client
from config import TOP_K
_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompt", "retrieval_prompts.yaml")
with open(_path) as f:
    _prompts = yaml.safe_load(f)
ANSWER_PROMPT = _prompts["answer_prompt"]
COMPANY_ALIASES = {
    "NVDA": ["nvidia", "nvda"],
    "AMD": ["amd", "advanced micro devices"],
    "PLTR": ["palantir", "pltr"],
    "MSFT": ["microsoft", "msft"],
}

class DocumentRetriever:
    def __init__(self):
        self.searcher = DocumentSearcher()
        self.reranker = None  # disable reranking for cloud deploy to save resources
        self.cross_encoder_model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def _get_reranker(self):
        if self.reranker is None:
            # set up environment variables for Hugging Face model loading
            if os.environ.get("HF.ENDPOINT"):
                print("Using custom Hugging Face endpoint for CrossEncoder model.")

            # allow offline loading if TRANSFORMERS_OFFLINE=1 is set
            if os.getenv("TRANSFORMERS_OFFLINE") == "1":
                print("Loading CrossEncoder model in offline mode.")
            
            try:
                from sentence_transformers.cross_encoder import CrossEncoder
                self.reranker = CrossEncoder(self.cross_encoder_model_name)
            except Exception as e:
                print(f"Failed to load CrossEncoder model: {e}")
                self.reranker = None
                raise

        return self.reranker
        

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
        
        return model_client.ModelClient.chat(
                messages=[
                    {"role": "system", "content": "You are a financial analyst assistant. Answer ONLY based on the provided sources. Do not infer, extrapolate, or add information not explicitly stated in the context. If the context is insufficient, say so."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=1000,
            )
        

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

    def retrieve_multi_company(self, query: str, companies: list[str], top_k_per_company: int = 3) -> list[dict]:
        all_results = []
        for company in companies:
            results = self.searcher.search(
                query=query,
                top_k=top_k_per_company,
                filter_ticker=company,
            )
            all_results.extend(results)
        return all_results

    def detect_companies(self, query: str) -> list[str]:
        query_lower = query.lower()
        found = []
        for ticker, aliases in COMPANY_ALIASES.items():
            if any(alias in query_lower for alias in aliases):
                found.append(ticker)
        return found
    
    def rerank(self, query: str, search_results: list[dict], top_k: int) -> list[dict]:
        reranker = self._get_reranker()

        if reranker is None:
            print("Reranker model not available, skipping reranking.")
            return search_results[:top_k]
            # Prepare pairs for scoring
        pairs = [[query, result["text"]] for result in search_results]
        try:
            scores = reranker.predict(pairs)
            ranked = sorted(
                zip(scores, search_results),
                key=lambda x: x[0],
                reverse=True
            )
            return [result for _, result in ranked[:top_k]]
        except Exception as e:
            print(f"Reranking failed: {e}")
            return search_results[:top_k]

    def retrieve_and_answer(
        self,
        query: str,
        top_k: int = TOP_K,
        filter_company: str = None,
        filter_form_type: str = None,
    ) -> dict:
        companies = self.detect_companies(query)

        if len(companies) > 1:
            search_results = self.retrieve_multi_company(query, companies)
        else:
            search_results = self.searcher.search(
                query=query,
                top_k=top_k,
                filter_ticker=filter_company or (companies[0] if companies else None),
                filter_filing_type=filter_form_type,
            )
        search_results = self.rerank(query, search_results, top_k)
        answer = self.generate_answer(query, search_results)
        citations = self.format_citations(search_results)

        return {
            "query": query,
            "answer": answer,
            "citations": citations,
            "num_sources": len(citations),
        }
    def expand_query(self, query: str) -> str:
        return model_client.ModelClient.chat(
            messages=[{
                "role": "user",
                "content": f"Expand this financial query with relevant terminology and context for searching SEC filings. Return only the expanded query, no explanation.\n\nQuery: {query}"
            }],
            temperature=0,
            max_tokens=150,
        )
       