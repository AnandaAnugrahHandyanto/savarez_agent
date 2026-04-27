import json
import subprocess
import sys
from functools import partial
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qmt_candidate_ranker import score_payload
from qmt_daily_report import render_daily
from qmt_intraday_refresh import render_intraday
from qmt_intraday_timeline import render_timeline
from qmt_intraday_state_matrix import render_matrix
from qmt_intraday_snapshot_and_refresh import run_pipeline
from qmt_sync_intraday import sync_intraday_bundle
from qmt_intraday_acceptance import validate_sync_bundle
from qmt_intraday_push_change_guard import detect_status as detect_intraday_push_status, extract_push_summary
from ifind_board_enrichment import build_ifind_board_context


def sample_payload():
    return {
        "limit_up_count": 35,
        "candidates": [
            {
                "code": "601778.SH",
                "name": "晶科科技",
                "sector_tags": ["沪深A股", "光伏", "储能"],
                "theme_tags": ["固态电池"],
                "concept_tags": ["固态电池"],
                "open_pct": 1.5,
                "pct": 10.04,
                "amount": 3291803900,
                "bid_ask_ratio": None,
                "stock_status": 5,
                "ask1": 0,
                "bid1": 12.3,
                "bid1_vol": 30000,
                "ask1_vol": 0,
                "limit_up_time": "09:45:03",
                "limit_up_type": "换手涨停",
                "board_count": 1,
                "streak": "1天1板",
            },
            {
                "code": "002580.SZ",
                "name": "圣阳股份",
                "sector_tags": ["沪深A股", "储能", "数据中心"],
                "theme_tags": ["固态电池"],
                "concept_tags": ["固态电池"],
                "open_pct": 3.2,
                "pct": 10.01,
                "amount": 3926483800,
                "bid_ask_ratio": None,
                "stock_status": 5,
                "ask1": 0,
                "bid1": 10.5,
                "bid1_vol": 50000,
                "ask1_vol": 0,
                "limit_up_time": "10:25:00",
                "limit_up_type": "换手涨停",
                "board_count": 3,
                "streak": "4天3板",
            },
            {
                "code": "002455.SZ",
                "name": "百川股份",
                "sector_tags": ["沪深A股", "储能", "锂电池"],
                "theme_tags": ["固态电池"],
                "concept_tags": ["固态电池"],
                "open_pct": 0.5,
                "pct": -0.24,
                "amount": 780793900,
                "bid_ask_ratio": 0.2,
                "stock_status": 0,
                "ask1": 12.29,
                "bid1": 12.28,
                "bid1_vol": 100,
                "ask1_vol": 500,
                "limit_up_time": "",
                "limit_up_type": "炸板",
                "board_count": 0,
                "streak": "0天0板",
            },
            {
                "code": "603799.SH",
                "name": "华友钴业",
                "sector_tags": ["沪深A股", "有色", "钴"],
                "theme_tags": ["有色资源"],
                "concept_tags": ["有色资源"],
                "open_pct": 1.87,
                "pct": 3.03,
                "amount": 7986436400,
                "bid_ask_ratio": 16.3,
                "stock_status": 0,
                "ask1": 64.33,
                "bid1": 64.32,
                "bid1_vol": 1095,
                "ask1_vol": 67,
                "limit_up_time": "",
                "limit_up_type": "趋势票",
                "board_count": 0,
                "streak": "0天0板",
            },
            {
                "code": "601231.SH",
                "name": "环旭电子",
                "sector_tags": ["沪深A股", "消费电子", "苹果"],
                "theme_tags": ["消费电子"],
                "concept_tags": ["消费电子"],
                "open_pct": 1.66,
                "pct": 1.2,
                "amount": 2457664900,
                "bid_ask_ratio": 3.47,
                "stock_status": 0,
                "ask1": 16.32,
                "bid1": 16.31,
                "bid1_vol": 8000,
                "ask1_vol": 2304,
                "limit_up_time": "",
                "limit_up_type": "趋势票",
                "board_count": 0,
                "streak": "0天0板",
            },
        ],
        "limit_up_pool": [
            {
                "code": "601778.SH",
                "name": "晶科科技",
                "sector_tags": ["沪深A股", "光伏", "储能"],
                "theme_tags": ["固态电池"],
                "concept_tags": ["固态电池"],
                "open_pct": 1.5,
                "pct": 10.04,
                "amount": 3291803900,
                "bid_ask_ratio": None,
                "stock_status": 5,
                "ask1": 0,
                "bid1": 12.3,
                "bid1_vol": 30000,
                "ask1_vol": 0,
                "limit_up_time": "09:45:03",
                "limit_up_type": "换手涨停",
                "board_count": 1,
                "streak": "1天1板",
            },
            {
                "code": "002580.SZ",
                "name": "圣阳股份",
                "sector_tags": ["沪深A股", "储能", "数据中心"],
                "theme_tags": ["固态电池"],
                "concept_tags": ["固态电池"],
                "open_pct": 3.2,
                "pct": 10.01,
                "amount": 3926483800,
                "bid_ask_ratio": None,
                "stock_status": 5,
                "ask1": 0,
                "bid1": 10.5,
                "bid1_vol": 50000,
                "ask1_vol": 0,
                "limit_up_time": "10:25:00",
                "limit_up_type": "换手涨停",
                "board_count": 3,
                "streak": "4天3板",
            },
        ],
    }


def test_score_payload_exposes_qmt_realtime_context_and_market_map():
    result = score_payload(sample_payload())

    assert "market_map" in result
    assert "qmt_realtime_context" in result
    assert "intraday_dynamics" in result
    assert "qmt_timeline_score" in result
    assert result["market_map"]["qmt_realtime"]["candidate_snapshot_count"] == 5
    assert result["market_map"]["qmt_realtime"]["auction_strength_count"] == 2
    assert result["market_map"]["qmt_realtime"]["blowup_count"] == 1
    assert result["market_map"]["qmt_realtime"]["first_board_count"] == 1
    assert result["market_map"]["qmt_realtime"]["multi_board_count"] == 1
    assert result["market_map"]["qmt_realtime"]["highest_board"] == 3
    assert result["market_map"]["qmt_realtime"]["sealed_limit_up_count"] == 2
    assert result["market_map"]["qmt_realtime"]["actionable_candidate_count"] == 1
    assert result["intraday_dynamics"]["leader_codes"] == ["601231.SH"]
    assert result["qmt_timeline_score"]["score"] >= 0
    assert result["strategy_candidate_pool"][0]["metrics"]["ask1_vol"] >= 0
    assert "bid1_vol" in result["strategy_candidate_pool"][0]["metrics"]


