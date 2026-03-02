"""
SEC EDGAR iXBRL Parser (10-K / 10-Q)

使用 ixbrl-parse 提取结构化财务数据
使用 BeautifulSoup 提取文字段落

数据路径：
  输入: data/raw/[公司名]/*.html
  输出: data/processed/*_parsed.json

安装依赖：
  pip install ixbrlparse beautifulsoup4 lxml tqdm
"""

import re
import json
import time
import warnings
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from tqdm import tqdm

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# ─────────────────────────────────────────────
# 路径配置
# ─────────────────────────────────────────────

DATA_DIR = "data"
RAW_DIR = f"{DATA_DIR}/raw"
PROCESSED_DIR = f"{DATA_DIR}/processed"

# US-GAAP 指标名 → 人类可读名称
GAAP_LABELS = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": "Revenue",
    "Revenues": "Revenue",
    "NetIncomeLoss": "Net Income",
    "OperatingIncomeLoss": "Operating Income",
    "GrossProfit": "Gross Profit",
    "CostsAndExpenses": "Total Costs and Expenses",
    "ResearchAndDevelopmentExpense": "R&D Expense",
    "SellingGeneralAndAdministrativeExpense": "SG&A Expense",
    "IncomeTaxExpenseBenefit": "Income Tax",
    "EarningsPerShareBasic": "EPS Basic",
    "EarningsPerShareDiluted": "EPS Diluted",
    "Assets": "Total Assets",
    "Liabilities": "Total Liabilities",
    "StockholdersEquity": "Stockholders Equity",
    "CashAndCashEquivalentsAtCarryingValue": "Cash and Equivalents",
    "LongTermDebt": "Long Term Debt",
    "CommonStockSharesOutstanding": "Shares Outstanding",
    "NetCashProvidedByUsedInOperatingActivities": "Operating Cash Flow",
    "NetCashProvidedByUsedInInvestingActivities": "Investing Cash Flow",
    "NetCashProvidedByUsedInFinancingActivities": "Financing Cash Flow",
    "AllocatedShareBasedCompensationExpense": "Stock-Based Compensation",
    "AmortizationOfIntangibleAssets": "Amortization of Intangibles",
    "DepreciationDepletionAndAmortization": "D&A",
    "InterestExpense": "Interest Expense",
}

# 报表分组关键词
STATEMENT_GROUPS = {
    "Income Statement": [
        "Revenue", "NetIncomeLoss", "OperatingIncomeLoss", "GrossProfit",
        "CostsAndExpenses", "ResearchAndDevelopmentExpense",
        "SellingGeneralAndAdministrativeExpense", "IncomeTaxExpenseBenefit",
        "EarningsPerShareBasic", "EarningsPerShareDiluted",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "IncomeLossFromContinuingOperations",
    ],
    "Balance Sheet": [
        "Assets", "Liabilities", "StockholdersEquity",
        "CashAndCashEquivalentsAtCarryingValue", "LongTermDebt",
        "CommonStockSharesOutstanding",
    ],
    "Cash Flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInInvestingActivities",
        "NetCashProvidedByUsedInFinancingActivities",
    ],
    
}


# ─────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────

@dataclass
class ParsedElement:
    element_type: str   # "table" | "text" | "section_header"
    content: str
    section: str = ""
    confidence: str = "high"
    error: Optional[str] = None


