"""
TechFilings - 索引构建脚本
运行数据准备流程：下载 -> 解析 -> 分块 -> 向量化
"""

from modules.loader import SECLoader
from modules.parser import SECParser
from modules.chunker import DocumentChunker
from modules.embedder import DocumentEmbedder


def build_index():
    """构建完整的向量索引"""
    
    print("="*60)
    print("TechFilings - 索引构建")
    print("="*60)
    
    # Step 1: 下载财报
    print("\n[Step 1/4] 下载财报文件...")
    loader = SECLoader()
    download_results = loader.download_all()
    
    # Step 2: 解析文件
    print("\n[Step 2/4] 解析财报内容...")
    parser = SECParser()
    # TODO: parsed_docs = parser.parse_all()
    
    # Step 3: 分块
    print("\n[Step 3/4] 文档分块...")
    chunker = DocumentChunker()
    # TODO: chunks = chunker.chunk_all()
    
    # Step 4: 生成向量并存储
    print("\n[Step 4/4] 生成向量索引...")
    embedder = DocumentEmbedder()
    # TODO: embedder.build_index()
    
    print("\n" + "="*60)
    print("索引构建完成!")
    print("="*60)


if __name__ == "__main__":
    build_index()