def test_score_payload_current_baseline_prefers_single_backup_candidate():
    result = score_payload(sample_payload())

    assert [row["code"] for row in result["primary"]] == []
    assert [row["code"] for row in result["backup"]] == ["601231.SH"]
    assert [row["code"] for row in result["observe"]] == []
    assert [row["code"] for row in result["avoid"]] == []
    assert [row["code"] for row in result["strategy_candidate_pool"]] == ["601231.SH"]
    assert [row["code"] for row in result["actionable_buckets"]["do_not_chase"]] == []


def test_score_payload_penalizes_low_relative_activity_and_surfaces_history_metrics(tmp_path):
    root = tmp_path / "qmt_sync" / "reports"
    prev_dir = root / "20260414"
    curr_dir = root / "20260417"
    prev_dir.mkdir(parents=True)
    curr_dir.mkdir(parents=True)

    prev_payload = {
        "limit_up_count": 58,
        "candidates": [
            {
                "code": "600001.SH",
                "name": "大票弱增量",
                "sector_tags": ["沪深A股"],
                "theme_tags": ["铜缆高速连接"],
                "concept_tags": ["铜缆高速连接"],
                "open_pct": 0.3,
                "pct": 0.2,
                "amount": 4_800_000_000,
                "volume": 1_600_000,
                "bid_ask_ratio": 2.0,
                "stock_status": 0,
                "ask1": 20.01,
                "bid1": 20.0,
                "bid1_vol": 5000,
                "ask1_vol": 2000,
            },
            {
                "code": "600002.SH",
                "name": "首板强增量",
                "sector_tags": ["沪深A股"],
                "theme_tags": ["铜缆高速连接"],
                "concept_tags": ["铜缆高速连接"],
                "open_pct": 1.1,
                "pct": 4.5,
                "amount": 900_000_000,
                "volume": 300_000,
                "bid_ask_ratio": 1.4,
                "stock_status": 0,
                "ask1": 10.06,
                "bid1": 10.05,
                "bid1_vol": 8000,
                "ask1_vol": 4000,
            },
        ],
        "limit_up_pool": [],
    }
    curr_payload = {
        "limit_up_count": 58,
        "candidates": [
            {
                "code": "600001.SH",
                "name": "大票弱增量",
                "sector_tags": ["沪深A股"],
                "theme_tags": ["铜缆高速连接"],
                "concept_tags": ["铜缆高速连接"],
                "open_pct": 0.2,
                "pct": 0.5,
                "amount": 4_500_000_000,
                "volume": 1_500_000,
                "bid_ask_ratio": 2.1,
                "stock_status": 0,
                "ask1": 20.01,
                "bid1": 20.0,
                "bid1_vol": 5200,
                "ask1_vol": 2100,
            },
            {
                "code": "600002.SH",
                "name": "首板强增量",
                "sector_tags": ["沪深A股"],
                "theme_tags": ["铜缆高速连接"],
                "concept_tags": ["铜缆高速连接"],
                "open_pct": 2.1,
                "pct": 9.95,
                "amount": 1_800_000_000,
                "volume": 720_000,
                "bid_ask_ratio": 1.6,
                "stock_status": 0,
                "ask1": 10.06,
                "bid1": 10.05,
                "bid1_vol": 8000,
                "ask1_vol": 4000,
            },
        ],
        "limit_up_pool": [
            {
                "code": "600002.SH",
                "name": "首板强增量",
                "sector_tags": ["沪深A股"],
                "theme_tags": ["铜缆高速连接"],
                "concept_tags": ["铜缆高速连接"],
                "open_pct": 2.1,
                "pct": 9.95,
                "amount": 1_800_000_000,
                "volume": 720_000,
                "bid_ask_ratio": 1.6,
                "stock_status": 0,
                "ask1": 10.06,
                "bid1": 10.05,
                "bid1_vol": 8000,
                "ask1_vol": 4000,
            }
        ],
    }

    prev_path = prev_dir / "auction_candidates_main_board_non_st.json"
    curr_path = curr_dir / "auction_candidates_main_board_non_st.json"
    prev_path.write_text(json.dumps(prev_payload, ensure_ascii=False), encoding="utf-8")
    curr_path.write_text(json.dumps(curr_payload, ensure_ascii=False), encoding="utf-8")

    with patch("qmt_candidate_ranker.fetch_tushare_theme_enrichment", return_value={"success": False}), \
         patch("qmt_candidate_ranker.build_ifind_board_context", return_value={"by_code": {}}), \
         patch("qmt_candidate_ranker.get_stock_themes", return_value=[]):
        result = score_payload(curr_payload, payload_path=str(curr_path))

    weak = next(row for row in result["strategy_candidate_pool"] if row["code"] == "600001.SH")
    strong = next(row for row in result["strategy_candidate_pool"] if row["code"] == "600002.SH")

    assert round(weak["metrics"]["amount_ratio_vs_prev"], 4) == 0.9375
    assert round(weak["metrics"]["volume_ratio_vs_prev"], 4) == 0.9375
    assert strong["metrics"]["incremental_amount"] == 900000000.0
    assert "相对量能不足" in weak["vetoes"]
    assert result["strategy_candidate_pool"][0]["code"] == "600002.SH"
    assert result["actionable_strongest"][0]["code"] == "600002.SH"


