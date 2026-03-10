"""
TechFilings - Loader 模块
从SEC EDGAR下载10-K和10-Q文件
"""

import os
import json
import time
import requests
from pathlib import Path
from typing import List, Dict, Optional

# 导入配置
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from techfilings.backend.config import (
    SEC_EDGAR_API, 
    USER_AGENT, 
    COMPANIES, 
    FILING_TYPES, 
    FILINGS_PER_TYPE,
    RAW_DIR
)


class SECLoader:
    """从SEC EDGAR下载财报文件"""
    
    def __init__(self):
        self.headers = {
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "gzip, deflate"
        }
        self.base_url = SEC_EDGAR_API
        
    def get_company_filings(self, cik: str) -> Dict:
        """
        获取公司的所有filing列表
        
        Args:
            cik: 公司的CIK代码
            
        Returns:
            SEC API返回的filing数据
        """
        # 移除CIK前面的0
        cik_clean = cik.lstrip("0")
        url = f"{self.base_url}/submissions/CIK{cik.zfill(10)}.json"
        
        print(f"正在获取filing列表: {url}")
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        # SEC有访问频率限制，每秒最多10次请求
        time.sleep(0.1)
        
        return response.json()
    
    def filter_filings(self, filings_data: Dict, filing_types: List[str], limit: int) -> List[Dict]:
        """
        筛选指定类型的filing
        
        Args:
            filings_data: SEC API返回的完整数据
            filing_types: 要筛选的filing类型，如["10-K", "10-Q"]
            limit: 每种类型最多返回多少个
            
        Returns:
            筛选后的filing列表
        """
        recent_filings = filings_data.get("filings", {}).get("recent", {})
        
        if not recent_filings:
            print("警告: 没有找到recent filings数据")
            return []
        
        # 获取各个字段的列表
        forms = recent_filings.get("form", [])
        accession_numbers = recent_filings.get("accessionNumber", [])
        filing_dates = recent_filings.get("filingDate", [])
        primary_documents = recent_filings.get("primaryDocument", [])
        
        results = []
        type_counts = {t: 0 for t in filing_types}
        
        for i in range(len(forms)):
            form_type = forms[i]
            
            # 检查是否是我们要的类型
            if form_type in filing_types and type_counts[form_type] < limit:
                results.append({
                    "form_type": form_type,
                    "accession_number": accession_numbers[i],
                    "filing_date": filing_dates[i],
                    "primary_document": primary_documents[i]
                })
                type_counts[form_type] += 1
            
            # 如果所有类型都达到限制，停止
            if all(count >= limit for count in type_counts.values()):
                break
        
        return results
    
    def get_primary_htm(self, cik: str, accession_number: str, primary_document: str) -> str:
        """
        找到 filing 里真正的人类可读 HTM 文件
        如果 primary_document 已经是正确的就直接返回
        """
        # XBRL 特征：文件名里有 xbrl 或者是 R1.htm 这种
        if not any(x in primary_document.lower() for x in ['xbrl', 'r1.htm', 'r2.htm']):
            return primary_document  # 已经是正确的

        # 获取 filing 的完整文件列表
        accession_clean = accession_number.replace("-", "")
        cik_clean = cik.lstrip("0")
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession_clean}/{accession_clean}-index.json"

        try:
            response = requests.get(index_url, headers=self.headers)
            files = response.json().get("directory", {}).get("item", [])

            for f in files:
                name = f.get("name", "")
                # 找公司名开头的 .htm 文件（如 nvda-20250126.htm）
                if name.endswith(".htm") and not name.startswith("R") and "xbrl" not in name.lower():
                    return name
        except Exception as e:
            print(f"获取文件列表失败: {e}")

        return primary_document  # 找不到就用原来的
    
    def download_filing(self, cik: str, accession_number: str, primary_document: str, save_path: str) -> bool:
        """
        下载单个filing文件
        
        Args:
            cik: 公司CIK
            accession_number: Filing的accession number
            primary_document: 主文档文件名
            save_path: 保存路径
            
        Returns:
            是否下载成功
        """
        # 构建URL
        accession_clean = accession_number.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession_clean}/{primary_document}"
        
        print(f"正在下载: {url}")
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 保存文件
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            
            print(f"已保存: {save_path}")
            
            # 遵守SEC的访问频率限制
            time.sleep(0.1)
            
            return True
            
        except Exception as e:
            print(f"下载失败: {e}")
            return False
    
    def download_company_filings(self, company_name: str, company_info: Dict) -> List[Dict]:
        """
        下载一家公司的所有目标filing
        
        Args:
            company_name: 公司名称
            company_info: 公司信息（包含cik和ticker）
            
        Returns:
            下载结果列表
        """
        cik = company_info["cik"]
        ticker = company_info["ticker"]
        
        print(f"\n{'='*50}")
        print(f"处理公司: {company_name} ({ticker})")
        print(f"{'='*50}")
        
        # 获取filing列表
        try:
            filings_data = self.get_company_filings(cik)
        except Exception as e:
            print(f"获取filing列表失败: {e}")
            return []
        
        # 筛选目标filing
        target_filings = self.filter_filings(filings_data, FILING_TYPES, FILINGS_PER_TYPE)
        
        if not target_filings:
            print("没有找到目标filing")
            return []
        
        print(f"找到 {len(target_filings)} 个目标filing")
        
        # 下载每个filing
        results = []
        for filing in target_filings:
            # 构建保存路径
            filename = f"{ticker}_{filing['form_type']}_{filing['filing_date']}.html"
            save_path = os.path.join(RAW_DIR, ticker, filename)
            
            # 找正确的 HTM 文件
            primary_doc = self.get_primary_htm(
                cik, 
                filing["accession_number"], 
                filing["primary_document"]
            )

            success = self.download_filing(
                cik=cik,
                accession_number=filing["accession_number"],
                primary_document=primary_doc,  
                save_path=save_path
            )
            
            results.append({
                **filing,
                "company": company_name,
                "ticker": ticker,
                "local_path": save_path if success else None,
                "download_success": success
            })
        
        return results
    
    def download_all(self) -> List[Dict]:
        """
        下载所有目标公司的filing
        
        Returns:
            所有下载结果
        """
        all_results = []
        
        for company_name, company_info in COMPANIES.items():
            results = self.download_company_filings(company_name, company_info)
            all_results.extend(results)
        
        # 保存下载记录
        self._save_download_log(all_results)
        
        return all_results
    
    def _save_download_log(self, results: List[Dict]) -> None:
        """保存下载日志"""
        log_path = os.path.join(RAW_DIR, "download_log.json")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n下载日志已保存: {log_path}")


def main():
    """主函数"""
    print("TechFilings - 财报下载工具")
    
    loader = SECLoader()
    results = loader.download_all()
    
    # 统计结果
    success_count = sum(1 for r in results if r["download_success"])
    total_count = len(results)
    print(f"下载完成: {success_count}/{total_count} 成功")
    
    return results


if __name__ == "__main__":
    main()
