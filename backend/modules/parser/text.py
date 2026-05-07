"""
TechFilings - Text Extractor
使用 BeautifulSoup 从 SEC HTML 文件提取文字段落
"""

import re
import warnings
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from modules.parser.models import ParsedElement

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Skip these sections' content (cover page, legal disclaimers, etc.)
SKIP_SECTIONS = {
    "UNITED STATES SECURITIES AND EXCHANGE COMMISSION",
    "ADVANCED MICRO DEVICES, INC .",
    "NVIDIA CORPORATION",
    "PALANTIR TECHNOLOGIES INC .",
    "UNKNOWN",
}

# 跳过包含这些关键词的段落（法律样板文字）
SKIP_PATTERNS = [
    r"^indicate by check mark",
    r"^securities registered pursuant",
    r"^exact name of registrant",
    r"^registrant.s telephone number",
    r"^former name, former address",
    r"^\(state or other jurisdiction",
    r"^commission file number",
    r"^i\.r\.s\. employer",
    r"^address of principal",
]

SKIP_REGEX = re.compile("|".join(SKIP_PATTERNS), re.IGNORECASE)


def extract_text_elements(html: str) -> list[ParsedElement]:
    """提取文字段落，去重、过滤无用内容"""
    soup = BeautifulSoup(html, "lxml")

    # 去掉 script/style/head/meta
    for tag in soup(["script", "style", "head", "meta"]):
        tag.decompose()

    # 去掉 ix: 命名空间标签，保留内容
    for tag in soup.find_all(True):
        if ":" in tag.name:
            tag.unwrap()

    # 去掉 display:none 的元素（XBRL hidden section）
    for tag in soup.find_all(style=re.compile(r'display\s*:\s*none', re.I)):
        tag.decompose()

    elements = []
    current_section = "UNKNOWN"
    seen_texts = set()  # 用于去重

    # 只提取 p 和 div，去掉 span 避免重复
    for tag in soup.find_all(["p", "div"]):
        # 跳过表格内的元素
        if tag.find_parent("table"):
            continue

        # 只取叶节点（没有子 p/div/table 的）
        if tag.find(["p", "div", "table"]):
            continue

        text = tag.get_text(separator=" ", strip=True)
        text = re.sub(r'\s+', ' ', text)

        if not text or len(text) < 20:
            continue

        # 检测章节标题
        if _is_section_header(text, tag):
            current_section = text[:100]
            elements.append(ParsedElement(
                element_type="section_header",
                content=text,
                section=current_section
            ))
            continue

        # 跳过无用 section
        if current_section in SKIP_SECTIONS:
            continue

        # 跳过法律样板文字
        if SKIP_REGEX.match(text):
            continue

        if _is_noise(text):
            continue
        

        # 去重：跳过已经出现过的文字
        text_key = text[:200]
        if text_key in seen_texts:
            continue
        seen_texts.add(text_key)

        elements.append(ParsedElement(
            element_type="text",
            content=text,
            section=current_section
        ))

    return elements


def _is_section_header(text: str, tag) -> bool:
    """Find section headers based on common patterns and formatting"""
    standard_patterns = [
        r"^ITEM\s+\d+[A-Z]?\.",
        r"^PART\s+[IVX]+",
        r"^NOTE\s+\d+",
    ]
    if any(re.match(pattern, text, re.IGNORECASE) for pattern in standard_patterns):
        return True

    # If text is short and bold, it might be a section header
    is_bold = tag.find(["b","strong"]) is not None or "font-weight:bold" in str(tag.get('style', ''))
    if is_bold and len(text) < 120:
        return True

    return False

def _is_noise(text:str)->bool:
    # segments only with numbers or punctuation
    if re.match(r'^[0-9\.\-\s\(\)\$%,]+$', text):
        return True
    # too short and no alphabetic characters
    if len(text)<10 and not any(word.isalpha() for word in text):
        return True