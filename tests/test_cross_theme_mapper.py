import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qmt_candidate_ranker import score_payload
from stock_theme_library import normalize_stock_code
from tushare_theme_enrichment import fetch_tushare_theme_enrichment


def test_normalize_stock_code_covers_main_board_and_bj():
    assert normalize_stock_code("600183") == "600183.SH"
    assert normalize_stock_code("000001") == "000001.SZ"
    assert normalize_stock_code(1) == "000001.SZ"
    assert normalize_stock_code("830799") == "830799.BJ"


def test_score_payload_uses_tushare_code_theme_map_when_qmt_tags_missing():
    payload = {
        "limit_up_count": 40,
        "candidates": [
            {
                "code": "600703.SH",
                "name": "三安光电",
                "sector_tags": ["上证A股", "沪深A股"],
                "theme_tags": [],
                "concept_tags": [],
                "open_pct": 1.2,
                "pct": 3.5,
                "amount": 3200000000,
                "bid_ask_ratio": 2.1,
                "ask1": 15.01,
                "bid1": 15.0,
                "bid1_vol": 30000,
                "ask1_vol": 10000,
                "board_count": 1,
                "streak": "1天1板",
                "limit_up_type": "换手涨停",
                "limit_up_time": "10:12:00",
            }
        ],
        "limit_up_pool": [],
    }
    mock_tushare = {
        "success": True,
        "trade_date": "20260417",
        "theme_money_rank": [],
        "theme_strength_rank": [],
        "hot_theme_rank": [],
        "market_sentiment": {},
        "strongest_limit_stocks": [],
        "lhb_focus": [],
        "stock_moneyflow_focus": [],
        "market_money_summary": {},
        "sources": {},
        "code_theme_map": {
            "600703.SH": ["CPO", "商业航天"],
        },
        "canonical_hot_theme_rank": [
            {"theme": "CPO", "hot_count": 5, "lead_stock": "三安光电"},
            {"theme": "商业航天", "hot_count": 4, "lead_stock": "三安光电"},
        ],
    }

    with patch("qmt_candidate_ranker.fetch_tushare_theme_enrichment", return_value=mock_tushare), \
         patch("qmt_candidate_ranker.build_ifind_board_context", return_value={}), \
         patch("qmt_candidate_ranker.get_stock_themes", return_value=[]):
        result = score_payload(payload, payload_path="/tmp/20260417/sample.json")

    best = result["strategy_candidate_pool"][0]
    assert best["semantics"]["trade_theme"] == "CPO"
    assert best["semantics"]["theme_hits"][:2] == ["CPO", "商业航天"]
    assert result["market_map"]["canonical_hot_themes"][0]["theme"] == "CPO"


def test_score_payload_uses_local_stock_theme_library_when_tushare_tags_missing():
    payload = {
        "limit_up_count": 18,
        "candidates": [
            {
                "code": "000001.SZ",
                "name": "平安银行",
                "sector_tags": ["深证A股", "沪深A股"],
                "theme_tags": [],
                "concept_tags": [],
                "open_pct": 0.8,
                "pct": 2.1,
                "amount": 2800000000,
                "bid_ask_ratio": 1.6,
                "ask1": 11.21,
                "bid1": 11.20,
                "bid1_vol": 40000,
                "ask1_vol": 20000,
                "board_count": 0,
                "streak": "0天0板",
                "limit_up_type": "趋势票",
                "limit_up_time": "",
            }
        ],
        "limit_up_pool": [],
    }
    mock_tushare = {
        "success": False,
        "reason": "mock-missing",
        "code_theme_map": {},
        "canonical_hot_theme_rank": [],
    }

    with patch("qmt_candidate_ranker.fetch_tushare_theme_enrichment", return_value=mock_tushare), \
         patch("qmt_candidate_ranker.build_ifind_board_context", return_value={}), \
         patch("qmt_candidate_ranker.get_stock_themes", return_value=["跨境支付(CIPS)"]):
        result = score_payload(payload, payload_path="/tmp/20260417/sample.json")

    best = result["strategy_candidate_pool"][0]
    assert best["semantics"]["trade_theme"] == "跨境支付"
    assert "跨境支付" in best["semantics"]["theme_hits"]
    assert best["theme_enrichment"]["theme"] == "跨境支付"
    assert best["theme_enrichment"]["member_count"] == 1


