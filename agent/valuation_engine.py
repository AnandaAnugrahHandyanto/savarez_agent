"""
Valuation Engine: Deterministic Finance Models (Damodaran Methodology).
Supports R&D/Lease Capitalization, WACC Convergence, and 10-year DCF.
Uses only standard library to ensure portability across agent environments.
"""

import math
from typing import Dict, List, Optional, Union, Any

class RDLeaseCapitalizer:
    """Adjusts financials by treating R&D and Leases as Capital Expenses."""
    
    @staticmethod
    def capitalize_rd(rd_history: List[float], tax_rate: float, amort_period: int = 5) -> Dict[str, float]:
        """
        Capitalizes R&D expenses.
        rd_history: [current_year, yr-1, yr-2, ..., yr-n]
        """
        if not rd_history:
            return {"asset_value": 0.0, "amortization": 0.0, "adjustment_to_ebit": 0.0}
            
        current_rd = rd_history[0]
        actual_period = min(amort_period, len(rd_history))
        
        # Calculate unamortized portion (Research Asset)
        asset_value = 0.0
        total_amortization = 0.0
        
        for i in range(actual_period):
            # i=0 is current year
            expense = rd_history[i]
            # Unamortized portion
            unamortized_fraction = (actual_period - i) / actual_period
            asset_value += expense * unamortized_fraction
            
            # Amortization this year (from past expenses)
            if i > 0:
                total_amortization += rd_history[i] / actual_period
                
        adjustment_to_ebit = current_rd - total_amortization
        
        return {
            "asset_value": asset_value,
            "amortization": total_amortization,
            "adjustment_to_ebit": adjustment_to_ebit,
            "tax_effect": adjustment_to_ebit * tax_rate
        }

    @staticmethod
    def capitalize_leases(lease_commitments: List[float], cost_of_debt: float) -> Dict[str, float]:
        """
        Capitalizes Operating Leases as Debt.
        lease_commitments: [yr1, yr2, yr3, yr4, yr5, yr6_beyond]
        """
        if not lease_commitments:
            return {"lease_debt": 0.0, "adjustment_to_ebit": 0.0}
            
        # Present Value of lease commitments
        pv_lease = 0.0
        for i, payment in enumerate(lease_commitments[:5]):
            pv_lease += payment / ((1 + cost_of_debt) ** (i + 1))
            
        # Handle Year 6 and beyond (usually an annuity)
        if len(lease_commitments) > 5:
            yr6_beyond = lease_commitments[5]
            # Assume 5 years of equal payments for the 'beyond' portion
            annuity_payment = yr6_beyond / 5
            for i in range(5, 10):
                pv_lease += annuity_payment / ((1 + cost_of_debt) ** (i + 1))
                
        # Adjustment to EBIT = Operating Lease Expense - Depreciation on Lease Asset
        interest_component = pv_lease * cost_of_debt
        
        return {
            "lease_debt": pv_lease,
            "adjustment_to_ebit": interest_component 
        }

class CostOfCapitalModel:
    """Handles WACC and its convergence over time."""
    
    @staticmethod
    def calculate_wacc(
        beta: float, 
        risk_free_rate: float, 
        erp: float, 
        cost_of_debt: float, 
        tax_rate: float, 
        debt_ratio: float
    ) -> float:
        cost_of_equity = risk_free_rate + (beta * erp)
        after_tax_debt = cost_of_debt * (1 - tax_rate)
        wacc = (cost_of_equity * (1 - debt_ratio)) + (after_tax_debt * debt_ratio)
        return wacc

    @staticmethod
    def converge_wacc(initial_wacc: float, terminal_wacc: float, years: int = 10) -> List[float]:
        """Converges WACC from initial to terminal over X years."""
        halfway = years // 2
        waccs = [0.0] * (years + 1)
        for i in range(halfway + 1):
            waccs[i] = initial_wacc
        
        for i in range(halfway + 1, years + 1):
            step = (initial_wacc - terminal_wacc) / (years - halfway)
            waccs[i] = initial_wacc - (step * (i - halfway))
            
        return waccs

