"""
TechFilings - Parser Data Models
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


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