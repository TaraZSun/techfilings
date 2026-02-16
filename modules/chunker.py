"""
TechFilings - Chunker 模块
将解析后的内容分块，为embedding做准备
使用LlamaIndex的SentenceSplitter进行递归分块，按token计数
"""

import os
import json
from typing import List, Dict

import tiktoken
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import Document, TextNode

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PROCESSED_DIR


class DocumentChunker:
    """将文档分成适合检索的块"""
    
    def __init__(self, chunk_size: int = 1024, chunk_overlap: int = 128):
        """
        初始化chunker
        
        Args:
            chunk_size: 每个块的目标大小（token数）
            chunk_overlap: 相邻块的重叠大小（token数）
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # 使用tiktoken来计算token数（OpenAI的tokenizer）
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # 使用LlamaIndex的SentenceSplitter，配置tokenizer
        self.splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            tokenizer=self.tokenizer.encode,
        )
    
    def chunk_section(self, section: Dict, filing_info: Dict) -> List[Dict]:
        """
        将单个章节分块
        
        Args:
            section: 章节内容 {"item": "Item 1", "title": "Business", "content": "..."}
            filing_info: 文件信息 {"ticker": "NVDA", "filing_type": "10-K", ...}
            
        Returns:
            分块列表
        """
        content = section.get("content", "")
        
        if not content or len(content) < 50:
            return []
        
        # 创建LlamaIndex Document
        doc = Document(text=content)
        
        # 分块
        nodes = self.splitter.get_nodes_from_documents([doc])
        
        chunks = []
        for i, node in enumerate(nodes):
            chunk = {
                "chunk_id": f"{filing_info['ticker']}_{filing_info['filing_type']}_{filing_info['filing_date']}_{section['item']}_{i}",
                "text": node.text,
                "metadata": {
                    "ticker": filing_info["ticker"],
                    "filing_type": filing_info["filing_type"],
                    "filing_date": filing_info["filing_date"],
                    "filename": filing_info["filename"],
                    "section_item": section["item"],
                    "section_title": section["title"],
                    "chunk_index": i,
                    "total_chunks_in_section": len(nodes),
                }
            }
            chunks.append(chunk)
        
        return chunks
    
    def chunk_document(self, document: Dict) -> List[Dict]:
        """
        将单个文档的所有章节分块
        
        Args:
            document: 解析后的文档 (parser.py的输出)
            
        Returns:
            该文档所有块的列表
        """
        filing_info = {
            "ticker": document["ticker"],
            "filing_type": document["filing_type"],
            "filing_date": document["filing_date"],
            "filename": document["filename"],
        }
        
        all_chunks = []
        
        for section in document.get("sections", []):
            chunks = self.chunk_section(section, filing_info)
            all_chunks.extend(chunks)
        
        return all_chunks
    
    def chunk_all(self, parsed_filings: List[Dict] = None) -> List[Dict]:
        """
        处理所有解析后的文档
        
        Args:
            parsed_filings: 解析后的文档列表，如果不传则从文件读取
            
        Returns:
            所有块的列表
        """
        # 如果没有传入数据，从文件读取
        if parsed_filings is None:
            parsed_path = os.path.join(PROCESSED_DIR, "parsed_filings.json")
            
            if not os.path.exists(parsed_path):
                print(f"错误: 找不到解析文件 {parsed_path}")
                print("请先运行 parser.py")
                return []
            
            with open(parsed_path, 'r', encoding='utf-8') as f:
                parsed_filings = json.load(f)
        
        all_chunks = []
        
        print(f"开始分块，共 {len(parsed_filings)} 个文档")
        print(f"参数: chunk_size={self.chunk_size}, overlap={self.chunk_overlap}")
        print("-" * 50)
        
        for doc in parsed_filings:
            ticker = doc["ticker"]
            filing_type = doc["filing_type"]
            filing_date = doc["filing_date"]
            
            chunks = self.chunk_document(doc)
            all_chunks.extend(chunks)
            
            print(f"{ticker} {filing_type} {filing_date}: {len(chunks)} 个块")
        
        # 保存分块结果
        self._save_chunks(all_chunks)
        
        return all_chunks
    
    def _save_chunks(self, chunks: List[Dict]) -> None:
        """保存分块结果"""
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        
        output_path = os.path.join(PROCESSED_DIR, "chunks.json")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        
        print(f"\n分块结果已保存: {output_path}")


def main():
    """主函数"""
    print("TechFilings - 文档分块工具")
    print("=" * 50)
    
    chunker = DocumentChunker(chunk_size=1024, chunk_overlap=128)
    chunks = chunker.chunk_all()
    
    if chunks:
        # 统计信息
        total_chunks = len(chunks)
        
        # 用tiktoken计算实际token数
        total_tokens = sum(len(chunker.tokenizer.encode(c["text"])) for c in chunks)
        avg_tokens = total_tokens / total_chunks if total_chunks > 0 else 0
        
        print(f"\n{'=' * 50}")
        print(f"分块完成!")
        print(f"总块数: {total_chunks}")
        print(f"平均块大小: {avg_tokens:.0f} tokens")
        print(f"总token数: {total_tokens:,}")
        print(f"{'=' * 50}")
    
    return chunks


if __name__ == "__main__":
    main()