"""
TechFilings - Embedder 模块
使用 nomic-embed-text (本地 Ollama) 生成文本向量，存入 Chroma
"""

import os
import json
from typing import List, Dict

import chromadb
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PROCESSED_DIR, CHROMA_PERSIST_DIR


# ─────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────
from config import EMBEDDING_MODEL, OLLAMA_URL  # noqa: E402
CHUNKS_PATH = os.path.join(PROCESSED_DIR, "chunks.json")


# ─────────────────────────────────────────────
# Embedder
# ─────────────────────────────────────────────

class DocumentEmbedder:
    def __init__(self, collection_name: str = "techfilings"):
        self.collection_name = collection_name
        self.embedding_model = EMBEDDING_MODEL

        # 检查 Ollama 连接
        self._check_ollama()

        # 初始化 Chroma
        os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "TechFilings SEC财报向量库"}
        )

    def _check_ollama(self):
        try:
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            if not any(EMBEDDING_MODEL in m for m in models):
                print(f"[警告] 未找到模型 {EMBEDDING_MODEL}，请先运行: ollama pull {EMBEDDING_MODEL}")
            else:
                print(f"[✓] {EMBEDDING_MODEL} 连接正常")
        except Exception:
            print("[警告] Ollama 未运行，请先执行: ollama serve")

    def get_embedding(self, text: str) -> List[float]:
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": self.embedding_model, "prompt": text},
            timeout=30
        )
        return response.json()["embedding"]

    

    def get_embeddings_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
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
                    print(f"  已处理 {completed}/{len(texts)} 个块")
        
        return all_embeddings

    def embed_chunks(self, chunks: List[Dict]) -> None:
        if not chunks:
            print("没有 chunks 需要处理")
            return

        print(f"开始生成 embeddings，共 {len(chunks)} 个块")
        print(f"使用模型: {self.embedding_model}")
        print("-" * 50)

        ids = [chunk["chunk_id"] for chunk in chunks]
        texts = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]

        embeddings = self.get_embeddings_batch(texts)

        # 存入 Chroma
        print("\n存入 Chroma 向量库...")
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
        if chunks is None:
            if not os.path.exists(CHUNKS_PATH):
                print(f"错误: 找不到分块文件 {CHUNKS_PATH}")
                print("请先运行 python modules/sec_indexer.py")
                return

            with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
                chunks = json.load(f)

        # 清空现有数据，重建索引
        try:
            self.chroma_client.delete_collection(self.collection_name)
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "TechFilings SEC财报向量库"}
            )
            print("已清空现有索引，重新构建...")
        except Exception:
            pass

        self.embed_chunks(chunks)

    def get_collection_info(self) -> Dict:
        return {
            "name": self.collection_name,
            "count": self.collection.count(),
            "persist_dir": CHROMA_PERSIST_DIR
        }


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

def main():
    print("TechFilings - 向量化工具")
    print("=" * 50)

    embedder = DocumentEmbedder()
    embedder.build_index()

    info = embedder.get_collection_info()
    print(f"\n{'=' * 50}")
    print(f"向量化完成!")
    print(f"Collection: {info['name']}")
    print(f"向量数量: {info['count']}")
    print(f"存储位置: {info['persist_dir']}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()