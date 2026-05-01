"""
数据获取模块
支持日线、分时、涨停板数据获取
"""
import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class TushareDataFetcher:
    """Tushare数据获取器"""
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get('TUSHARE_TOKEN')
        if not self.token:
            raise ValueError("未设置TUSHARE_TOKEN环境变量")
        self.base_url = "https://api.tushare.pro"
    
    def _post(self, api: str, params: dict) -> List[Dict]:
        """调用Tushare API"""
        data = {
            "api_name": api,
            "token": self.token,
            "params": params,
            "fields": ""
        }
        response = requests.post(self.base_url, json=data, timeout=30)
        result = response.json()
        
        if result.get('code') != 0:
            raise Exception(f"API调用失败: {result.get('msg')}")
        
        items = result.get('data', {})
        fields = items.get('fields', [])
        rows = items.get('items', [])
        
        return [dict(zip(fields, row)) for row in rows]
    
    def get_daily_data(self, ts_code: str, start_date: str, end_date: str) -> List[Dict]:
        """
        获取日线数据
        
        Args:
            ts_code: 股票代码（如 002192.SZ）
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）
        
        Returns:
            日线数据列表，按日期升序
        """
        daily = self._post('daily', {
            'ts_code': ts_code,
            'start_date': start_date,
            'end_date': end_date
        })
        return sorted(daily, key=lambda x: x['trade_date'])
    
    def get_intraday_data(self, ts_code: str, trade_date: str, freq: str = '5min') -> List[Dict]:
        """
        获取分时数据
        
        Args:
            ts_code: 股票代码
            trade_date: 交易日期（YYYYMMDD）
            freq: 频率（1min/5min/15min/30min/60min）
        
        Returns:
            分时数据列表，按时间升序
        """
        try:
            intraday = self._post('stk_mins', {
                'ts_code': ts_code,
                'trade_date': trade_date,
                'freq': freq
            })
            return sorted(intraday, key=lambda x: x.get('trade_time', ''))
        except Exception as e:
            # 分时数据可能不可用（需要高级权限）
            print(f"警告: 无法获取分时数据 - {e}")
            return []
    
    def get_limit_list(self, trade_date: str) -> Dict[str, Dict]:
        """
        获取涨停板数据
        
        Args:
            trade_date: 交易日期（YYYYMMDD）
        
        Returns:
            {ts_code: limit_data} 字典
        """
        limit_list = self._post('limit_list_d', {'trade_date': trade_date})
        return {r['ts_code']: r for r in limit_list if r.get('limit') == 'U'}
    
    def get_trade_cal(self, start_date: str, end_date: str, exchange: str = 'SSE') -> List[str]:
        """
        获取交易日历
        
        Args:
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）
            exchange: 交易所（SSE/SZSE）
        
        Returns:
            交易日列表（升序）
        """
        cal = self._post('trade_cal', {
            'exchange': exchange,
            'start_date': start_date,
            'end_date': end_date
        })
        trade_dates = sorted([r['cal_date'] for r in cal if r.get('is_open') == 1])
        return trade_dates
    
    def get_recent_trade_dates(self, days: int = 30) -> List[str]:
        """
        获取最近N个交易日
        
        Args:
            days: 天数
        
        Returns:
            交易日列表（升序）
        """
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days+10)).strftime('%Y%m%d')
        
        trade_dates = self.get_trade_cal(start_date, end_date)
        return trade_dates[-days:]
    
    def get_stock_basic(self, ts_code: str) -> Optional[Dict]:
        """
        获取股票基本信息
        
        Args:
            ts_code: 股票代码
        
        Returns:
            股票基本信息
        """
        try:
            result = self._post('stock_basic', {'ts_code': ts_code})
            return result[0] if result else None
        except:
            return None


if __name__ == '__main__':
    # 测试
    fetcher = TushareDataFetcher()
    
    # 测试日线数据
    print("测试日线数据获取...")
    daily = fetcher.get_daily_data('002192.SZ', '20260401', '20260423')
    print(f"获取到 {len(daily)} 条日线数据")
    if daily:
        print(f"最新: {daily[-1]}")
    
    # 测试交易日历
    print("\n测试交易日历...")
    trade_dates = fetcher.get_recent_trade_dates(10)
    print(f"最近10个交易日: {trade_dates}")
    
    # 测试涨停板数据
    print("\n测试涨停板数据...")
    limits = fetcher.get_limit_list('20260423')
    print(f"20260423 涨停股票数: {len(limits)}")
    
    print("\n✓ 数据获取模块测试通过")