def test_render_daily_includes_qmt_tushare_and_ifind_structure_sections():
    mock_tushare = {
        "success": True,
        "trade_date": "20260415",
        "theme_money_rank": [],
        "theme_strength_rank": [],
        "hot_theme_rank": [],
        "canonical_hot_theme_rank": [
            {"theme": "CPO", "hot_count": 5, "lead_stock": "中际旭创"},
            {"theme": "商业航天", "hot_count": 4, "lead_stock": "中国卫星"},
        ],
        "market_sentiment": {
            "limit_up_count": 24,
            "first_board_count": 18,
            "multi_board_count": 6,
            "highest_board": 3,
        },
        "strongest_limit_stocks": [
            {"name": "圣阳股份", "open_num": 3, "lu_desc": "固态电池"},
            {"name": "晶科科技", "open_num": 1, "lu_desc": "光伏"},
        ],
        "lhb_focus": [
            {"name": "圣阳股份", "net_buy": 1.25},
            {"name": "晶科科技", "net_buy": 0.88},
        ],
        "stock_moneyflow_focus": [
            {"ts_code": "002580.SZ", "net_mf_amount": 2.5},
            {"ts_code": "601778.SH", "net_mf_amount": 1.7},
        ],
        "market_money_summary": {},
        "sources": {},
    }
    mock_ifind = {
        "probe": {"can_attempt_network": False},
        "by_code": {},
        "market_scope": [],
        "industry_leads": [],
        "theme_candidates": {},
        "missing_core_candidates": [],
        "theme_leaderboard": {"消费电子": [{"code": "601231.SH", "name": "环旭电子"}]},
        "event_signals": {"消费电子": {"report_query_ready": True, "report_hint": "可对 消费电子 或核心股补跑 report_query"}},
    }
    with patch("qmt_candidate_ranker.fetch_tushare_theme_enrichment", return_value=mock_tushare), \
         patch("qmt_candidate_ranker.build_ifind_board_context", return_value=mock_ifind):
        result = score_payload(sample_payload(), payload_path="/tmp/20260415/sample.json")
    report = render_daily(result, "sample.json")

    assert "## 二、市场地图" in report
    assert "### 1) QMT本地竞价口径" in report
    assert "### 2) 外部全市场口径" in report
    assert "QMT实时结构" in report
    assert "QMT时间轴评分：" in report
    assert "IFIND题材前排：601231.SH 环旭电子" in report
    assert "Tushare交叉题材热榜：CPO=5次/代表中际旭创；商业航天=4次/代表中国卫星" in report
    assert "Tushare情绪结构：涨停=24只；首板=18只；连板=6只；最高板=3板" in report
    assert "Tushare涨停焦点：圣阳股份(3板/固态电池)；晶科科技(1板/光伏)" in report
    assert "Tushare龙虎榜焦点：圣阳股份=净买1.25；晶科科技=净买0.88" in report
    assert "Tushare个股资金焦点：002580.SZ=净额2.50；601778.SH=净额1.70" in report
    assert "口径提示：QMT实时结构/候选池来自本地竞价快照；Tushare情绪结构/涨停焦点来自外部全市场快照，两者不是同一口径，不能直接逐项对表。" in report


def test_render_intraday_reports_changes_between_snapshots():
    prev_result = score_payload(sample_payload())
    payload2 = sample_payload()
    for row in payload2["candidates"]:
        if row["code"] == "601231.SH":
            row["pct"] = 2.4
            row["amount"] = 3457664900
    curr_result = score_payload(payload2)
    report = render_intraday(prev_result, curr_result, "prev.json", "curr.json")

    assert "# QMT 盘中二次刷新报告" in report
    assert "## 零、最新窗口变化" in report
    assert "最新盘中流：封单=0；回封=0；炸板=0；承接转强=0；承接转弱=0" in report
    assert "## 一、变化" in report
    assert "## 二、当前最强候选" in report
    assert "QMT实时结构：候选=5只" in report
    assert "主轴焦点：601231.SH" in report
    assert "601231.SH 环旭电子：总分" in report


def test_render_daily_exposes_stock_theme_anchor_and_trade_theme_reason():
    result = {
        "environment": "分歧日",
        "limit_up_count": 12,
        "primary": [],
        "backup": [
            {
                "code": "600392.SH",
                "name": "盛和资源",
                "total_score": 18,
                "board_count": 0,
                "limit_up_type": "趋势票",
                "limit_up_time": "",
                "stock_theme_tags": ["有色资源"],
                "stock_theme_context": {
                    "industry_signal_themes": ["有色资源"],
                    "primary_signal_themes": ["有色资源"],
                    "signal_themes": ["有色资源", "消费电子"],
                },
                "metrics": {"open_pct": 0.5, "pct": 2.8, "amount": 2200000000, "bid_ask_ratio": 1.3},
                "grades": {"amount": 2, "open": 2, "bidask": 2, "rank": 1, "theme_strength": 0, "theme_money": 0, "theme_breadth": 0, "board_alignment": 0},
                "vetoes": [],
                "semantics": {
                    "trade_theme": "有色资源",
                    "chain_role": "主线前排",
                    "primary_sector": "沪深A股",
                    "sector_rank": 1,
                    "theme_hits": ["有色资源", "消费电子"],
                    "theme_source_label": "本地题材库主线",
                    "trade_theme_reason": "优先采用本地题材库主线首位 canonical theme。",
                },
            }
        ],
        "observe": [],
        "avoid": [],
        "market_map": {},
        "sector_profiles": [],
        "actionable_buckets": {"actionable_primary": [], "low_absorb_watch": [], "do_not_chase": []},
        "ifind_board_context": {},
        "qmt_realtime_context": {},
        "intraday_dynamics": {},
        "qmt_timeline_score": {},
    }

    report = render_daily(result, "sample.json")

    assert "行业题材锚点：有色资源" in report
    assert "本地题材库主线：有色资源" in report
    assert "最终交易题材判定：有色资源（优先依据=本地题材库主线；命中链路=有色资源、消费电子；原因=优先采用本地题材库主线首位 canonical theme。" in report


