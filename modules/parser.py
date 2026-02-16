"""
TechFilings - Parser 模块
解析下载的HTML财报文件，提取结构化内容
"""

import os
import re
import json
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RAW_DIR, PROCESSED_DIR


# 10-K和10-Q的标准章节
SEC_ITEMS = {
    "10-K": [
        ("Item 1", "Business"),
        ("Item 1A", "Risk Factors"),
        ("Item 1B", "Unresolved Staff Comments"),
        ("Item 2", "Properties"),
        ("Item 3", "Legal Proceedings"),
        ("Item 4", "Mine Safety Disclosures"),
        ("Item 5", "Market for Registrant's Common Equity"),
        ("Item 6", "Selected Financial Data"),
        ("Item 7", "Management's Discussion and Analysis"),
        ("Item 7A", "Quantitative and Qualitative Disclosures About Market Risk"),
        ("Item 8", "Financial Statements"),
        ("Item 9", "Changes in and Disagreements with Accountants"),
        ("Item 9A", "Controls and Procedures"),
        ("Item 9B", "Other Information"),
        ("Item 10", "Directors, Executive Officers and Corporate Governance"),
        ("Item 11", "Executive Compensation"),
        ("Item 12", "Security Ownership"),
        ("Item 13", "Certain Relationships and Related Transactions"),
        ("Item 14", "Principal Accountant Fees and Services"),
        ("Item 15", "Exhibits and Financial Statement Schedules"),
    ],
    "10-Q": [
        ("Item 1", "Financial Statements"),
        ("Item 2", "Management's Discussion and Analysis"),
        ("Item 3", "Quantitative and Qualitative Disclosures About Market Risk"),
        ("Item 4", "Controls and Procedures"),
        ("Item 1A", "Risk Factors"),
        ("Item 2", "Unregistered Sales of Equity Securities"),
        ("Item 5", "Other Information"),
        ("Item 6", "Exhibits"),
    ]
}


