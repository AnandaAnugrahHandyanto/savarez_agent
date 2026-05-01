#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QMT 数据源适配器
支持从本地快照、远程 VM、或 QMT API 读取实时行情
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime, date
from typing import Optional, List, Dict

HERMES_HOME = Path.home() / ".hermes"
QMT_SNAPSHOT_DIR = HERMES_HOME / "state" / "qmt_snapshots"
QMT_SYNC_ROOT = HERMES_HOME / "state" / "qmt_sync"


class QMTDataSource:
    """QMT 数据源基类"""
    
    def get_realtime_quote(self, code: str) -> Optional[Dict]:
        """
        获取实时行情
        
        返回:
        {
            "code": "300123",
            "name": "太阳鸟",
            "price": 12.34,
            "open": 12.00,
            "high": 12.50,
            "low": 11.90,
            "close": 12.34,
            "volume": 1234567,
            "amount": 15234567.89,
            "change_pct": 3.2,
            "bid_volume": 123456,
            "ask_volume": 234567,
            "time": "2026-04-21 10:30:00",
        }
        """
        raise NotImplementedError
    
    def get_batch_quotes(self, codes: List[str]) -> List[Dict]:
        """批量获取实时行情"""
        return [self.get_realtime_quote(code) for code in codes if self.get_realtime_quote(code)]
    
    def get_historical_data(self, code: str, days: int = 20) -> List[Dict]:
        """
        获取历史数据
        
        返回: [{"date": "2026-04-21", "close": 12.34, "volume": 1234567, "amount": 15234567.89, "change_pct": 3.2}, ...]
        """
        raise NotImplementedError


