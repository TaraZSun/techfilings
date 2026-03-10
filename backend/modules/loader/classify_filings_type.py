"""
TechFilings - File Classifier Module

Classifies downloaded SEC filings into categories:
ixbrl, html, xml, txt, pdf, other
"""

import os
import logging
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import CLASSIFED_RAW_FILINGS
logger = logging.getLogger(__name__)


def classify_filing(file_path: str) -> str:
    """
    Classify a downloaded SEC filing based on extension and content.

    Args:
        file_path: Path to the downloaded filing

    Returns:
        One of: 'ixbrl', 'html', 'xml', 'txt', 'pdf', 'other'
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return "pdf"
    if ext == ".xml":
        return "xml"
    if ext == ".txt":
        return "txt"

    if ext in (".htm", ".html"):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(5000)  # only read first 5000 chars for speed
            if "ix:" in content or "xmlns:ix" in content:
                return "ixbrl"
            return "html"
        except Exception as e:
            logger.warning(f"Could not read file {file_path}: {e}")
            return "other"

    return "other"

def classify_and_move(file_path: str, ticker: str) -> str:
    """
    Classify a filing and move it to the appropriate subdirectory.

    Args:
        file_path: Path to the downloaded filing
        ticker: Company ticker (e.g. NVDA)

    Returns:
        New file path after moving
    """
    category = classify_filing(file_path)
    target_dir = os.path.join(CLASSIFED_RAW_FILINGS, ticker, category)
    os.makedirs(target_dir, exist_ok=True)

    filename = os.path.basename(file_path)
    new_path = os.path.join(target_dir, filename)

    os.rename(file_path, new_path)
    logger.info(f"Classified as '{category}': {filename} → {new_path}")

    return new_path

def count_by_category(base_dir: str) -> dict:
    """
    Count filings by category in a base directory.

    Args:
        base_dir: Base directory (e.g. data/raw/NVDA)

    Returns:
        Dict of category -> count
    """
    categories = ["ixbrl", "html", "xml", "txt", "pdf", "other"]
    counts = {cat: 0 for cat in categories}

    for cat in categories:
        cat_dir = os.path.join(base_dir, cat)
        if os.path.exists(cat_dir):
            counts[cat] = len([f for f in os.listdir(cat_dir) if os.path.isfile(os.path.join(cat_dir, f))])

    return counts