def test_render_intraday_exposes_stock_theme_anchor_and_trade_theme_reason():
    prev_result = {
        'environment': '分歧日',
        'primary': [],
        'backup': [],
        'observe': [],
        'avoid': [],
        'actionable_buckets': {'actionable_primary': [], 'low_absorb_watch': [], 'do_not_chase': []},
        'qmt_realtime_context': {},
        'intraday_dynamics': {},
        'market_map': {},
    }
    curr_result = {
        'environment': '分歧日',
        'primary': [],
        'backup': [
            {
                'code': '600522.SH',
                'name': '中天科技',
                'final_action': '备选',
                'total_score': 19,
                'stock_theme_tags': ['铜缆高速连接', 'CPO'],
                'stock_theme_context': {
                    'industry_signal_themes': ['铜缆高速连接'],
                    'primary_signal_themes': ['铜缆高速连接', 'CPO'],
                    'signal_themes': ['铜缆高速连接', 'CPO', '商业航天'],
                },
                'semantics': {
                    'chain_role': '主线前排',
                    'trade_theme': '铜缆高速连接',
                    'theme_hits': ['铜缆高速连接', 'CPO', '商业航天'],
                    'theme_source_label': '本地题材库主线',
                    'trade_theme_reason': '行业锚点与主线候选一致，优先命中铜缆高速连接。',
                },
                'metrics': {'open_pct': 1.1, 'pct': 4.2, 'amount': 3600000000, 'bid_ask_ratio': 1.8},
                'limit_up_type': '趋势票',
                'limit_up_time': '',
                'vetoes': [],
            }
        ],
        'observe': [],
        'avoid': [],
        'actionable_buckets': {'actionable_primary': [], 'low_absorb_watch': [], 'do_not_chase': []},
        'qmt_realtime_context': {},
        'intraday_dynamics': {},
        'market_map': {},
        'strategy_candidate_pool': [],
    }

    report = render_intraday(prev_result, curr_result, 'prev.json', 'curr.json')

    assert '行业题材锚点：铜缆高速连接' in report
    assert '本地题材库主线：铜缆高速连接、CPO' in report
    assert '最终交易题材判定：铜缆高速连接（优先依据=本地题材库主线；命中链路=铜缆高速连接、CPO、商业航天；原因=行业锚点与主线候选一致，优先命中铜缆高速连接。' in report


def test_render_intraday_latest_window_summary_uses_shared_flow_signals():
    prev_result = {
        'environment': '分歧日',
        'primary': [],
        'backup': [
            {
                'code': '001001.SZ', 'name': '龙一', 'final_action': '备选', 'total_score': 18,
                'semantics': {'chain_role': '主线前排', 'trade_theme': '消费电子'},
                'metrics': {'open_pct': 1.2, 'pct': 8.6, 'amount': 20.0, 'bid_ask_ratio': 1.0, 'ask1_vol': 500},
                'limit_up_type': '', 'limit_up_time': '', 'vetoes': []
            },
            {
                'code': '001002.SZ', 'name': '承接票', 'final_action': '备选', 'total_score': 17,
                'semantics': {'chain_role': '主线前排', 'trade_theme': '消费电子'},
                'metrics': {'open_pct': 0.8, 'pct': 3.9, 'amount': 18.0, 'bid_ask_ratio': 0.8, 'ask1_vol': 600},
                'limit_up_type': '', 'limit_up_time': '', 'vetoes': []
            },
        ],
        'observe': [],
        'avoid': [],
        'actionable_buckets': {'actionable_primary': [], 'low_absorb_watch': [], 'do_not_chase': []},
        'qmt_realtime_context': {'candidate_snapshot_count': 2, 'auction_strength_count': 0, 'blowup_count': 0, 'highest_board': 2},
        'intraday_dynamics': {'leader_codes': ['001001.SZ'], 'upgrade_watch': [], 'downgrade_watch': []},
        'strategy_candidate_pool': [],
    }
    curr_result = {
        'environment': '分歧日',
        'primary': [
            {
                'code': '001001.SZ', 'name': '龙一', 'final_action': '主攻', 'total_score': 22,
                'semantics': {'chain_role': '主线龙头候选', 'trade_theme': '消费电子'},
                'metrics': {'open_pct': 1.2, 'pct': 10.0, 'amount': 25.0, 'bid_ask_ratio': 8.8, 'ask1_vol': 0},
                'limit_up_type': '', 'limit_up_time': '09:41:03', 'vetoes': []
            }
        ],
        'backup': [
            {
                'code': '001002.SZ', 'name': '承接票', 'final_action': '备选', 'total_score': 19,
                'semantics': {'chain_role': '主线前排', 'trade_theme': '消费电子'},
                'metrics': {'open_pct': 0.8, 'pct': 5.7, 'amount': 19.0, 'bid_ask_ratio': 2.3, 'ask1_vol': 280},
                'limit_up_type': '', 'limit_up_time': '', 'vetoes': []
            },
        ],
        'observe': [],
        'avoid': [],
        'actionable_buckets': {'actionable_primary': [{'code': '001001.SZ', 'name': '龙一', 'theme': '消费电子'}], 'low_absorb_watch': [{'code': '001002.SZ', 'name': '承接票'}], 'do_not_chase': []},
        'qmt_realtime_context': {'candidate_snapshot_count': 2, 'auction_strength_count': 1, 'blowup_count': 0, 'highest_board': 3},
        'intraday_dynamics': {'leader_codes': ['001001.SZ'], 'upgrade_watch': [{'code': '001002.SZ', 'name': '承接票'}], 'downgrade_watch': []},
        'strategy_candidate_pool': [],
    }
    prev_result['strategy_candidate_pool'] = prev_result['backup']
    curr_result['strategy_candidate_pool'] = curr_result['primary'] + curr_result['backup']

    report = render_intraday(prev_result, curr_result, 'prev.json', 'curr.json')

    assert '## 零、最新窗口变化' in report
    assert '自动动作：当前可执行主攻' in report
    assert '当前最强：001001.SZ 龙一 / 主攻' in report
    assert '最新盘中流：封单=1；回封=0；炸板=0；承接转强=1；承接转弱=0' in report
    assert '001001.SZ 龙一 封单' in report
    assert '001002.SZ 承接票 承接转强' in report


