"""
TechFilings - Numeric Data Extractor
This module focuses on extracting and structuring numeric data from SEC filings.
"""

import re
from collections import Counter
from modules.parser.models import ParsedElement

import json
import os
_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financial_constants.json")
with open(_path) as f:
    _data = json.load(f)

GAAP_LABELS = _data["gaap_labels"]
STATEMENT_GROUPS = _data["statement_groups"]
EXCLUDE_FROM_SEGMENTS = set(_data["exclude_from_segments"])

def extract_segment_label(dims: list) -> str:
    labels = []
    for dim in dims:
        value = dim.get("value", "")
        dimension = dim.get("dimension", "")
        if ":" in value:
            value = value.split(":")[-1]
        value = value.replace("Member", "").replace("Segment", "")
        value = re.sub(r'([A-Z])', r' \1', value).strip()
        if "ConsolidationItems" in dimension or "StatementEquityComponents" in dimension:
            continue
        if value and value not in ["Operating Segments", "Consolidation Items"]:
            labels.append(value)
    return labels[0] if labels else ""


def extract_numeric_data(filing) -> list[ParsedElement]:
    elements = []
    by_name: dict = {}

    for item in filing.numeric:
        name = item.name
        if name not in by_name:
            by_name[name] = []
        by_name[name].append(item)

    for statement_name, metric_names in STATEMENT_GROUPS.items():
        rows = []

        for metric_name in metric_names:
            if metric_name not in by_name:
                continue

            items = by_name[metric_name]
            label = GAAP_LABELS.get(metric_name, metric_name)
            consolidated = [i for i in items if not i.context.segments]
            consolidated.sort(
                key=lambda x: x.context.startdate or x.context.instant or x.context.enddate,
                reverse=True
            )

            if not consolidated:
                continue

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

        periods = list(dict.fromkeys(r["period"] for r in rows))[:4]
        metrics = list(dict.fromkeys(r["metric"] for r in rows))

        header = "| Metric | " + " | ".join(periods) + " |"
        separator = "| --- | " + " | ".join("---" for _ in periods) + " |"

        table_rows = []
        for metric in metrics:
            metric_data = {r["period"]: r["value"] for r in rows if r["metric"] == metric}
            values = []
            for period in periods:
                val = metric_data.get(period, "")
                if val != "" and isinstance(val, (int, float)):
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

    segment_elements = extract_segment_data(by_name)
    elements.extend(segment_elements)

    return elements


def extract_segment_data(by_name: dict) -> list[ParsedElement]:
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

    period_counts = Counter(r["period"] for r in segment_rows)
    periods = [p for p, _ in period_counts.most_common(4)]
    periods.sort(reverse=True)
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