class DCFModel:
    """Free Cash Flow to the Firm model."""
    
    @staticmethod
    def calculate_intrinsic_value(
        current_revenue: float,
        growth_rates: List[float], # 10 years
        target_margin: float,
        current_margin: float,
        sales_to_capital: float,
        waccs: List[float],
        terminal_growth: float,
        terminal_wacc: float,
        tax_rate: float,
        nol: float = 0,
        cash: float = 0,
        debt: float = 0,
        minority_interests: float = 0,
        non_operating_assets: float = 0,
        shares_outstanding: float = 1
    ) -> Dict[str, Any]:
        """Runs a full 10-year FCFF DCF."""
        
        revenues = [current_revenue]
        margins = []
        ebits = []
        taxes = []
        reinvestments = []
        fcffs = []
        
        # 1. Forecast 10 years
        cumulative_revenue = current_revenue
        for i in range(10):
            # Growth
            growth = growth_rates[i]
            next_revenue = cumulative_revenue * (1 + growth)
            incremental_revenue = next_revenue - cumulative_revenue
            revenues.append(next_revenue)
            
            # Margin convergence
            margin = current_margin + (target_margin - current_margin) * ((i + 1) / 10)
            margins.append(margin)
            
            # EBIT
            ebit = next_revenue * margin
            ebits.append(ebit)
            
            # Tax (accounting for NOL)
            if ebit > 0:
                taxable_income = max(0.0, ebit - nol)
                tax = taxable_income * tax_rate
                nol = max(0.0, nol - ebit)
            else:
                tax = 0.0
                nol += abs(ebit)
            taxes.append(tax)
            
            # Reinvestment (Sales to Capital ratio)
            reinvestment = incremental_revenue / sales_to_capital
            reinvestments.append(reinvestment)
            
            # FCFF
            fcff = ebit - tax - reinvestment
            fcffs.append(fcff)
            
            cumulative_revenue = next_revenue
            
        # 2. Terminal Value
        terminal_growth = min(terminal_growth, terminal_wacc)
        terminal_ebit = revenues[-1] * (1 + terminal_growth) * target_margin
        terminal_tax = terminal_ebit * tax_rate
        terminal_reinvestment = (terminal_growth / terminal_wacc) * (terminal_ebit - terminal_tax)
        terminal_fcff = terminal_ebit - terminal_tax - terminal_reinvestment
        
        terminal_value = terminal_fcff / (terminal_wacc - terminal_growth)
        
        # 3. Present Value
        pv_fcff = 0.0
        discount_factor = 1.0
        for i in range(10):
            discount_factor *= (1 + waccs[i+1])
            pv_fcff += fcffs[i] / discount_factor
            
        pv_terminal_value = terminal_value / discount_factor
        
        enterprise_value = pv_fcff + pv_terminal_value
        equity_value = enterprise_value + cash + non_operating_assets - debt - minority_interests
        
        return {
            "enterprise_value": enterprise_value,
            "equity_value": equity_value,
            "price_per_share": equity_value / shares_outstanding,
            "forecast": {
                "revenues": revenues[1:],
                "ebits": ebits,
                "fcffs": fcffs,
                "pv_fcff": pv_fcff,
                "pv_terminal": pv_terminal_value
            }
        }

class ValuationMapper:
    """Maps user-friendly qualitative descriptions to quantitative inputs."""
    
    SENSITIVITY_MAP = {
        "revenue_growth": {
            "explosive": 0.40,
            "high": 0.20,
            "moderate": 0.10,
            "low": 0.05,
            "stagnant": 0.02
        },
        "target_margin": {
            "software_best": 0.40,
            "software_avg": 0.25,
            "retail_best": 0.12,
            "retail_avg": 0.06,
            "industrial": 0.15
        },
        "sales_to_capital": {
            "asset_light": 3.0,
            "standard": 2.0,
            "capital_intensive": 1.0,
            "heavy_infra": 0.5
        }
    }
    
    @classmethod
    def map_input(cls, category: str, label: str) -> float:
        return cls.SENSITIVITY_MAP.get(category, {}).get(label, 0.0)