def test_tushare_enrichment_exposes_market_sentiment_and_focus_fields():
    from tushare_theme_enrichment import fetch_tushare_theme_enrichment

    concept_raw = {"code": 0, "data": {"fields": ["name"], "items": [["消费电子"]]}}
    ths_index_raw = {"code": 0, "data": {"fields": ["name"], "items": [["消费电子"]]}}
    money_raw = {"code": 0, "data": {"fields": ["industry", "lead_stock", "net_amount", "pct_change", "pct_change_stock", "company_num"], "items": [["消费电子", "环旭电子", 12.0, 2.0, 3.0, 10]]}}
    limit_raw = {"code": 0, "data": {"fields": ["ts_code", "name", "tag", "limit", "open_num", "lu_desc", "fd_amount"], "items": [["002580.SZ", "圣阳股份", "涨停", "U", 3, "固态电池", 5.0], ["601778.SH", "晶科科技", "涨停", "U", 1, "光伏", 3.0]]}}
    market_raw = {"code": 0, "data": {"fields": ["net_amount"], "items": [[23.5]]}}
    top_inst_raw = {"code": 0, "data": {"fields": ["ts_code", "name", "net_buy", "amount", "buy", "sell"], "items": [["002580.SZ", "圣阳股份", 1.25, 5.0, 3.0, 1.75]]}}
    stock_money_raw = {"code": 0, "data": {"fields": ["ts_code", "buy_sm_amount", "buy_md_amount", "buy_lg_amount", "buy_elg_amount", "net_mf_amount"], "items": [["002580.SZ", 1.0, 2.0, 3.0, 4.0, 2.5]]}}

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
        data = fetch_tushare_theme_enrichment("20260415")

    assert data["market_sentiment"]["limit_up_count"] == 2
    assert data["market_sentiment"]["first_board_count"] == 1
    assert data["market_sentiment"]["multi_board_count"] == 1
    assert data["market_sentiment"]["highest_board"] == 3
    assert data["strongest_limit_stocks"][0]["name"] == "圣阳股份"
    assert data["lhb_focus"][0]["name"] == "圣阳股份"
    assert data["stock_moneyflow_focus"][0]["ts_code"] == "002580.SZ"


def test_ifind_board_context_exposes_safe_second_round_slots_without_network():
    context = build_ifind_board_context([])
    assert "theme_leaderboard" in context
    assert "event_signals" in context


def test_render_state_matrix_exposes_automatic_decision_and_transitions():
    def fake_row(code, name, action, score, role='主线龙头候选', theme='消费电子', vetoes=None, dragon=3, pct=1.0):
        return {
            'code': code,
            'name': name,
            'final_action': action,
            'total_score': score,
            'cluster_score': score,
            'dragon_yes_count': dragon,
            'vetoes': vetoes or [],
            'semantics': {'chain_role': role, 'trade_theme': theme},
            'metrics': {'pct': pct},
        }

    items = [
        ('0930', {'601231.SH': fake_row('601231.SH', '环旭电子', '备选', 18, role='主线前排', dragon=2)}),
        ('1000', {'601231.SH': fake_row('601231.SH', '环旭电子', '主攻', 21, role='主线龙头候选', dragon=3)}),
    ]
    report = render_matrix(items)

    assert '# QMT 自动状态迁移决策引擎' in report
    assert '## IM 极简摘要' in report
    assert '## 完整报告' in report
    assert '自动动作：重写主攻' in report
    assert '当前最强：601231.SH 环旭电子 / 主攻' in report
    assert '最新盘中流：封单=0；回封=0；炸板=0；承接转强=0；承接转弱=0' in report
    assert '自动动作：重写主攻' in report
    assert '601231.SH 环旭电子' in report
    assert '0930 → 1000 | 升级' in report
    assert '动作 备选 → 主攻' in report