@dataclass
class ParsedDocument:
    source_file: str
    company: str = ""
    form_type: str = ""
    elements: list = field(default_factory=list)

    def to_json(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "source": self.source_file,
            "company": self.company,
            "form_type": self.form_type,
            "total_elements": len(self.elements),
            "elements": [
                {
                    "type": e.element_type,
                    "section": e.section,
                    "content": e.content,
                    "confidence": e.confidence,
                    "error": e.error,
                }
                for e in self.elements
            ]
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# iXBRL 数值数据提取
# ─────────────────────────────────────────────

def extract_segment_label(dims: list) -> str:
    labels = []
    for dim in dims:
        value = dim.get("value", "")
        dimension = dim.get("dimension", "")
        if ":" in value:
            value = value.split(":")[-1]
        value = value.replace("Member", "").replace("Segment", "")
        value = re.sub(r'([A-Z])', r' \1', value).strip()
        # 跳过合并维度，只取业务分部维度
        if "ConsolidationItems" in dimension or "StatementEquityComponents" in dimension:
            continue
        if value and value not in ["Operating Segments", "Consolidation Items"]:
            labels.append(value)
    return labels[0] if labels else ""


def extract_numeric_data(filing) -> list[ParsedElement]:
    """
    从 ixbrl-parse 的 numeric 数据生成表格 chunks
    按报表类型分组，每组生成一个 Markdown 表格
    """
    elements = []

    # 按指标名分组
    by_name: dict = {}
    for item in filing.numeric:
        name = item.name
        if name not in by_name:
            by_name[name] = []
        by_name[name].append(item)

    # 按报表类型分组生成表格
    for statement_name, metric_names in STATEMENT_GROUPS.items():
        rows = []

        for metric_name in metric_names:
            if metric_name not in by_name:
                continue

            items = by_name[metric_name]
            label = GAAP_LABELS.get(metric_name, metric_name)

            # 只取没有 segment 维度的数据（合并报表）
            consolidated = [i for i in items if not i.context.segments]

            # 按时间段排序
            consolidated.sort(
            key=lambda x: x.context.startdate or x.context.instant or x.context.enddate,
            reverse=True)

            if not consolidated:
                continue

            # 取最近4个时间段
            for item in consolidated[:8]:
                ctx = item.context
                if ctx.startdate:
                    period = f"{ctx.startdate} to {ctx.enddate}"
                elif ctx.instant:
                    period = str(ctx.instant)
                elif ctx.enddate:
                    period = str(ctx.enddate)
                else:
                    period = "N/A"

                rows.append({
                    "metric": label,
                    "period": period,
                    "value": item.value,
                    "unit": getattr(item, "unit", "USD"),
                })

        if not rows:
            continue

        # 转成 Markdown 表格
        # 收集所有时间段
        periods = list(dict.fromkeys(r["period"] for r in rows))[:4]
        metrics = list(dict.fromkeys(r["metric"] for r in rows))

        # 构建表格
        header = "| Metric | " + " | ".join(periods) + " |"
        separator = "| --- | " + " | ".join("---" for _ in periods) + " |"

        table_rows = []
        for metric in metrics:
            metric_data = {r["period"]: r["value"] for r in rows if r["metric"] == metric}
            values = []
            for period in periods:
                val = metric_data.get(period, "")
                if val != "" and isinstance(val, (int, float)):
                    # 格式化数字
                    if abs(val) >= 1_000_000:
                        val = f"${val/1_000_000:.1f}M"
                    else:
                        val = f"{val:,.4f}".rstrip("0").rstrip(".")
                values.append(str(val))
            table_rows.append(f"| {metric} | " + " | ".join(values) + " |")

        content = "\n".join([header, separator] + table_rows)
        elements.append(ParsedElement(
            element_type="table",
            content=content,
            section=statement_name,
            confidence="high"
        ))

    # 业务分部数据单独一个表格
    segment_elements = extract_segment_data(by_name)
    elements.extend(segment_elements)

    return elements


def extract_segment_data(by_name: dict) -> list[ParsedElement]:
    """提取业务分部数据"""
    EXCLUDE_FROM_SEGMENTS = {
    "Stockholders Equity", "Shares Outstanding", "Total Assets",
    "Total Liabilities", "Cash and Equivalents", "Long Term Debt"
    }
    elements = []
    segment_rows = []

    for metric_name, items in by_name.items():
        label = GAAP_LABELS.get(metric_name, metric_name)
        segmented = [i for i in items if i.context.segments]

        if label in EXCLUDE_FROM_SEGMENTS:
            continue
        if metric_name not in GAAP_LABELS:
            continue
        for item in segmented:
            if item.context.instant and not item.context.startdate:
                continue
            seg_label = extract_segment_label(item.context.segments)
            if not seg_label:
                continue
            ctx = item.context

            if ctx.startdate:
                period = f"{ctx.startdate} to {ctx.enddate}"
            elif ctx.instant:
                period = str(ctx.instant)
            elif ctx.enddate:
                period = str(ctx.enddate)
            else:
                period = "N/A"

            segment_rows.append({
                "metric": label,
                "segment": seg_label,
                "period": period,
                "value": item.value,
            })

    if not segment_rows:
        return elements

    # 按 metric + segment 分组
    from collections import Counter
    period_counts = Counter(r["period"] for r in segment_rows)
    periods = [p for p, _ in period_counts.most_common(4)]
    periods.sort(reverse=True)

    # 过滤掉没有任何数据的时间段
    periods = [
        p for p in periods
        if any(
            r["value"] not in [None, 0, ""]
            for r in segment_rows
            if r["period"] == p
        )
    ]

    combinations = list(dict.fromkeys(
        (r["metric"], r["segment"]) for r in segment_rows
    ))

    header = "| Metric | Segment | " + " | ".join(periods) + " |"
    separator = "| --- | --- | " + " | ".join("---" for _ in periods) + " |"
    rows = []

    for metric, segment in combinations:  
        data = {
            r["period"]: r["value"]
            for r in segment_rows
            if r["metric"] == metric and r["segment"] == segment
        }
        values = []
        for period in periods:
            val = data.get(period, "")
            if val != "" and isinstance(val, (int, float)):
                val = f"${val/1_000_000:.1f}M" if abs(val) >= 1_000_000 else f"{val:,.0f}"
            values.append(str(val))

        if not any(v for v in values if v and v not in ["", "0"]):
            continue
        # 加这一行：跳过未翻译的 GAAP 指标名
        if metric not in GAAP_LABELS.values():
            continue
        rows.append(f"| {metric} | {segment} | " + " | ".join(values) + " |")

    if rows:
        content = "\n".join([header, separator] + rows)
        elements.append(ParsedElement(
            element_type="table",
            content=content,
            section="Business Segments",
            confidence="high"
        ))

    return elements


# ─────────────────────────────────────────────
# 文字段落提取（BeautifulSoup）
# ─────────────────────────────────────────────

def extract_text_elements(html: str) -> list[ParsedElement]:
    """去掉 ix: 标签，提取文字段落"""
    soup = BeautifulSoup(html, "lxml")

    # 去掉 script/style/head
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

    for tag in soup.find_all(["p", "div", "span"]):
        # 跳过表格内的元素
        if tag.find_parent("table"):
            continue
        # 跳过有子块级元素的（只取叶节点文字）
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
        elif len(text) > 50:
            elements.append(ParsedElement(
                element_type="text",
                content=text,
                section=current_section
            ))

    return elements


def _is_section_header(text: str, tag) -> bool:
    """判断是否为章节标题"""
    # SEC 标准章节模式
    patterns = [
        r"^ITEM\s+\d+[A-Z]?\.",
        r"^PART\s+[IVX]+",
        r"^NOTE\s+\d+",
    ]
    for pattern in patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True

    # 短文字 + 全大写
    if len(text) < 100 and text.isupper():
        return True

    return False


# ─────────────────────────────────────────────
# 主解析器
# ─────────────────────────────────────────────

def parse_filename(filename: str) -> dict:
    stem = Path(filename).stem
    parts = stem.split("_")
    return {
        "company": parts[0] if len(parts) > 0 else "",
        "form_type": parts[1] if len(parts) > 1 else "",
    }


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
            content=f"[XBRL解析失败: {e}]",
            section="ERROR"
        ))

    # 2. BeautifulSoup 提取文字段落
    text_elements = extract_text_elements(html)
    doc.elements.extend(text_elements)

    return doc