class LocalSnapshotDataSource(QMTDataSource):
    """从本地快照读取（最快，但可能不是最新）"""
    
    def __init__(self, snapshot_dir: Path = QMT_SNAPSHOT_DIR):
        self.snapshot_dir = snapshot_dir
        self._cache = None
        self._cache_time = None
    
    def _load_latest_snapshot(self) -> Dict:
        """加载最新快照"""
        if not self.snapshot_dir.exists():
            return {}
        
        # 检查缓存（5秒内有效）
        if self._cache and self._cache_time:
            if (datetime.now() - self._cache_time).total_seconds() < 5:
                return self._cache
        
        # 查找最新快照
        snapshots = sorted(self.snapshot_dir.glob("snapshot_*.json"), reverse=True)
        if not snapshots:
            # 尝试 intraday_refresh_last.json
            sync_file = QMT_SYNC_ROOT / "intraday_refresh_last.json"
            if sync_file.exists():
                with open(sync_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._cache = data
                    self._cache_time = datetime.now()
                    return data
            return {}
        
        with open(snapshots[0], "r", encoding="utf-8") as f:
            data = json.load(f)
            self._cache = data
            self._cache_time = datetime.now()
            return data
    
    def get_realtime_quote(self, code: str) -> Optional[Dict]:
        snapshot = self._load_latest_snapshot()
        
        # 查找股票
        for item in snapshot.get("data", []):
            if item.get("code") == code:
                return {
                    "code": code,
                    "name": item.get("name", ""),
                    "price": float(item.get("current_price") or item.get("price") or 0),
                    "open": float(item.get("open_price") or 0),
                    "high": float(item.get("high_price") or 0),
                    "low": float(item.get("low_price") or 0),
                    "close": float(item.get("current_price") or item.get("price") or 0),
                    "volume": int(item.get("volume") or 0),
                    "amount": float(item.get("amount") or 0),
                    "change_pct": float(item.get("change_pct") or 0),
                    "bid_volume": int(item.get("bid_volume") or 0),
                    "ask_volume": int(item.get("ask_volume") or 0),
                    "time": snapshot.get("timestamp", datetime.now().isoformat()),
                }
        
        return None
    
    def get_historical_data(self, code: str, days: int = 20) -> List[Dict]:
        # 本地快照没有历史数据，返回空
        return []


class RemoteVMDataSource(QMTDataSource):
    """从远程 Windows VM 同步（需要 SSH 配置）"""
    
    def __init__(self, host: str, user: str, password: str):
        self.host = host
        self.user = user
        self.password = password
    
    def _sync_latest_snapshot(self):
        """同步最新快照"""
        from qmt_sync_intraday import sync_intraday_bundle
        
        today = date.today().isoformat()
        sync_intraday_bundle(
            host=self.host,
            user=self.user,
            password=self.password,
            date=today,
            out_dir=HERMES_HOME / "state" / "qmt_reports",
            sync_root=QMT_SYNC_ROOT,
        )
    
    def get_realtime_quote(self, code: str) -> Optional[Dict]:
        # 先同步最新快照
        self._sync_latest_snapshot()
        
        # 然后用本地快照读取
        local_source = LocalSnapshotDataSource()
        return local_source.get_realtime_quote(code)
    
    def get_historical_data(self, code: str, days: int = 20) -> List[Dict]:
        # TODO: 从 VM 同步历史数据
        return []


class TushareDataSource(QMTDataSource):
    """从 tushare 获取（需要 token）"""
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or self._load_token()
        if not self.token:
            raise ValueError("Tushare token 未配置")
        
        try:
            import tushare as ts
            self.ts = ts
            self.pro = ts.pro_api(self.token)
        except ImportError:
            raise ImportError("请安装 tushare: pip install tushare")
    
    def _load_token(self) -> Optional[str]:
        """从配置文件加载 token"""
        config_file = HERMES_HOME / "config" / "tushare.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("token")
        return None
    
    def get_realtime_quote(self, code: str) -> Optional[Dict]:
        """tushare 实时行情需要高级权限，这里返回最新日线数据"""
        try:
            # 转换代码格式：300123 -> 300123.SZ
            ts_code = self._convert_code(code)
            
            df = self.pro.daily(ts_code=ts_code, start_date=date.today().strftime("%Y%m%d"))
            
            if df.empty:
                return None
            
            row = df.iloc[0]
            return {
                "code": code,
                "name": "",  # tushare daily 没有名称
                "price": float(row["close"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["vol"] * 100),  # tushare 单位是手
                "amount": float(row["amount"] * 1000),  # tushare 单位是千元
                "change_pct": float(row["pct_chg"]),
                "bid_volume": 0,
                "ask_volume": 0,
                "time": datetime.now().isoformat(),
            }
        except Exception as e:
            print(f"Tushare 获取 {code} 失败: {e}")
            return None
    
    def get_historical_data(self, code: str, days: int = 20) -> List[Dict]:
        """获取历史数据"""
        try:
            ts_code = self._convert_code(code)
            
            # 获取最近 N 天数据
            end_date = date.today().strftime("%Y%m%d")
            start_date = (date.today() - __import__("datetime").timedelta(days=days*2)).strftime("%Y%m%d")
            
            df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            
            if df.empty:
                return []
            
            # 按日期排序
            df = df.sort_values("trade_date")
            
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": row["trade_date"],
                    "close": float(row["close"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "volume": int(row["vol"] * 100),
                    "amount": float(row["amount"] * 1000),
                    "change_pct": float(row["pct_chg"]),
                })
            
            return result[-days:]  # 只返回最近 N 天
        
        except Exception as e:
            print(f"Tushare 获取 {code} 历史数据失败: {e}")
            return []
    
    def _convert_code(self, code: str) -> str:
        """转换代码格式：300123 -> 300123.SZ"""
        if "." in code:
            return code
        
        if code.startswith("6"):
            return f"{code}.SH"
        elif code.startswith("0") or code.startswith("3"):
            return f"{code}.SZ"
        elif code.startswith("8") or code.startswith("4"):
            return f"{code}.BJ"
        else:
            return f"{code}.SH"


class AkshareDataSource(QMTDataSource):
    """从 akshare 获取（免费，无需 token）"""
    
    def __init__(self):
        try:
            import akshare as ak
            self.ak = ak
        except ImportError:
            raise ImportError("请安装 akshare: pip install akshare")
    
    def get_realtime_quote(self, code: str) -> Optional[Dict]:
        """获取实时行情"""
        try:
            # akshare 实时行情
            df = self.ak.stock_zh_a_spot_em()
            
            # 查找股票
            row = df[df["代码"] == code]
            if row.empty:
                return None
            
            row = row.iloc[0]
            return {
                "code": code,
                "name": row["名称"],
                "price": float(row["最新价"]),
                "open": float(row["今开"]),
                "high": float(row["最高"]),
                "low": float(row["最低"]),
                "close": float(row["最新价"]),
                "volume": int(row["成交量"]),
                "amount": float(row["成交额"]),
                "change_pct": float(row["涨跌幅"]),
                "bid_volume": 0,
                "ask_volume": 0,
                "time": datetime.now().isoformat(),
            }
        except Exception as e:
            print(f"Akshare 获取 {code} 失败: {e}")
            return None
    
    def get_historical_data(self, code: str, days: int = 20) -> List[Dict]:
        """获取历史数据"""
        try:
            # akshare 历史日线
            end_date = date.today().strftime("%Y%m%d")
            start_date = (date.today() - __import__("datetime").timedelta(days=days*2)).strftime("%Y%m%d")
            
            df = self.ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="")
            
            if df.empty:
                return []
            
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": row["日期"],
                    "close": float(row["收盘"]),
                    "open": float(row["开盘"]),
                    "high": float(row["最高"]),
                    "low": float(row["最低"]),
                    "volume": int(row["成交量"]),
                    "amount": float(row["成交额"]),
                    "change_pct": float(row["涨跌幅"]),
                })
            
            return result[-days:]
        
        except Exception as e:
            print(f"Akshare 获取 {code} 历史数据失败: {e}")
            return []