def test_render_daily_and_intraday_expose_action_templates_for_watch_dont_chase_and_avoid():
    result = {
        'environment': '分歧日',
        'limit_up_count': 18,
        'primary': [],
        'backup': [],
        'observe': [
            {
                'code': '001001.SZ',
                'name': '观察票',
                'total_score': 16,
                'board_count': 1,
                'limit_up_type': '换手涨停',
                'limit_up_time': '09:45:00',
                'stock_theme_tags': ['消费电子'],
                'stock_theme_context': {'industry_signal_themes': ['消费电子'], 'primary_signal_themes': ['消费电子'], 'signal_themes': ['消费电子']},
                'metrics': {'open_pct': 0.8, 'pct': 3.2, 'amount': 1800000000, 'bid_ask_ratio': 1.4},
                'grades': {'amount': 2, 'open': 2, 'bidask': 2, 'rank': 2, 'theme_strength': 0, 'theme_money': 0, 'theme_breadth': 0, 'board_alignment': 0},
                'vetoes': [],
                'semantics': {'trade_theme': '消费电子', 'chain_role': '主线前排', 'primary_sector': '沪深A股', 'sector_rank': 1, 'theme_hits': ['消费电子'], 'theme_source_label': '本地题材库主线', 'trade_theme_reason': '优先采用本地题材库主线首位 canonical theme。'},
            }
        ],
        'avoid': [
            {
                'code': '001003.SZ',
                'name': '回避票',
                'total_score': 10,
                'board_count': 0,
                'limit_up_type': '趋势票',
                'limit_up_time': '',
                'metrics': {'open_pct': 0.2, 'pct': 1.1, 'amount': 900000000, 'bid_ask_ratio': 0.7},
                'grades': {'amount': 1, 'open': 1, 'bidask': 1, 'rank': 3, 'theme_strength': 0, 'theme_money': 0, 'theme_breadth': 0, 'board_alignment': 0},
                'vetoes': ['承接不足', '相对量能不足'],
                'semantics': {'trade_theme': '半导体', 'chain_role': '非核心', 'primary_sector': '沪深A股', 'sector_rank': 3, 'theme_hits': ['半导体'], 'theme_source_label': 'QMT题材/概念标签', 'trade_theme_reason': '本地题材库主线缺失，回退到 QMT 显式题材/概念标签。'},
                'action_label': '回避',
                'action_reason': '承接不足、相对量能不足',
                'action_plan': '直接回避，除非承接与题材地位明显修复。',
            }
        ],
        'market_map': {'reason_tag_counts': [('开盘', 2), ('龙头三问', 1)]},
        'sector_profiles': [],
        'actionable_buckets': {
            'actionable_primary': [],
            'low_absorb_watch': [{'code': '001001.SZ', 'name': '观察票', 'theme': '消费电子', 'role': '主线前排', 'action_label': '低吸观察', 'action_reason': '当前无唯一主攻，且尚未脱离观察位。', 'action_reason_tags': ['开盘'], 'action_plan': '只等回踩承接确认后的低吸，不追高、不抢封。'}],
            'do_not_chase': [{'code': '001002.SZ', 'name': '禁追票', 'theme': '消费电子', 'board_count': 2, 'limit_up_type': '换手涨停', 'action_label': '禁追', 'action_reason': '封死不给换手。', 'action_reason_tags': ['封板'], 'action_plan': '禁止追价，等炸板回封或次日弱转强再评估。'}],
        },
        'ifind_board_context': {},
        'qmt_realtime_context': {},
        'intraday_dynamics': {},
        'qmt_timeline_score': {},
    }

    daily_report = render_daily(result, 'sample.json')
    intraday_report = render_intraday({'environment': '分歧日', 'primary': [], 'backup': [], 'observe': [], 'avoid': [], 'actionable_buckets': {'actionable_primary': [], 'low_absorb_watch': [], 'do_not_chase': []}, 'qmt_realtime_context': {}, 'intraday_dynamics': {}, 'market_map': {}}, result, 'prev.json', 'curr.json')

    assert '低吸观察：001001.SZ 观察票（消费电子，主线前排，标签=开盘；原因=当前无唯一主攻，且尚未脱离观察位。；计划=只等回踩承接确认后的低吸，不追高、不抢封。）' in daily_report
    assert '禁追：001002.SZ 禁追票（消费电子，2板，标签=封板；原因=封死不给换手。；计划=禁止追价，等炸板回封或次日弱转强再评估。）' in daily_report
    assert 'QMT动作原因标签：开盘=2次；龙头三问=1次' in daily_report
    assert '回避理由样本：001003.SZ 回避票（题材=半导体；原因=承接不足、相对量能不足；计划=直接回避，除非承接与题材地位明显修复。）' in daily_report
    assert '低吸观察：001001.SZ 观察票（标签=开盘；原因=当前无唯一主攻，且尚未脱离观察位。；计划=只等回踩承接确认后的低吸，不追高、不抢封。）' in intraday_report
    assert '禁追：001002.SZ 禁追票（标签=封板；原因=封死不给换手。；计划=禁止追价，等炸板回封或次日弱转强再评估。）' in intraday_report


def test_render_state_matrix_im_summary_tracks_seal_reseal_blowup_and_support_flow():
    def fake_row(
        code,
        name,
        action,
        score,
        *,
        pct,
        ratio,
        ask1_vol,
        limit_up_type='',
        limit_up_time='',
        role='主线龙头候选',
        theme='消费电子',
    ):
        return {
            'code': code,
            'name': name,
            'final_action': action,
            'total_score': score,
            'cluster_score': score,
            'dragon_yes_count': 3,
            'vetoes': [],
            'semantics': {'chain_role': role, 'trade_theme': theme},
            'metrics': {'pct': pct, 'bid_ask_ratio': ratio, 'ask1_vol': ask1_vol},
            'limit_up_type': limit_up_type,
            'limit_up_time': limit_up_time,
        }

    items = [
        ('0930', {
            '001001.SZ': fake_row('001001.SZ', '龙一', '备选', 18, pct=8.5, ratio=1.2, ask1_vol=300),
            '001002.SZ': fake_row('001002.SZ', '承接票', '备选', 17, pct=4.2, ratio=2.6, ask1_vol=400),
        }),
        ('0940', {
            '001001.SZ': fake_row('001001.SZ', '龙一', '主攻', 22, pct=10.0, ratio=9.6, ask1_vol=0, limit_up_time='09:40:01'),
            '001002.SZ': fake_row('001002.SZ', '承接票', '备选', 17, pct=4.0, ratio=0.7, ask1_vol=500),
        }),
        ('1000', {
            '001001.SZ': fake_row('001001.SZ', '龙一', '禁追观察', 16, pct=7.3, ratio=0.6, ask1_vol=800, limit_up_type='炸板'),
            '001002.SZ': fake_row('001002.SZ', '承接票', '备选', 18, pct=5.6, ratio=2.1, ask1_vol=260),
        }),
        ('1015', {
            '001001.SZ': fake_row('001001.SZ', '龙一', '主攻', 23, pct=10.0, ratio=8.8, ask1_vol=0, limit_up_time='10:15:18'),
            '001002.SZ': fake_row('001002.SZ', '承接票', '备选', 19, pct=6.1, ratio=3.2, ask1_vol=180),
        }),
    ]

    report = render_matrix(items)

    assert '最新盘中流：封单=0；回封=1；炸板=0；承接转强=1；承接转弱=0' in report
    assert '### 3) 全日累计盘中流' in report
    assert '- 全日累计：封单=1；回封=1；炸板=1；承接转强=2；承接转弱=1' in report
    assert '001001.SZ 龙一 回封' in report
    assert '001002.SZ 承接票 承接转强' in report


def test_render_state_matrix_im_summary_exposes_theme_diagnosis_and_action_template():
    items = [
        ('0930', {'600392.SH': {
            'code': '600392.SH',
            'name': '盛和资源',
            'final_action': '禁追观察',
            'total_score': 24,
            'cluster_score': 18,
            'dragon_yes_count': 2,
            'vetoes': ['分歧日低开，仅保留观察'],
            'semantics': {
                'chain_role': '主线龙头候选',
                'trade_theme': '有色资源',
                'theme_hits': ['有色资源'],
                'theme_source_label': '本地题材库主线',
                'trade_theme_reason': '优先采用本地题材库主线首位 canonical theme。',
            },
            'stock_theme_context': {'industry_signal_themes': ['有色资源'], 'primary_signal_themes': ['有色资源']},
            'action_label': '禁追观察',
            'action_reason': '分歧日低开，仅保留观察',
            'action_reason_tags': ['开盘', '龙头三问'],
            'action_plan': '只观察不追高，等回踩承接确认后再评估。',
            'metrics': {'pct': 3.0, 'bid_ask_ratio': 1.2, 'ask1_vol': 1200},
        }})
    ]

    report = render_matrix(items)

    assert '题材判定：有色资源（优先依据=本地题材库主线；行业锚点=有色资源；命中链路=有色资源）' in report
    assert '动作模板：禁追观察（标签=开盘/龙头三问；原因=分歧日低开，仅保留观察；计划=只观察不追高，等回踩承接确认后再评估。）' in report