# ─────────────────────────────────────────────
# 批量处理
# ─────────────────────────────────────────────

def get_output_path(html_path: str) -> str:
    filename = Path(html_path).stem
    return str(Path(PROCESSED_DIR) / f"{filename}_parsed.json")


def parse_all():
    raw_path = Path(RAW_DIR)
    Path(PROCESSED_DIR).mkdir(parents=True, exist_ok=True)

    html_files = list(raw_path.glob("*/*.html")) + list(raw_path.glob("*/*.htm"))
    if not html_files:
        print(f"[!] 未在 {RAW_DIR} 找到 HTML 文件")
        return

    print(f"[信息] 共找到 {len(html_files)} 个文件")

    for html_file in tqdm(html_files, desc="解析进度"):
        output_path = get_output_path(str(html_file))

        try:
            start = time.time()
            result = parse_file(str(html_file))
            result.to_json(output_path)

            tables = sum(1 for e in result.elements if e.element_type == "table")
            texts = sum(1 for e in result.elements if e.element_type == "text")
            elapsed = time.time() - start

            tqdm.write(f"[✓] {html_file.name} → 表格:{tables} 文字:{texts} 耗时:{elapsed:.1f}s")
        except Exception as e:
            tqdm.write(f"[✗] {html_file.name} 失败: {e}")


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        html_file = sys.argv[1]
        result = parse_file(html_file)
        out = get_output_path(html_file)
        result.to_json(out)
        print(f"[✓] 输出: {out}")
        print(f"    表格: {sum(1 for e in result.elements if e.element_type == 'table')}")
        print(f"    文字: {sum(1 for e in result.elements if e.element_type == 'text')}")
    else:
        parse_all()