def get_data_source(source_type: str = "auto", **kwargs) -> QMTDataSource:
    """
    获取数据源
    
    source_type:
    - "auto": 自动选择（优先本地快照 -> akshare -> tushare）
    - "local": 本地快照
    - "remote": 远程 VM
    - "tushare": Tushare
    - "akshare": Akshare
    """
    
    if source_type == "local":
        return LocalSnapshotDataSource()
    
    elif source_type == "remote":
        return RemoteVMDataSource(
            host=kwargs.get("host", ""),
            user=kwargs.get("user", ""),
            password=kwargs.get("password", ""),
        )
    
    elif source_type == "tushare":
        return TushareDataSource(token=kwargs.get("token"))
    
    elif source_type == "akshare":
        return AkshareDataSource()
    
    elif source_type == "auto":
        # 优先本地快照
        try:
            source = LocalSnapshotDataSource()
            # 测试是否有数据
            if source._load_latest_snapshot():
                return source
        except:
            pass
        
        # 尝试 akshare（免费）
        try:
            return AkshareDataSource()
        except:
            pass
        
        # 尝试 tushare
        try:
            return TushareDataSource()
        except:
            pass
        
        # 最后回退到本地快照
        return LocalSnapshotDataSource()
    
    else:
        raise ValueError(f"未知数据源类型: {source_type}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="QMT 数据源适配器")
    parser.add_argument("action", choices=["quote", "history", "test"])
    parser.add_argument("--code", help="股票代码")
    parser.add_argument("--codes", nargs="+", help="股票代码列表")
    parser.add_argument("--source", default="auto", choices=["auto", "local", "remote", "tushare", "akshare"])
    parser.add_argument("--days", type=int, default=20, help="历史数据天数")
    
    args = parser.parse_args()
    
    # 获取数据源
    source = get_data_source(args.source)
    print(f"使用数据源: {source.__class__.__name__}")
    
    if args.action == "quote":
        if not args.code:
            print("错误：需要 --code")
            exit(1)
        
        quote = source.get_realtime_quote(args.code)
        if quote:
            print(json.dumps(quote, ensure_ascii=False, indent=2))
        else:
            print(f"未找到 {args.code}")
    
    elif args.action == "history":
        if not args.code:
            print("错误：需要 --code")
            exit(1)
        
        history = source.get_historical_data(args.code, args.days)
        print(json.dumps(history, ensure_ascii=False, indent=2))
    
    elif args.action == "test":
        test_codes = args.codes or ["300123", "600519", "000001"]
        
        print(f"\n=== 测试实时行情 ===")
        for code in test_codes:
            quote = source.get_realtime_quote(code)
            if quote:
                print(f"{quote['name']} ({code}): {quote['price']:.2f} ({quote['change_pct']:+.2f}%)")
            else:
                print(f"{code}: 未找到")
        
        print(f"\n=== 测试历史数据 ===")
        code = test_codes[0]
        history = source.get_historical_data(code, 5)
        if history:
            print(f"{code} 最近 5 天:")
            for item in history:
                print(f"  {item['date']}: {item['close']:.2f} ({item['change_pct']:+.2f}%)")
        else:
            print(f"{code}: 无历史数据")