def test_score_payload_sets_action_template_from_final_action():
    result = score_payload(sample_payload())
    best = result['strategy_candidate_pool'][0]
    assert best['final_action'] == '备选'
    assert best['action_label'] == '备选'


def test_score_payload_exposes_fixed_action_reason_tags_and_counts():
    payload = sample_payload()
    payload['candidates'].append({
        'code': '600522.SH',
        'name': '中天科技',
        'sector_tags': ['沪深A股', '铜缆高速连接', 'CPO'],
        'theme_tags': ['铜缆高速连接'],
        'concept_tags': ['铜缆高速连接'],
        'open_pct': -1.2,
        'pct': 1.3,
        'amount': 2500000000,
        'bid_ask_ratio': 1.2,
        'stock_status': 0,
        'ask1': 16.32,
        'bid1': 16.31,
        'bid1_vol': 8000,
        'ask1_vol': 2304,
        'limit_up_time': '',
        'limit_up_type': '趋势票',
        'board_count': 0,
        'streak': '0天0板',
    })
    result = score_payload(payload)
    target = next(row for row in result['strategy_candidate_pool'] if row['code'] == '600522.SH')
    avoid = next(row for row in result['strategy_candidate_pool'] if row['code'] == '601231.SH')
    assert '开盘' in target['action_reason_tags']
    assert '龙头三问' in avoid['action_reason_tags']
    tag_counts = dict(result['market_map']['reason_tag_counts'])
    assert result['market_map']['reason_tag_counts'] == [('开盘', 1), ('龙头三问', 1)]
    assert tag_counts['开盘'] >= 1
    assert tag_counts['龙头三问'] >= 1


def test_render_timeline_includes_stability_metrics():
    base = score_payload(sample_payload())
    payload2 = sample_payload()
    for row in payload2["candidates"]:
        if row["code"] == "601231.SH":
            row["pct"] = 2.4
            row["amount"] = 3457664900
    later = score_payload(payload2)
    report = render_timeline([
        ("0930", Path("a.json"), base),
        ("1000", Path("b.json"), later),
    ])

    assert "# QMT 全日盘中轨迹汇总" in report
    assert "主轴稳定性：" in report
    assert "最强切换=" in report
    assert "焦点切换=" in report


def test_snapshot_pipeline_generates_refresh_timeline_matrix_and_status(tmp_path):
    export_dir = tmp_path / "exports" / "20260414"
    report_dir = tmp_path / "reports" / "20260414"
    export_dir.mkdir(parents=True)
    report_dir.mkdir(parents=True)

    source = export_dir / "auction_candidates_main_board_non_st.json"
    source.write_text('{"limit_up_count": 0, "candidates": [], "limit_up_pool": []}', encoding="utf-8")
    older = export_dir / "auction_candidates_main_board_non_st_0926.json"
    older.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    calls = []

    def fake_run(cmd, check=True):
        calls.append(cmd)
        out_path = Path(cmd[-1])
        out_path.write_text("ok", encoding="utf-8")

    with patch("qmt_intraday_snapshot_and_refresh.subprocess.run", side_effect=fake_run):
        status = run_pipeline(export_dir, report_dir, python_bin="python", tag="1000")

    tagged = export_dir / "auction_candidates_main_board_non_st_1000.json"
    assert tagged.exists()
    assert status["ok"] is True
    assert status["tag"] == "1000"
    assert status["snapshot_path"].endswith("auction_candidates_main_board_non_st_1000.json")
    assert status["refresh_report"].endswith("intraday_refresh_report.txt")
    assert status["timeline_report"].endswith("intraday_timeline_report.txt")
    assert status["matrix_report"].endswith("intraday_state_matrix_report.txt")

    called_scripts = [Path(cmd[1]).name for cmd in calls]
    assert called_scripts == [
        "qmt_intraday_refresh.py",
        "qmt_intraday_timeline.py",
        "qmt_intraday_state_matrix.py",
    ]

    status_json = tmp_path / "intraday_refresh_last.json"
    assert status_json.exists()
    assert '"ok": true' in status_json.read_text(encoding="utf-8")


def test_sync_intraday_bundle_pulls_reports_status_and_panel(tmp_path):
    out_dir = tmp_path / "qmt_sync" / "reports"
    sync_root = tmp_path / "qmt_sync"
    copied = []

    def fake_run(cmd):
        copied.append(cmd[-1])
        Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(cmd[-1]).write_text(f"copied:{Path(cmd[-1]).name}", encoding="utf-8")

    result = sync_intraday_bundle(
        host="127.0.0.1",
        user="mac",
        password="test",
        date="20260414",
        out_dir=out_dir,
        sync_root=sync_root,
        run_fn=fake_run,
        sync_snapshots=False,
    )

    assert result["intraday_status_path"].endswith("intraday_refresh_last.json")
    assert result["status_panel_path"].endswith("status_panel.txt")
    assert result["intraday_refresh_report"].endswith("intraday_refresh_report.txt")
    assert result["intraday_timeline_report"].endswith("intraday_timeline_report.txt")
    assert result["intraday_state_matrix_report"].endswith("intraday_state_matrix_report.txt")
    assert result["intraday_status_changed"] is True
    assert result["status_panel_changed"] is True
    assert len(copied) == 5
    assert (sync_root / "intraday_refresh_last.json").exists()
    assert (sync_root / "status_panel.txt").exists()
    assert (out_dir / "20260414" / "intraday_state_matrix_report.txt").exists()