def test_canonicalized_stock_theme_hints_take_priority_over_qmt_theme_tags():
    payload = {
        "limit_up_count": 12,
        "candidates": [
            {
                "code": "600392.SH",
                "name": "盛和资源",
                "sector_tags": ["上证A股", "沪深A股"],
                "theme_tags": ["消费电子概念"],
                "concept_tags": ["消费电子概念"],
                "open_pct": 0.5,
                "pct": 2.8,
                "amount": 2200000000,
                "bid_ask_ratio": 1.3,
                "ask1": 10.01,
                "bid1": 10.0,
                "bid1_vol": 30000,
                "ask1_vol": 10000,
                "board_count": 0,
                "streak": "0天0板",
                "limit_up_type": "趋势票",
                "limit_up_time": "",
            }
        ],
        "limit_up_pool": [],
    }
    mock_tushare = {
        "success": False,
        "reason": "mock-missing",
        "code_theme_map": {},
        "canonical_hot_theme_rank": [],
    }

    with patch("qmt_candidate_ranker.fetch_tushare_theme_enrichment", return_value=mock_tushare), \
         patch("qmt_candidate_ranker.build_ifind_board_context", return_value={}), \
         patch("qmt_candidate_ranker.get_stock_themes", return_value=["有色资源"]):
        result = score_payload(payload, payload_path="/tmp/20260417/sample.json")

    best = result["strategy_candidate_pool"][0]
    assert best["semantics"]["trade_theme"] == "有色资源"
    assert "消费电子" in best["semantics"]["theme_hits"]


def test_fetch_tushare_theme_enrichment_builds_code_theme_map_and_canonical_hot_rank():
    concept_raw = {"code": 0, "data": {"fields": ["name"], "items": [["CPO"], ["PCB"], ["商业航天"]]}}
    ths_index_raw = {"code": 0, "data": {"fields": ["name"], "items": [["光模块"], ["印制电路板"], ["卫星互联网"]]}}
    money_raw = {"code": 0, "data": {"fields": ["industry", "lead_stock", "net_amount", "pct_change", "pct_change_stock", "company_num"], "items": []}}
    limit_raw = {
        "code": 0,
        "data": {
            "fields": ["ts_code", "name", "tag", "limit", "open_num", "lu_desc", "fd_amount"],
            "items": [
                ["600703.SH", "三安光电", "首板", None, 1, "光模块+CPO+商业航天", 5.0],
                ["600183.SH", "生益科技", "首板", None, 1, "PCB+先进封装", 3.0],
                ["300000.SZ", "样本股", "首板", None, 1, "印制电路板+卫星互联网", 2.0],
            ],
        },
    }
    market_raw = {"code": 0, "data": {"fields": ["net_amount"], "items": [[23.5]]}}
    top_inst_raw = {"code": 0, "data": {"fields": ["ts_code", "name", "net_buy", "amount", "buy", "sell"], "items": []}}
    stock_money_raw = {"code": 0, "data": {"fields": ["ts_code", "buy_sm_amount", "buy_md_amount", "buy_lg_amount", "buy_elg_amount", "net_mf_amount"], "items": []}}

    responses = {
        "concept": {"success": True, "raw": concept_raw},
        "ths_index": {"success": True, "raw": ths_index_raw},
        "moneyflow_ind_ths": {"success": True, "raw": money_raw},
        "limit_list_ths": {"success": True, "raw": limit_raw},
        "moneyflow_mkt_dc": {"success": True, "raw": market_raw},
        "top_inst": {"success": True, "raw": top_inst_raw},
        "moneyflow": {"success": True, "raw": stock_money_raw},
    }

    with patch("tushare_theme_enrichment._post", side_effect=lambda api_name, params=None, fields='': responses[api_name]):
        data = fetch_tushare_theme_enrichment("20260417")

    assert data["code_theme_map"]["600703.SH"] == ["CPO", "商业航天"]
    assert data["code_theme_map"]["600183.SH"] == ["PCB"]
    assert {item["theme"] for item in data["canonical_hot_theme_rank"][:3]} >= {"CPO", "PCB", "商业航天"}


if __name__ == "__main__":
    test_normalize_stock_code_covers_main_board_and_bj()
    test_score_payload_uses_tushare_code_theme_map_when_qmt_tags_missing()
    test_score_payload_uses_local_stock_theme_library_when_tushare_tags_missing()
    test_canonicalized_stock_theme_hints_take_priority_over_qmt_theme_tags()
    test_fetch_tushare_theme_enrichment_builds_code_theme_map_and_canonical_hot_rank()
    print('ok')
