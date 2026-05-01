import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.import_stock_theme_library import build_library
from stock_theme_library import get_stock_themes


def test_build_library_emits_ranked_primary_signal_themes(tmp_path):
    df = pd.DataFrame(
        [
            {
                "股票代码": "600522",
                "名称": "中天科技",
                "Unnamed: 2": "通信-通信设备-通信线缆及配套",
                "地区": "江苏省",
                "题材1": "光纤概念",
                "题材2": "共封装光学(CPO)",
                "题材3": "铜缆高速连接",
                "题材4": "液冷服务器",
                "题材5": "国企改革",
                "题材6": "一带一路",
            }
        ]
    )
    payload = build_library(df, source_path=tmp_path / "sample.xlsx", sheet="题材库", source_name="unit")
    entry = payload["by_code"]["600522.SH"]

    assert entry["industry"] == "通信-通信设备-通信线缆及配套"
    assert entry["industry_signal_themes"] == ["铜缆高速连接"]
    assert entry["primary_signal_themes"] == ["铜缆高速连接", "CPO"]
    assert "商业航天" not in entry["primary_signal_themes"]
    assert "国企改革" not in entry["primary_signal_themes"]
    assert entry["signal_theme_scores"][0]["theme"] == "铜缆高速连接"
    assert entry["signal_theme_scores"][0]["score"] > entry["signal_theme_scores"][-1]["score"]


def test_build_library_uses_industry_mapping_when_raw_themes_are_noisy(tmp_path):
    df = pd.DataFrame(
        [
            {
                "股票代码": "600392",
                "名称": "盛和资源",
                "Unnamed: 2": "有色金属-小金属-稀土",
                "地区": "四川省",
                "题材1": "苹果概念",
                "题材2": "国企改革",
                "题材3": "融资融券",
            }
        ]
    )
    payload = build_library(df, source_path=tmp_path / "sample.xlsx", sheet="题材库", source_name="unit")
    entry = payload["by_code"]["600392.SH"]

    assert entry["industry"] == "有色金属-小金属-稀土"
    assert entry["industry_signal_themes"] == ["有色资源"]
    assert entry["primary_signal_themes"] == ["有色资源"]


def test_build_library_drops_noncanonical_trade_themes_from_primary_signal_list(tmp_path):
    df = pd.DataFrame(
        [
            {
                "股票代码": "600234",
                "名称": "科新发展",
                "Unnamed: 2": "建筑装饰-建筑装饰-装饰园林",
                "地区": "上海市",
                "题材1": "物业管理",
                "题材2": "文化传媒概念",
                "题材3": "抖音概念(字节概念)",
                "题材4": "摘帽",
            }
        ]
    )
    payload = build_library(df, source_path=tmp_path / "sample.xlsx", sheet="题材库", source_name="unit")
    entry = payload["by_code"]["600234.SH"]

    assert entry["industry_signal_themes"] == []
    assert entry["primary_signal_themes"] == []
    assert entry["signal_themes"] == []


def test_get_stock_themes_prefers_primary_signal_themes_from_library_file(tmp_path):
    lib_path = tmp_path / "theme_library.json"
    lib_path.write_text(
        json.dumps(
            {
                "meta": {"source_name": "unit"},
                "by_code": {
                    "600522.SH": {
                        "code": "600522.SH",
                        "name": "中天科技",
                        "primary_signal_themes": ["CPO", "铜缆高速连接"],
                        "signal_themes": ["CPO", "铜缆高速连接"],
                        "trade_themes": ["光纤概念", "国企改革"],
                    },
                    "600234.SH": {
                        "code": "600234.SH",
                        "name": "科新发展",
                        "primary_signal_themes": [],
                        "signal_themes": [],
                        "trade_themes": ["物业管理", "文化传媒概念"],
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert get_stock_themes("600522.SH", path=lib_path) == ["CPO", "铜缆高速连接"]
    assert get_stock_themes("600234.SH", path=lib_path) == []
