import os
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import pandas as pd

logger = logging.getLogger(__name__)

class AbstractFinanceProvider(ABC):
    \"\"\"Abstract base class for financial data providers.\"\"\"
    
    @abstractmethod
    def get_info(self, ticker: str) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def get_history(self, ticker: str, period: str = \"1y\", interval: str = \"1d\") -> pd.DataFrame:
        pass
    
    @abstractmethod
    def get_financials(self, ticker: str) -> Dict[str, pd.DataFrame]:
        pass

class YahooFinanceProvider(AbstractFinanceProvider):
    \"\"\"Provider using the yfinance library (unofficial/scraping).\"\"\"
    
    def __init__(self):
        try:
            import yfinance as yf
            self.yf = yf
        except ImportError:
            self.yf = None
            logger.warning(\"yfinance is not installed. YahooFinanceProvider will be limited.\")

    def _get_ticker(self, ticker: str):
        if not self.yf:
            raise ImportError(\"yfinance is required for YahooFinanceProvider\")
        return self.yf.Ticker(ticker)

    def get_info(self, ticker: str) -> Dict[str, Any]:
        t = self._get_ticker(ticker)
        return t.info

    def get_history(self, ticker: str, period: str = \"1y\", interval: str = \"1d\") -> pd.DataFrame:
        t = self._get_ticker(ticker)
        return t.history(period=period, interval=interval)

    def get_financials(self, ticker: str) -> Dict[str, pd.DataFrame]:
        t = self._get_ticker(ticker)
        return {
            \"income_stmt\": t.income_stmt,
            \"balance_sheet\": t.balance_sheet,
            \"cashflow\": t.cashflow,
            \"calendar\": t.calendar
        }

class AlphaVantageProvider(AbstractFinanceProvider):
    \"\"\"Official provider using Alpha Vantage API (requires API key).\"\"\"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv(\"ALPHA_VANTAGE_API_KEY\")
        if not self.api_key:
            logger.debug(\"AlphaVantage API key not found.\")

    def get_info(self, ticker: str) -> Dict[str, Any]:
        # Implementation would use requests to fetch from Alpha Vantage
        # This is a stub for Phase 2 implementation
        return {\"error\": \"AlphaVantageProvider.get_info not yet fully implemented\"}

    def get_history(self, ticker: str, period: str = \"1y\", interval: str = \"1d\") -> pd.DataFrame:
        return pd.DataFrame()

    def get_financials(self, ticker: str) -> Dict[str, pd.DataFrame]:
        return {}

def get_finance_provider(ticker: Optional[str] = None) -> AbstractFinanceProvider:
    \"\"\"
    Factory to return the best available finance provider.
    Can be extended to return different providers based on ticker region.
    \"\"\"
    # If Alpha Vantage key is present, it might be preferred for certain tasks
    # but for now, Yahoo is the most comprehensive free option despite brittleness.
    
    # Regional logic (Phase 6)
    if ticker and (\".NS\" in ticker or \".BO\" in ticker):
        # Could prefer a specific provider for Indian markets
        pass
        
    return YahooFinanceProvider()

def map_ticker_suffix(ticker: str, region: str) -> str:
    \"\"\"Map common regions to their Yahoo Finance suffixes.\"\"\"
    suffixes = {
        \"india\": [\".NS\", \".BO\"],
        \"london\": [\".L\"],
        \"toronto\": [\".TO\", \".V\"],
        \"frankfurt\": [\".DE\"],
        \"hongkong\": [\".HK\"],
        \"australia\": [\".AX\"],
    }
    region = region.lower()
    if region in suffixes:
        # Return first suffix for the region if ticker doesn't already have it
        primary_suffix = suffixes[region][0]
        if not any(ticker.endswith(s) for s in suffixes[region]):
            return f\"{ticker}{primary_suffix}\"
    return ticker