class SECParser:
    """解析SEC财报文件"""
    
    def __init__(self):
        self.raw_dir = RAW_DIR
        self.processed_dir = PROCESSED_DIR
        
    def clean_text(self, text: str) -> str:
        """
        清理提取的文本
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        if not text:
            return ""
        
        # 替换多个空白字符为单个空格
        text = re.sub(r'\s+', ' ', text)
        
        # 去除首尾空白
        text = text.strip()
        
        # 去除特殊字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
        
        return text
    
    def extract_text_from_html(self, html_content: str) -> str:
        """
        从HTML中提取纯文本
        
        Args:
            html_content: HTML内容
            
        Returns:
            提取的纯文本
        """
        soup = BeautifulSoup(html_content, 'lxml')
        
        # 移除script和style标签
        for tag in soup(['script', 'style', 'meta', 'link', 'head']):
            tag.decompose()
        
        # 移除隐藏元素
        for tag in soup.find_all(style=re.compile(r'display\s*:\s*none', re.I)):
            tag.decompose()
        
        # 获取文本
        text = soup.get_text(separator=' ')
        
        return self.clean_text(text)
    
    def find_item_sections(self, text: str, filing_type: str) -> List[Dict]:
        """
        识别文档中的Item章节
        
        Args:
            text: 文档文本
            filing_type: 文件类型 (10-K 或 10-Q)
            
        Returns:
            章节列表
        """
        sections = []
        
        # 获取对应的Item列表
        items = SEC_ITEMS.get(filing_type, SEC_ITEMS["10-K"])
        
        # 构建正则表达式来匹配Item标题
        # 匹配模式如: "Item 1." "Item 1A." "ITEM 1 -" 等
        for item_num, item_name in items:
            # 创建灵活的匹配模式
            pattern = re.compile(
                rf'({re.escape(item_num)}[\.\s\-:]+\s*{re.escape(item_name)})',
                re.IGNORECASE
            )
            
            matches = list(pattern.finditer(text))
            
            for match in matches:
                sections.append({
                    "item": item_num,
                    "title": item_name,
                    "start_pos": match.start(),
                    "matched_text": match.group(1)
                })
        
        # 按位置排序
        sections.sort(key=lambda x: x["start_pos"])
        
        # 去重（同一个Item可能匹配多次，只保留第一次）
        seen_items = set()
        unique_sections = []
        for section in sections:
            if section["item"] not in seen_items:
                seen_items.add(section["item"])
                unique_sections.append(section)
        
        return unique_sections
    
    def split_into_sections(self, text: str, sections: List[Dict]) -> List[Dict]:
        """
        根据识别的章节位置，将文本分割成段落
        
        Args:
            text: 完整文本
            sections: 章节信息列表
            
        Returns:
            带内容的章节列表
        """
        if not sections:
            # 如果没有识别到章节，将整个文档作为一个section
            return [{
                "item": "Full Document",
                "title": "Complete Filing",
                "content": text
            }]
        
        result = []
        
        for i, section in enumerate(sections):
            start = section["start_pos"]
            
            # 结束位置是下一个章节的开始，或者文档末尾
            if i + 1 < len(sections):
                end = sections[i + 1]["start_pos"]
            else:
                end = len(text)
            
            content = text[start:end].strip()
            
            # 只保留有实质内容的章节
            if len(content) > 100:
                result.append({
                    "item": section["item"],
                    "title": section["title"],
                    "content": content
                })
        
        return result
    
    def parse_filing(self, file_path: str) -> Dict:
        """
        解析单个财报文件
        
        Args:
            file_path: HTML文件路径
            
        Returns:
            结构化的财报内容
        """
        print(f"正在解析: {file_path}")
        
        # 从文件名提取信息
        filename = os.path.basename(file_path)
        parts = filename.replace('.html', '').split('_')
        
        if len(parts) >= 3:
            ticker = parts[0]
            filing_type = parts[1]
            filing_date = parts[2]
        else:
            ticker = "Unknown"
            filing_type = "10-K"
            filing_date = "Unknown"
        
        # 读取文件
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                html_content = f.read()
        
        # 提取文本
        text = self.extract_text_from_html(html_content)
        
        # 识别章节
        sections = self.find_item_sections(text, filing_type)
        
        # 分割内容
        section_contents = self.split_into_sections(text, sections)
        
        result = {
            "filename": filename,
            "file_path": file_path,
            "ticker": ticker,
            "filing_type": filing_type,
            "filing_date": filing_date,
            "total_length": len(text),
            "num_sections": len(section_contents),
            "sections": section_contents
        }
        
        print(f"  - 提取了 {len(text)} 字符, {len(section_contents)} 个章节")
        
        return result
    
    def parse_all(self) -> List[Dict]:
        """
        解析所有下载的财报
        
        Returns:
            所有解析结果的列表
        """
        all_results = []
        
        # 遍历raw目录下的所有公司文件夹
        for ticker_dir in os.listdir(self.raw_dir):
            ticker_path = os.path.join(self.raw_dir, ticker_dir)
            
            if not os.path.isdir(ticker_path):
                continue
            
            print(f"\n{'='*50}")
            print(f"处理公司: {ticker_dir}")
            print(f"{'='*50}")
            
            # 遍历该公司的所有HTML文件
            for filename in os.listdir(ticker_path):
                if filename.endswith('.html'):
                    file_path = os.path.join(ticker_path, filename)
                    result = self.parse_filing(file_path)
                    all_results.append(result)
        
        # 保存解析结果
        self._save_parsed_results(all_results)
        
        return all_results
    
    def _save_parsed_results(self, results: List[Dict]) -> None:
        """保存解析结果到JSON文件"""
        os.makedirs(self.processed_dir, exist_ok=True)
        
        output_path = os.path.join(self.processed_dir, "parsed_filings.json")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n解析结果已保存: {output_path}")


def main():
    """主函数"""
    print("TechFilings - 财报解析工具")
    print("="*50)
    
    parser = SECParser()
    results = parser.parse_all()
    
    # 统计
    total_sections = sum(r["num_sections"] for r in results)
    total_chars = sum(r["total_length"] for r in results)
    
    print(f"\n{'='*50}")
    print(f"解析完成!")
    print(f"文件数量: {len(results)}")
    print(f"总章节数: {total_sections}")
    print(f"总字符数: {total_chars:,}")
    print(f"{'='*50}")
    
    return results


if __name__ == "__main__":
    main()
