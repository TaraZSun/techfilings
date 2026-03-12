"""
TechFilings - Parser Main
"""

import time
import warnings
from pathlib import Path
from tqdm import tqdm

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from modules.parser.models import ParsedElement, ParsedDocument
from modules.parser.numeric import extract_numeric_data
from modules.parser.text import extract_text_elements

from config import CLASSIFED_RAW_FILINGS as RAW_DIR, PROCESSED_DIR


def parse_filename(filename: str) -> dict:
    stem = Path(filename).stem
    parts = stem.split("_")
    return {
        "company": parts[0] if len(parts) > 0 else "",
        "form_type": parts[1] if len(parts) > 1 else "",
    }


def get_output_path(html_path: str) -> str:
    filename = Path(html_path).stem
    return str(Path(PROCESSED_DIR) / f"{filename}_parsed.json")


def parse_file(html_path: str) -> ParsedDocument:
    meta = parse_filename(html_path)
    doc = ParsedDocument(
        source_file=html_path,
        company=meta["company"],
        form_type=meta["form_type"]
    )

    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    # 1. ixbrl-parse 提取数值数据
    try:
        from ixbrlparse import IXBRL
        filing = IXBRL.open(html_path)
        numeric_elements = extract_numeric_data(filing)
        doc.elements.extend(numeric_elements)
    except Exception as e:
        doc.elements.append(ParsedElement(
            element_type="text",
            content=f"[XBRL parsing failed: {e}]",
            section="ERROR"
        ))

    # 2. BeautifulSoup 提取文字段落
    text_elements = extract_text_elements(html)
    doc.elements.extend(text_elements)

    return doc


def parse_all():
    raw_path = Path(RAW_DIR)
    Path(PROCESSED_DIR).mkdir(parents=True, exist_ok=True)

    html_files = list(raw_path.glob("**/*.html")) + list(raw_path.glob("**/*.htm"))
    if not html_files:
        print(f"[!] No HTML files found in {RAW_DIR}")
        return

    print(f"[Info] Found {len(html_files)} files")

    for html_file in tqdm(html_files, desc="Parsing"):
        output_path = get_output_path(str(html_file))

        try:
            start = time.time()
            result = parse_file(str(html_file))
            result.to_json(output_path)

            tables = sum(1 for e in result.elements if e.element_type == "table")
            texts = sum(1 for e in result.elements if e.element_type == "text")
            elapsed = time.time() - start

            tqdm.write(f"[✓] {html_file.name} → tables:{tables} texts:{texts} time:{elapsed:.1f}s")
        except Exception as e:
            tqdm.write(f"[✗] {html_file.name} failed: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        html_file = sys.argv[1]
        result = parse_file(html_file)
        out = get_output_path(html_file)
        result.to_json(out)
        print(f"[✓] Output: {out}")
        print(f"    Tables: {sum(1 for e in result.elements if e.element_type == 'table')}")
        print(f"    Texts: {sum(1 for e in result.elements if e.element_type == 'text')}")
    else:
        parse_all()