def test_validate_sync_bundle_checks_status_and_reports(tmp_path):
    sync_root = tmp_path / "qmt_sync"
    report_dir = sync_root / "reports" / "20260414"
    report_dir.mkdir(parents=True)
    sync_root.mkdir(parents=True, exist_ok=True)

    (sync_root / "intraday_refresh_last.json").write_text('{"ok": true, "tag": "2200"}', encoding="utf-8")
    (sync_root / "status_panel.txt").write_text("# QMT 自动化状态面板", encoding="utf-8")
    (report_dir / "intraday_refresh_report.txt").write_text("# QMT 盘中二次刷新报告", encoding="utf-8")
    (report_dir / "intraday_timeline_report.txt").write_text("# QMT 全日盘中轨迹汇总", encoding="utf-8")
    (report_dir / "intraday_state_matrix_report.txt").write_text("# QMT 自动状态迁移决策引擎", encoding="utf-8")

    result = validate_sync_bundle(sync_root=sync_root, date="20260414")

    assert result["ok"] is True
    assert result["missing"] == []
    assert result["intraday_status_ok"] is True
    assert result["status_panel_present"] is True


def test_sync_intraday_bundle_accepts_legacy_state_matrix_remote_name(tmp_path):
    out_dir = tmp_path / "qmt_sync" / "reports"
    sync_root = tmp_path / "qmt_sync"

    def fake_run(cmd):
        remote = cmd[-2]
        local = Path(cmd[-1])
        if remote.endswith("intraday_state_matrix_report.txt"):
            raise subprocess.CalledProcessError(1, cmd)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(f"copied:{Path(local).name}", encoding="utf-8")

    result = sync_intraday_bundle(
        host="127.0.0.1",
        user="mac",
        password="test",
        date="20260414",
        out_dir=out_dir,
        sync_root=sync_root,
        run_fn=fake_run,
        sync_snapshots=False,
    )

    assert result["intraday_state_matrix_report"].endswith("intraday_state_matrix_report.txt")
    assert (out_dir / "20260414" / "intraday_state_matrix_report.txt").exists()


def test_sync_intraday_bundle_supports_wrapped_runner_when_sync_snapshots_enabled(tmp_path):
    out_dir = tmp_path / "qmt_sync" / "reports"
    sync_root = tmp_path / "qmt_sync"
    copied = []

    def fake_run(cmd, copied):
        copied.append(cmd)
        remote = cmd[-2]
        local = Path(cmd[-1])
        if remote.endswith("auction_candidates_main_board_non_st_*.json"):
            local.mkdir(parents=True, exist_ok=True)
            (local / "auction_candidates_main_board_non_st_1000.json").write_text("{}", encoding="utf-8")
            return
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(f"copied:{local.name}", encoding="utf-8")

    wrapped_run = partial(fake_run, copied=copied)

    result = sync_intraday_bundle(
        host="127.0.0.1",
        user="mac",
        password="test",
        date="20260414",
        out_dir=out_dir,
        sync_root=sync_root,
        run_fn=wrapped_run,
        sync_snapshots=True,
    )

    assert any(cmd[-2].endswith("auction_candidates_main_board_non_st_*.json") for cmd in copied)
    assert (out_dir / "20260414" / "auction_candidates_main_board_non_st_1000.json").exists()
    assert result["intraday_status_changed"] is True


def test_intraday_push_change_guard_detects_material_change_and_commit_state(tmp_path):
    report_dir = tmp_path / "qmt_sync" / "reports" / "20260418"
    report_dir.mkdir(parents=True)
    report_path = report_dir / "intraday_state_matrix_report.txt"
    state_path = tmp_path / "qmt_sync" / "reports" / ".last_feishu_intraday_state_matrix.json"
    report_path.write_text("# QMT 自动状态迁移决策引擎\n\n> 仅留备选\n", encoding="utf-8")

    status, current_hash, state = detect_intraday_push_status(report_path, state_path)
    assert status == "CHANGED"
    assert current_hash
    state_path.write_text(__import__('json').dumps(state, ensure_ascii=False), encoding="utf-8")

    status2, current_hash2, _ = detect_intraday_push_status(report_path, state_path)
    assert status2 == "UNCHANGED"
    assert current_hash2 == current_hash


def test_extract_push_summary_reads_theme_action_and_reason_tags_from_im_summary():
    report = """# QMT 自动状态迁移决策引擎

## IM 极简摘要
- 自动动作：仅观察
- 当前最强：600392.SH 盛和资源 / 禁追观察
- 最新盘中流：封单=0；回封=0；炸板=0；承接转强=0；承接转弱=1
- 最新焦点：600522.SH 中天科技 承接转弱
- 题材判定：有色资源（优先依据=本地题材库主线；行业锚点=有色资源；命中链路=有色资源）
- 动作模板：禁追观察（标签=开盘/龙头三问；原因=分歧日低开，仅保留观察；计划=只观察不追高，等回踩承接确认后再评估。）
- 最新快照：2200 / 快照总数=3
"""
    summary = extract_push_summary(report)
    assert summary['action_line'] == '自动动作：仅观察'
    assert summary['best_line'] == '当前最强：600392.SH 盛和资源 / 禁追观察'
    assert summary['theme_line'].startswith('题材判定：有色资源')
    assert summary['template_line'].startswith('动作模板：禁追观察')
    assert summary['reason_tags'] == ['开盘', '龙头三问']


if __name__ == "__main__":
    test_score_payload_exposes_qmt_realtime_context_and_market_map()
    test_score_payload_current_baseline_prefers_single_backup_candidate()
    test_render_daily_includes_qmt_tushare_and_ifind_structure_sections()
    test_render_intraday_reports_changes_between_snapshots()
    test_tushare_enrichment_exposes_market_sentiment_and_focus_fields()
    test_ifind_board_context_exposes_safe_second_round_slots_without_network()
    test_render_timeline_includes_stability_metrics()
    test_render_state_matrix_exposes_automatic_decision_and_transitions()
    print("ok")
