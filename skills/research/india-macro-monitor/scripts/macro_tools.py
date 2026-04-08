import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from agent.india_finance_providers import (
    NSEProvider, RBIProvider, GoogleFinanceProvider, 
    GlobalMacroProvider, EnergyMonitorProvider, BankingProvider
)
from hermes_state import SessionDB

logger = logging.getLogger(__name__)

class IndiaMacroMonitor:
    """Tools for tracking and summarizing Indian macroeconomic indicators."""
    
    def __init__(self):
        self.nse = NSEProvider()
        self.rbi = RBIProvider()
        self.google = GoogleFinanceProvider()
        self.global_macro = GlobalMacroProvider()
        self.energy = EnergyMonitorProvider()
        self.banking = BankingProvider()
        self.db = SessionDB()

    def get_macro_pulse(self) -> str:
        """
        Generate a comprehensive pulse report of Indian macro indicators.
        Fetches data from NSE, RBI, Google Finance, and ground-truth providers.
        """
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M")
        now_ts = now.timestamp()
        
        # 1. Fetch Market Status & Flows (NSE)
        try:
            fii_dii = self.nse.get_fii_dii_flows()
        except Exception as e:
            logger.error(f"NSE fetch failed: {e}")
            fii_dii = {}

        # 2. Fetch Real-time Indices & Pulse (Google Finance)
        tickers = {
            "Nifty 50": "NIFTY_50:INDEXNSE",
            "Sensex": "SENSEX:INDEXBOM",
            "INR/USD": "USDINR",
            "Brent Crude": "BRENT_CRUDE:COMMODITY",
            "US 10Y Yield": "US10Y:INDEX"
        }
        quotes = {}
        for name, ticker in tickers.items():
            quotes[name] = self.google.get_quote(ticker)
            time.sleep(0.2)

        # 3. Fetch Ground Truth & Global Macro
        bdi = self.global_macro.get_baltic_dry_index()
        electricity = self.energy.get_daily_generation()
        credit = self.banking.get_bank_credit_growth()

        # Log to History for Charting
        self._log_history("BDRY", bdi.get("price"), "Global Trade", "USD", "Google", now_ts)
        self._log_history("ELEC_GEN", electricity.get("value"), "Energy", "MU", "POSOCO", now_ts)
        self._log_history("NIFTY_50", quotes.get("Nifty 50", {}).get("price"), "Market", "INR", "Google", now_ts)
        self._log_history("BRENT", quotes.get("Brent Crude", {}).get("price"), "Commodity", "USD", "Google", now_ts)
        self._log_history("BANK_CREDIT", credit.get("value"), "Banking", "%", "RBI", now_ts)

        # Build Markdown Report
        report = f"# 🇮🇳 India Macro Pulse ({now_str})\\n\\n"
        
        report += "### 📊 Market Pulse\\n"
        report += "| Indicator | Price | Change |\\n"
        report += "| :--- | :--- | :--- |\\n"
        for name, q in quotes.items():
            report += f"| {name} | {q.get('price', 'N/A')} | {q.get('change', 'N/A')} |\\n"
        report += "\\n"

        report += "### 🌍 Ground Truth & Global Proxy\\n"
        report += f"- **Baltic Dry Index (BDRY):** {bdi.get('price', 'N/A')} USD\\n"
        report += f"- **Electricity Generation:** {electricity.get('value', 'N/A')} {electricity.get('unit', '')}\\n"
        report += f"- **Bank Credit Growth:** {credit.get('value', 'N/A')} (YoY)\\n"
        report += "\\n"

        # Risk Assessment
        report += "### 🔴 Risk Assessment\\n"
        # (Simplified logic from before...)
        report += "\\n---\\n"
        report += "*Data sourced from NSE, RBI, POSOCO, and Google Finance. Truth-seeking metrics included.*"
        
        return report

    def _log_history(self, metric_id: str, value: Any, category: str, unit: str, source: str, timestamp: float):
        try:
            if value and str(value) != "Unknown" and str(value) != "N/A":
                clean_val = float(str(value).replace(",", "").replace("%", ""))
                self.db.log_macro_metric(
                    metric_id=metric_id,
                    value=clean_val,
                    category=category,
                    unit=unit,
                    source=source,
                    timestamp=timestamp
                )
        except Exception as e:
            logger.debug(f"Failed to log macro history for {metric_id}: {e}")

def get_macro_pulse():
    """Helper for the agent to call the tool directly."""
    monitor = IndiaMacroMonitor()
    return monitor.get_macro_pulse()
