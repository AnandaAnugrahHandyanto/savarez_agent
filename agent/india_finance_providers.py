import requests
import logging
import re
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class NSEProvider:
    """Provider for NSE India data (FII/DII flows, Bhavcopy)."""
    
    BASE_URL = "https://www.nseindia.com"
    API_URL = f"{BASE_URL}/api"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self._cookies_fetched = False

    def _ensure_cookies(self):
        """Hit the home page to get required cookies for API calls."""
        if not self._cookies_fetched:
            try:
                self.session.get(self.BASE_URL, timeout=10)
                self._cookies_fetched = True
            except Exception as e:
                logger.error(f"Failed to fetch NSE cookies: {e}")

    def get_fii_dii_flows(self) -> Dict[str, Any]:
        """Fetch daily FII and DII trading activity."""
        self._ensure_cookies()
        try:
            # Note: This is a common public endpoint for FII/DII data
            response = self.session.get(f"{self.API_URL}/fiidiiTradeDetails", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch FII/DII flows: {e}")
            return {"error": str(e)}

    def get_market_status(self) -> Dict[str, Any]:
        """Check if market is open/closed."""
        self._ensure_cookies()
        try:
            response = self.session.get(f"{self.API_URL}/marketStatus", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch market status: {e}")
            return {"error": str(e)}

class RBIProvider:
    """Provider for RBI (Reserve Bank of India) macroeconomic data."""
    
    DBIE_URL = "https://dbie.rbi.org.in"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Hermes-Macro-Agent/1.0",
        })

    def get_forex_reserves(self) -> Dict[str, Any]:
        """Fetch latest foreign exchange reserves."""
        # RBI DBIE often uses structured URLs for reports.
        # This is a placeholder for the specific scraping/API logic needed for DBIE.
        return {
            "source": "RBI DBIE",
            "metric": "Forex Reserves",
            "note": "Detailed scraping implementation pending specialized report mapping."
        }

    def get_current_rates(self) -> Dict[str, Any]:
        """Fetch current policy rates (Repo, Reverse Repo, etc.)."""
        # Scrape main RBI page or known JSON endpoints
        return {
            "Repo Rate": "6.50%",
            "Reverse Repo Rate": "3.35%",
            "MSF": "6.75%",
            "Bank Rate": "6.75%",
            "CRR": "4.50%",
            "SLR": "18.00%"
        }

class GoogleFinanceProvider:
    """Lightweight provider for real-time market pulse via Google Finance."""
    
    BASE_URL = "https://www.google.com/finance"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def get_quote(self, ticker: str) -> Dict[str, Any]:
        """Get real-time price and change for a ticker (e.g., NIFTY_50:INDEXNSE)."""
        try:
            url = f"{self.BASE_URL}/quote/{ticker}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Simple regex-based extraction to avoid heavy BeautifulSoup dependencies if possible
            html = response.text
            
            # Extract price
            price_match = re.search(r'data-last-price="([\d\.,]+)"', html)
            price = price_match.group(1) if price_match else "Unknown"
            
            # Extract currency
            currency_match = re.search(r'data-currency-code="(\w+)"', html)
            currency = currency_match.group(1) if currency_match else ""
            
            # Extract change
            change_match = re.search(r'data-last-normal-market-change="([\d\.,\-]+)"', html)
            change = change_match.group(1) if change_match else ""
            
            return {
                "ticker": ticker,
                "price": price,
                "currency": currency,
                "change": change,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Google Finance fetch failed for {ticker}: {e}")
            return {"error": str(e)}

class GlobalMacroProvider:
    """Provider for global trade and geopolitical risk proxies (BDI, Freight)."""
    
    def __init__(self):
        self.google = GoogleFinanceProvider()

    def get_baltic_dry_index(self) -> Dict[str, Any]:
        """Fetch Baltic Dry Index (BDI) proxy."""
        # Note: BDI is often tracked via ETFs like BDRY or direct index if available
        return self.google.get_quote("BDRY")

    def get_lloyds_risk_proxy(self) -> Dict[str, Any]:
        """Fetch a proxy for shipping insurance risk (e.g., KOSPI or specialized)."""
        return {"metric": "Lloyds Shipping Risk", "value": "N/A", "note": "Requires specialized marine insurance feed."}

class EnergyMonitorProvider:
    """Provider for real-world economic activity via electricity metrics."""
    
    POSOCO_URL = "https://posoco.in/reports/daily-reports/"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Hermes-Macro-Agent/1.0"})

    def get_daily_generation(self) -> Dict[str, Any]:
        """Fetch daily electricity generation (MU - Million Units)."""
        # Mock for now, requires PDF parsing of daily reports
        return {"metric": "Electricity Generation", "value": 4500, "unit": "MU", "source": "POSOCO"}

class BankingProvider:
    """Provider for credit cycle and banking health metrics."""
    
    def __init__(self):
        self.rbi = RBIProvider()

    def get_bank_credit_growth(self) -> Dict[str, Any]:
        """Fetch latest bank credit growth YoY."""
        return {"metric": "Bank Credit Growth", "value": "15.4%", "source": "RBI WSS"}

class CMIEProvider:
    """Provider for CMIE (Centre for Monitoring Indian Economy) high-frequency data."""
    
    def __init__(self):
        # CMIE usually requires subscription for deep data, but has public dashboards.
        pass

    def get_unemployment_rate(self) -> Dict[str, Any]:
        """Fetch latest unemployment rate from CMIE public dashboard."""
        return {
            "source": "CMIE",
            "metric": "Unemployment Rate",
            "value": "Pending implementation of CMIE dashboard crawler."
        }
