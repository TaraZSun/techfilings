"""
TechFilings - Embedder 模块
使用OpenAI生成文本向量，存入Chroma
"""

import os
import json
from typing import List, Dict

from dotenv import load_dotenv
load_dotenv()  # 加载.env文件

import chromadb
from chromadb.config import Settings
from openai import OpenAI

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PROCESSED_DIR, CHROMA_PERSIST_DIR, OPENAI_EMBEDDING_MODEL


class DocumentEmbedder:
    """生成文档向量并存储到Chroma"""
    
    def __init__(self, collection_name: str = "techfilings"):
        """
        初始化embedder
        
        Args:
            collection_name: Chroma collection名称
        """
        self.collection_name = collection_name
        self.embedding_model = OPENAI_EMBEDDING_MODEL
        
        # 初始化OpenAI client
        self.openai_client = OpenAI()
        
        # 初始化Chroma client（持久化存储）
        os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        
        # 获取或创建collection
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "TechFilings SEC财报向量库"}
        )
    
    def get_embedding(self, text: str) -> List[float]:
        """
        获取单个文本的embedding
        
        Args:
            text: 输入文本
            
        Returns:
            embedding向量
        """
        response = self.openai_client.embeddings.create(
            model=self.embedding_model,
            input=text
        )
        return response.data[0].embedding
    
    def get_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        批量获取embeddings
        
        Args:
            texts: 文本列表
            batch_size: 每批处理数量（OpenAI限制单次最多2048个）
            
        Returns:
            embedding向量列表
        """
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=batch
            )
            
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
            
            print(f"  已处理 {min(i + batch_size, len(texts))}/{len(texts)} 个块")
        
        return all_embeddings
    
    def embed_chunks(self, chunks: List[Dict]) -> None:
        """
        为所有chunks生成embedding并存入Chroma
        
        Args:
            chunks: 分块后的文档列表
        """
        if not chunks:
            print("没有chunks需要处理")
            return
        
        print(f"开始生成embeddings，共 {len(chunks)} 个块")
        print(f"使用模型: {self.embedding_model}")
        print("-" * 50)
        
        # 提取文本和元数据
        ids = [chunk["chunk_id"] for chunk in chunks]
        texts = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]
        
        # 批量生成embeddings
        embeddings = self.get_embeddings_batch(texts)
        
        # 存入Chroma（分批存入，避免内存问题）
        print("\n存入Chroma向量库...")
        batch_size = 500
        
        for i in range(0, len(chunks), batch_size):
            end_idx = min(i + batch_size, len(chunks))
            
            self.collection.add(
                ids=ids[i:end_idx],
                embeddings=embeddings[i:end_idx],
                documents=texts[i:end_idx],
                metadatas=metadatas[i:end_idx]
            )
            
            print(f"  已存入 {end_idx}/{len(chunks)} 个块")
        
        print(f"\n向量库已保存到: {CHROMA_PERSIST_DIR}")
    
    def build_index(self, chunks: List[Dict] = None) -> None:
        """
        构建完整的向量索引
        
        Args:
            chunks: 分块列表，如果不传则从文件读取
        """
        # 如果没有传入数据，从文件读取
        if chunks is None:
            chunks_path = os.path.join(PROCESSED_DIR, "chunks.json")
            
            if not os.path.exists(chunks_path):
                print(f"错误: 找不到分块文件 {chunks_path}")
                print("请先运行 chunker.py")
                return
            
            with open(chunks_path, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
        
        # 清空现有数据（重建索引）
        try:
            self.chroma_client.delete_collection(self.collection_name)
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "TechFilings SEC财报向量库"}
            )
            print("已清空现有索引，重新构建...")
        except Exception:
            pass
        
        # 生成embeddings并存储
        self.embed_chunks(chunks)
    
    def get_collection_info(self) -> Dict:
        """获取向量库信息"""
        return {
            "name": self.collection_name,
            "count": self.collection.count(),
            "persist_dir": CHROMA_PERSIST_DIR
        }


def main():
    """主函数"""
    print("TechFilings - 向量化工具")
    print("=" * 50)
    
    embedder = DocumentEmbedder()
    embedder.build_index()
    
    # 显示结果
    info = embedder.get_collection_info()
    
    print(f"\n{'=' * 50}")
    print(f"向量化完成!")
    print(f"Collection: {info['name']}")
    print(f"向量数量: {info['count']}")
    print(f"存储位置: {info['persist_dir']}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()