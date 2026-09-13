"""
SEC Filing Chunker

Output Path:
  data/processed/chunks.json
"""

import json
import re
from pathlib import Path


import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import  PROCESSED_DIR, CHUNKS_PATH, CHUNK_SIZE

SKIP_SECTIONS = [
    "DOCUMENTS INCORPORATED BY REFERENCE",
    "TABLE OF CONTENTS",
    "SIGNATURES",
    "EXHIBIT INDEX",
    "CERTIFICATIONS",
    "EXHIBITS",
    "FINANCIAL STATEMENT SCHEDULES",
]

def should_skip_section(section_name: str) -> bool:
  
    for skip in SKIP_SECTIONS:
        if skip.upper() in section_name.upper():
            return True
    return False


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



def split_text(text: str, chunk_size: int = CHUNK_SIZE) -> list[str]:
   
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []

    # chunk according to paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    for para in paragraphs:
        if len(para) <= chunk_size:
            chunks.append(para)
        else:
            # chunk according to sentences
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




def chunk_document(json_path: str) -> list[dict]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    file_meta = parse_filename(Path(json_path).name)
    chunks = []
    chunk_idx = 0

    pending_texts = []
    current_section = "UNKNOWN"


    def flush_pending():
        nonlocal chunk_idx
        if not pending_texts:
            return
        
        if should_skip_section(current_section):
            pending_texts.clear()
            return
        
        merged = "\n\n".join(pending_texts)
        prefix = (
            f"Company: {file_meta['company']} | "
            f"Filing: {file_meta['form_type']} | "
            f"Period: {file_meta['period']} | "
            f"Section: {current_section}\n\n"
        )
        # prefix = (
        #     f"[TEXT] {file_meta['company']} {file_meta['form_type']} {file_meta['period']}\n"
        #     f"Section: {pending_section}\n\n"
        # )
        for text_chunk in split_text(prefix + merged):
            chunks.append({
                "chunk_id": f"{Path(json_path).stem}_chunk_{chunk_idx}",
                "text": text_chunk,
                "metadata": {
                    "company": file_meta["company"],
                    "form_type": file_meta["form_type"],
                    "period": file_meta["period"],
                    "section": current_section,
                    "type": "text",
                    "source": Path(json_path).name,
                },
            })
            chunk_idx += 1
        pending_texts.clear()

    for element in data["elements"]:
        elem_type = element["type"]
        content = element["content"].strip()
        section_from_elem = element.get("section", "")

        if not content:
            continue
        
        if elem_type=="section_header":
            flush_pending()
            current_section = content
            continue

        if section_from_elem and section_from_elem != current_section:
            flush_pending()
            current_section = section_from_elem

        if elem_type == "table":
            flush_pending()
            if should_skip_section(current_section):
                continue
            
            text = (
                f"Company: {file_meta['company']} | "
                f"Filing: {file_meta['form_type']} | "
                f"Period: {file_meta['period']} | "
                f"Section: {current_section}\n\n{content}"
            )
            chunks.append({
                "chunk_id": f"{Path(json_path).stem}_chunk_{chunk_idx}",
                "text": text,
                "metadata": {
                    "company": file_meta["company"],
                    "form_type": file_meta["form_type"],
                    "period": file_meta["period"],
                    "section": current_section,
                    "type": "table",
                    "source": Path(json_path).name,
                },
            })
            chunk_idx += 1

        elif elem_type == "text":
            pending_texts.append(content)

    flush_pending()
    return chunks

def chunk_all():
    processed_path = Path(PROCESSED_DIR)
    json_files = list(processed_path.glob("*_parsed.json"))

    if not json_files:
        print(f"[!] No {PROCESSED_DIR} files found. Run the parser first.")
        return


    all_chunks = []
    for json_file in json_files:
        chunks = chunk_document(str(json_file))
        tables = sum(1 for c in chunks if c["metadata"]["type"] == "table")
        texts = sum(1 for c in chunks if c["metadata"]["type"] == "text")
        print(f"  {json_file.name}: table={tables} text={texts} {len(chunks)} chunks")
        all_chunks.extend(chunks)

    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"\n[✓] {len(all_chunks)} chunks")
   


if __name__ == "__main__":
    chunk_all()