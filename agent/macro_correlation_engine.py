import logging
import time
from typing import List, Dict, Any, Optional
import numpy as np
from scipy import stats
from hermes_state import SessionDB

logger = logging.getLogger(__name__)

class MacroCorrelationEngine:
    """Engine for calculating correlations and identifying 'Truth-Seeking' divergences."""
    
    def __init__(self, db: Optional[SessionDB] = None):
        self.db = db or SessionDB()

    def get_correlation(self, metric_a: str, metric_b: str, days: int = 90) -> Dict[str, Any]:
        """Calculate correlation between two time-series metrics."""
        series_a = self.db.get_macro_history(metric_a, days=days)
        series_b = self.db.get_macro_history(metric_b, days=days)
        
        if not series_a or not series_b:
            return {"error": "Insufficient data for one or both metrics"}
            
        # Align series by timestamp (simplified to daily buckets)
        data_a = {time.strftime('%Y-%m-%d', time.gmtime(r['timestamp'])): r['value'] for r in series_a}
        data_b = {time.strftime('%Y-%m-%d', time.gmtime(r['timestamp'])): r['value'] for r in series_b}
        
        common_dates = sorted(set(data_a.keys()) & set(data_b.keys()))
        if len(common_dates) < 5:
            return {"error": "Insufficient overlapping data points"}
            
        vals_a = [data_a[d] for d in common_dates]
        vals_b = [data_b[d] for d in common_dates]
        
        res = stats.pearsonr(vals_a, vals_b)
        
        return {
            "metric_a": metric_a,
            "metric_b": metric_b,
            "correlation": round(res.statistic, 4),
            "p_value": round(res.pvalue, 6),
            "sample_size": len(common_dates),
            "interpretation": self._interpret_correlation(res.statistic)
        }

    def get_divergence_narrative(self, metric_a: str, metric_b: str, days: int = 30) -> Dict[str, Any]:
        """Generate a 'Truth-Seeking' narrative comparing two metrics."""
        corr_info = self.get_correlation(metric_a, metric_b, days=days)
        if "error" in corr_info:
            return corr_info
            
        r = corr_info["correlation"]
        
        # Determine status and insight
        if r > 0.85:
            status = "Aligned 🟢"
            insight = f"The relationship between {metric_a} and {metric_b} is highly consistent (r={r}). This suggests the official data is well-supported by physical ground-truth proxies."
        elif r > 0.6:
            status = "Broadly Supported 🟡"
            insight = f"Moderate correlation (r={r}). While aligned, there are localized divergences that may suggest reporting lags or structural shifts in the energy/freight intensity of the target metric."
        elif r > 0.3:
            status = "Diverging Alert 🟠"
            insight = f"Low correlation (r={r}). Significant divergence detected. The physical economy (ground-truth) is not scaling linearly with the target metric. High probability of data smoothing or window-dressing in official figures."
        else:
            status = "Critical Decoupling 🔴"
            insight = f"Negative or near-zero correlation (r={r}). Critical decoupling. The target metric is moving independently of its physical foundations. Official data should be treated with extreme skepticism; check for one-off fiscal adjustments or reporting manipulation."

        return {
            **corr_info,
            "status": status,
            "insight": insight,
            "timestamp": time.time()
        }

    def generate_narrative(self) -> str:
        """Generate a high-level macro narrative based on current correlations."""
        # 1. Fetch latest ground truth vs official
        # 2. Fetch credit cycle vs inflation
        # 3. Fetch global freight vs exports
        return "Narrative engine initialized. Waiting for sufficient time-series data to identify trends."

    def _interpret_correlation(self, r: float) -> str:
        if r > 0.8: return "Strong Positive"
        if r > 0.5: return "Moderate Positive"
        if r > -0.2 and r < 0.2: return "Neutral/No Correlation"
        if r < -0.8: return "Strong Inverse"
        if r < -0.5: return "Moderate Inverse"
        return "Weak"
