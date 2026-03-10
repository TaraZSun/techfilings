# backend/tests/test_loader.py
import pytest
from unittest.mock import patch, MagicMock
from modules.loader import SECLoader
import tempfile, os

def test_filter_filings_returns_correct_types():
    loader = SECLoader()
    fake_data = {
        "filings": {
            "recent": {
                "form": ["10-K", "10-Q", "8-K", "10-K"],
                "accessionNumber": ["001", "002", "003", "004"],
                "filingDate": ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"],
                "primaryDocument": ["a.htm", "b.htm", "c.htm", "d.htm"]
            }
        }
    }
    results = loader.filter_filings(fake_data, ["10-K", "10-Q"], limit=2)
    forms = [r["form_type"] for r in results]
    assert "8-K" not in forms
    assert forms.count("10-K") <= 2

def test_filter_filings_respects_limit():
    loader = SECLoader()
    fake_data = {
        "filings": {
            "recent": {
                "form": ["10-K", "10-K", "10-K"],
                "accessionNumber": ["001", "002", "003"],
                "filingDate": ["2024-01-01", "2024-02-01", "2024-03-01"],
                "primaryDocument": ["a.htm", "b.htm", "c.htm"]
            }
        }
    }
    results = loader.filter_filings(fake_data, ["10-K"], limit=2)
    assert len(results) == 2

@patch("modules.loader.requests.get")
def test_download_filing_success(mock_get):
    mock_get.return_value = MagicMock(status_code=200, text="<html>test</html>")
    mock_get.return_value.raise_for_status = MagicMock()
    
    loader = SECLoader()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "test.html")
        result = loader.download_filing("0001045810", "0001045810-24-000001", "test.htm", save_path)
        assert result == True
        assert os.path.exists(save_path)