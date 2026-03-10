"""
TechFilings - Loader Module

This module is responsible for downloading and managing SEC filings 
for the specified companies. It interacts with the SEC EDGAR API to 
obtain filing metadata, filters filings based on type and date, and 
downloads the primary HTML documents for the filings. The downloaded 
filings are saved locally, and a log of the download process is maintained.

"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import json
import time
import requests
import logging
from modules.loader.classify_filings_type import count_by_category, classify_and_move
from config import (  # noqa: E402
    SEC_EDGAR_API, 
    USER_AGENT, 
    COMPANIES, 
    FILING_TYPES, 
    RAW_DIR,
    START_YEAR,
    END_YEAR,
    CLASSIFED_RAW_FILINGS
)
logger = logging.getLogger(__name__)


class SECLoader:
    def __init__(self):
        self.headers = {
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "gzip, deflate"
        }
        self.base_url = SEC_EDGAR_API
        
    def get_company_filings(self, cik: str) -> dict:
        url = f"{self.base_url}/submissions/CIK{cik.zfill(10)}.json"
        logger.info(f"obtaining filings list: {url}")
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        time.sleep(0.1)
        return response.json()
    
    def filter_filings(self, filings_data: dict, 
                       filing_types: list[str], 
                       start_year: int, end_year:int) -> list[dict]:
        """
        Filter filings based on type and limit per type

        Args:
            filings_data: The raw filings data from SEC API
            filing_types: list of filing types to filter (e.g., ["10-K", "10-Q"])
            limit: Maximum number of filings to keep per type
        Returns:
            A list of filtered filings with required information
        """
        recent_filings = filings_data.get("filings", {}).get("recent", {})
        if not recent_filings:
            logger.warning("No recent filings found.")
            return []
        
        forms = recent_filings.get("form", [])
        accession_numbers = recent_filings.get("accessionNumber", [])
        filing_dates = recent_filings.get("filingDate", [])
        primary_documents = recent_filings.get("primaryDocument", [])
        
        results = []
        for i in range(len(forms)):
            form_type = forms[i]
            year = int(filing_dates[i][:4])
            if form_type in filing_types and start_year <= year <= end_year:
                results.append({
                    "form_type": form_type,
                    "accession_number": accession_numbers[i],
                    "filing_date": filing_dates[i],
                    "primary_document": primary_documents[i]
                })
        
        return results
    
    def get_primary_htm(self, cik: str, accession_number: str, primary_document: str) -> str:
        """
        Obtain the correct primary HTM document name for a filing, especially when the original primary document is an XBRL file or an index file.
        """
        if not any(x in primary_document.lower() for x in ['xbrl', 'r1.htm', 'r2.htm']):
            return primary_document 

        # Obtain the list of files in the filing directory
        accession_clean = accession_number.replace("-", "")
        cik_clean = cik.lstrip("0")
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession_clean}/{accession_clean}-index.json"

        try:
            response = requests.get(index_url, headers=self.headers)
            files = response.json().get("directory", {}).get("item", [])

            for f in files:
                name = f.get("name", "")
               
                if name.endswith(".htm") and not name.startswith("R") and "xbrl" not in name.lower():
                    return name
        except Exception as e:
            logger.warning(f"No filings obtained: {e}")

        return primary_document 
    
    def download_filing(self, cik: str, accession_number: str, 
                        primary_document: str, save_path: str) -> bool:
        accession_clean = accession_number.replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession_clean}/{primary_document}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            time.sleep(0.1)
            return True
            
        except Exception as e:
            logger.warning(f"Failure: {e}")
            return False
    
    def download_company_filings(self, company_name: str, company_info: dict) -> list[dict]:
        
        cik = company_info["cik"]
        ticker = company_info["ticker"]
        
        try:
            filings_data = self.get_company_filings(cik)
        except Exception as e:
            logger.warning(f"Failed to get filings for{company_name}: {e}")
            return []
        
       
        target_filings = self.filter_filings(filings_data, FILING_TYPES, START_YEAR, END_YEAR)
        if not target_filings:
            logger.warning("No target filings found after filtering.")
            return []
        
        logger.info(f"find {len(target_filings)} filings")
      
        results = []
        for filing in target_filings:
        
            filename = f"{ticker}_{filing['form_type']}_{filing['filing_date']}.html"
            save_path = os.path.join(RAW_DIR, ticker, filename)
       
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
            if success:
                save_path=classify_and_move(save_path, ticker)
        
            results.append({
                **filing,
                "company": company_name,
                "ticker": ticker,
                "local_path": save_path if success else None,
                "download_success": success
            })
        
        return results
    
    

    def download_all(self) -> list[dict]:
        all_results = []
        for company_name, company_info in COMPANIES.items():
            results = self.download_company_filings(company_name, company_info)
            all_results.extend(results)
            
            ticker = company_info["ticker"]
            counts = count_by_category(os.path.join(CLASSIFED_RAW_FILINGS, ticker))
            logger.info(f"{ticker} filing counts: {counts}")

        self._save_download_log(all_results)
        return all_results
        
    def _save_download_log(self, results: list[dict]) -> None:
        log_path = os.path.join(RAW_DIR, "download_log.json")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\nDownloding log saved: {log_path}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    loader = SECLoader()
    results = loader.download_all()
    return results


if __name__ == "__main__":
    main()
