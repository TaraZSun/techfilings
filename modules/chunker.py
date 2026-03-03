"""
SEC Filing Chunker
将 parsed JSON → chunks.json
供 embedder.py 读取使用

输出格式：
  data/processed/chunks.json
"""

import json
import re
from pathlib import Path

# ─────────────────────────────────────────────
# 路径配置
# ─────────────────────────────────────────────

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import  PROCESSED_DIR, CHUNKS_PATH, CHUNK_SIZE



# ─────────────────────────────────────────────
# 从文件名提取元数据
# ─────────────────────────────────────────────

def parse_filename(filename: str) -> dict:
    """
    AMD_10-Q_2025-05-07_parsed.json
    → company=AMD, form_type=10-Q, period=2025-05-07
    """
    stem = filename.replace("_parsed.json", "")
    parts = stem.split("_")
    return {
        "company": parts[0] if len(parts) > 0 else "",
        "form_type": parts[1] if len(parts) > 1 else "",
        "period": parts[2] if len(parts) > 2 else "",
    }


# ─────────────────────────────────────────────
# 文字 chunking（recursive）
# ─────────────────────────────────────────────

def split_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
    """
    层级切割：段落 → 句子
    - 优先按段落（\n\n）切
    - 段落超过 chunk_size 再按句子切
    - 不使用 overlap，避免单词截断
    """
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []

    # 第一层：按段落切
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    for para in paragraphs:
        if len(para) <= chunk_size:
            chunks.append(para)
        else:
            # 第二层：按句子切
            sentences = re.split(r'(?<=[.!?])\s+', para)
            current = ""
            for sent in sentences:
                if len(current) + len(sent) + 1 <= chunk_size:
                    current = (current + " " + sent).strip()
                else:
                    if current:
                        chunks.append(current)
                    current = sent
            if current:
                chunks.append(current)

    return [c for c in chunks if c.strip()]



# ─────────────────────────────────────────────
# 主 chunking 逻辑
# ─────────────────────────────────────────────

def chunk_document(json_path: str) -> list[dict]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    file_meta = parse_filename(Path(json_path).name)
    chunks = []
    chunk_idx = 0

    # 按 section 积累文字
    pending_texts = []
    pending_section = "UNKNOWN"

    def flush_pending():
        nonlocal chunk_idx
        if not pending_texts:
            return
        merged = "\n\n".join(pending_texts)
     
        prefix = (
            f"[TEXT] {file_meta['company']} {file_meta['form_type']} {file_meta['period']}\n"
            f"Section: {pending_section}\n\n"
        )
        for text_chunk in split_text(prefix + merged):
            chunks.append({
                "chunk_id": f"{Path(json_path).stem}_chunk_{chunk_idx}",
                "text": text_chunk,
                "metadata": {
                    "company": file_meta["company"],
                    "form_type": file_meta["form_type"],
                    "period": file_meta["period"],
                    "section": pending_section,
                    "type": "text",
                    "source": Path(json_path).name,
                },
            })
            chunk_idx += 1
        pending_texts.clear()

    for element in data["elements"]:
        elem_type = element["type"]
        content = element["content"].strip()
        section = element.get("section", "UNKNOWN")

        if not content or elem_type == "section_header":
            continue

        if elem_type == "table":
            flush_pending()
            text = (
                f"[TABLE] {file_meta['company']} {file_meta['form_type']} {file_meta['period']}\n"
                f"Section: {section}\n\n{content}"
            )
            chunks.append({
                "chunk_id": f"{Path(json_path).stem}_chunk_{chunk_idx}",
                "text": text,
                "metadata": {
                    "company": file_meta["company"],
                    "form_type": file_meta["form_type"],
                    "period": file_meta["period"],
                    "section": section,
                    "type": "table",
                    "source": Path(json_path).name,
                },
            })
            chunk_idx += 1

        elif elem_type == "text":
            if section != pending_section:
                flush_pending()
                pending_section = section
            pending_texts.append(content)

    flush_pending()
    return chunks

# ─────────────────────────────────────────────
# 批量处理所有 parsed JSON
# ─────────────────────────────────────────────

def chunk_all():
    processed_path = Path(PROCESSED_DIR)
    json_files = list(processed_path.glob("*_parsed.json"))

    if not json_files:
        print(f"[!] 未在 {PROCESSED_DIR} 找到 parsed JSON 文件")
        return

    print(f"[信息] 共找到 {len(json_files)} 个文件")

    all_chunks = []
    for json_file in json_files:
        chunks = chunk_document(str(json_file))
        tables = sum(1 for c in chunks if c["metadata"]["type"] == "table")
        texts = sum(1 for c in chunks if c["metadata"]["type"] == "text")
        print(f"  {json_file.name}: 表格={tables} 文字={texts} 共{len(chunks)}个chunk")
        all_chunks.extend(chunks)

    # 保存到 chunks.json（embedder.py 读取这个文件）
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"\n[✓] 共 {len(all_chunks)} 个 chunks")
    print(f"[✓] 已保存到 {CHUNKS_PATH}")
    print(f"\n下一步运行: python modules/embedder.py")


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    chunk_all()