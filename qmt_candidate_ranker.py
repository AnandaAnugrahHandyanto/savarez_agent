#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Read QMT candidate pool JSON and normalize it to the user's
A-share shortline auction-leader strategy result shape.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from qmt_theme_enrichment import merge_theme_enrichment, summarize_theme_enrichment
from ifind_board_enrichment import build_ifind_board_context
from tushare_theme_enrichment import fetch_tushare_theme_enrichment
from cross_theme_mapper import merge_theme_lists
from stock_theme_library import get_stock_theme_entry, get_stock_themes, summarize_theme_library


THEME_RULES = {
    "CPO": ["中际", "新易盛", "天孚", "光模块", "光通信", "光芯片", "cpo", "共封装光学", "硅光", "800g", "1.6t"],
    "PCB": ["沪电股份", "深南电路", "胜宏科技", "生益科技", "pcb", "pcb概念", "fpc", "印制电路板", "覆铜板", "高频高速板"],
    "商业航天": ["中国卫星", "航天电子", "上海瀚讯", "商业航天", "卫星互联网", "低轨卫星", "卫星导航", "商业卫星", "卫星", "航天"],
    "低空经济": ["万丰奥威", "中信海直", "宗申动力", "低空经济", "飞行汽车", "evtol", "通用航空", "低空飞行"],
    "AI算力": ["寒武纪", "海光", "工业富联", "浪潮信息", "中科曙光", "算力", "液冷", "服务器", "数据中心", "东数西算", "gpu"],
    "AI应用": ["deepseek", "ai应用", "ai智能体", "大模型", "多模态", "aigc应用", "kimi", "豆包"],
    "铜缆高速连接": ["中天科技", "沃尔核材", "神宇", "华丰科技", "胜蓝", "铜缆", "高速连接", "连接器", "线缆", "高速线", "dac"],
    "半导体": ["寒武纪", "半导体", "芯片", "芯片概念", "存储", "封测", "晶圆", "光刻", "eda", "第三代半导体", "先进封装"],
    "消费电子": ["环旭电子", "立讯精密", "歌尔股份", "鹏鼎控股", "消费电子", "消费电子概念", "苹果", "ai手机", "折叠屏", "mr", "vr"],
    "机器人": ["埃斯顿", "绿的谐波", "机器人", "机器人概念", "人形", "人形机器人", "减速器", "机器视觉", "自动化", "工业母机"],
    "固态电池": ["天齐锂业", "赣锋锂业", "宁德时代", "固态电池", "锂电", "锂电池概念", "钠离子电池", "电池", "储能", "钠电", "磷酸铁锂", "高压快充", "充电桩"],
    "新能源汽车": ["比亚迪", "赛力斯", "拓普集团", "新能源车", "新能源汽车", "比亚迪概念", "汽车零部件", "整车", "智能驾驶", "无人驾驶", "汽配"],
    "跨境支付": ["跨境支付", "cips", "数字货币", "人民币跨境"],
    "医药": ["药明康德", "恒瑞医药", "百济神州", "片仔癀", "医药", "创新药", "中药", "医疗器械", "减肥药", "cro", "cxo"],
    "军工": ["中航成飞", "中无人机", "军工", "军工信息化", "大飞机"],
    "有色资源": ["华友钴业", "包钢股份", "洛阳钼业", "北方稀土", "天通股份", "有色", "稀土", "钴", "锂", "小金属", "黄金", "铜", "铝"],
}

THRESHOLDS = {
    "environment": {
        "strong_limit_up_count": 60,
        "disagreement_limit_up_count": 25,
    },
    "hard_filter": {
        "min_amount": 500_000_000,
        "min_auction_amount": 100_000,
        "min_open_pct": -1.5,
        "max_open_pct": 6.5,
        "min_bid_ask_ratio": 0.8,
    },
    "dragon": {
        "min_amount": 1_500_000_000,
        "min_auction_amount": 20_000_000,
        "min_bid_ask_ratio": 1.1,
        "max_premium_open_pct": 4.5,
    },
    "scoring": {
        "amount_a": 3_000_000_000,
        "amount_b": 1_500_000_000,
        "open_a_low": 1.0,
        "open_a_high": 4.0,
        "open_b_low": 0.3,
        "open_b_high": 5.5,
        "bidask_a": 1.8,
        "bidask_b": 1.1,
    },
    "relative_activity": {
        "score_a_ratio": 1.5,
        "score_b_ratio": 1.15,
        "score_a_incremental_amount": 1_000_000_000,
        "score_b_incremental_amount": 300_000_000,
        "veto_min_amount_ratio": 1.1,
        "veto_min_volume_ratio": 1.1,
        "veto_min_pct": 6.0,
    },
}

GENERIC_NAMES = {
    "中国平安", "招商银行", "中国海油", "长江电力", "工商银行", "建设银行", "农业银行", "中国银行",
    "中国石油", "中国石化", "中国神华", "贵州茅台", "五粮液", "宁德时代", "美的集团", "格力电器",
}
REASON_TAG_RULES = {
    "承接": ("承接",),
    "量能": ("量能", "增量", "成交额", "挂单金额"),
    "开盘": ("高开", "低开", "开盘"),
    "封板": ("封死", "一字", "炸板", "封板", "回封"),
    "龙头三问": ("龙头三问",),
}
REASON_TAG_ORDER = tuple(REASON_TAG_RULES)


def classify_reason_tags(reasons: list[str] | None) -> list[str]:
    tags: list[str] = []
    for reason in reasons or []:
        text = str(reason or "")
        if not text:
            continue
        for tag, keywords in REASON_TAG_RULES.items():
            if tag in tags:
                continue
            if any(keyword in text for keyword in keywords):
                tags.append(tag)
    return tags


def summarize_reason_tags(reason_tags: list[str] | None) -> str:
    return "/".join([tag for tag in (reason_tags or []) if tag]) or "无"


def classify_environment(limit_up_count: int) -> str:
    if limit_up_count >= THRESHOLDS["environment"]["strong_limit_up_count"]:
        return "强势日"
    if limit_up_count >= THRESHOLDS["environment"]["disagreement_limit_up_count"]:
        return "分歧日"
    return "退潮日"


def infer_trade_theme(row: dict):
    if row.get("trade_theme"):
        theme = str(row["trade_theme"])
        return theme, merge_theme_lists(
            row.get("stock_theme_tags"),
            row.get("theme_tags"),
            row.get("concept_tags"),
            row.get("cross_theme_tags"),
            [theme] if theme not in {"泛市场", "未知题材"} else [],
        ), {
            "source": "trade_theme",
            "source_label": "显式交易题材",
            "reason": "沿用输入行已有 trade_theme。",
        }

    def _collect_hits(texts: list[str]) -> list[str]:
        lowered = [text.lower() for text in texts if text]
        hits = []
        for theme, keywords in THEME_RULES.items():
            for keyword in keywords:
                if any(keyword.lower() in text for text in lowered):
                    hits.append(theme)
                    break
        return merge_theme_lists(hits)

    name_text = str(row.get("name", ""))
    stock_primary_hits = merge_theme_lists(row.get("stock_theme_tags"))
    if not stock_primary_hits:
        stock_primary_hits = _collect_hits([name_text, *(str(tag) for tag in (row.get("stock_theme_tags") or []))])

    primary_hits = merge_theme_lists(row.get("theme_tags"), row.get("concept_tags"))
    if not primary_hits:
        primary_hits = _collect_hits([name_text, *(str(tag) for tag in (row.get("theme_tags") or [])), *(str(tag) for tag in (row.get("concept_tags") or []))])

    supplemental_hits = merge_theme_lists(row.get("cross_theme_tags"))
    if not supplemental_hits:
        supplemental_hits = _collect_hits([name_text, *(str(tag) for tag in (row.get("sector_tags") or []))])

    if stock_primary_hits:
        return stock_primary_hits[0], merge_theme_lists(stock_primary_hits, primary_hits, supplemental_hits), {
            "source": "stock_theme_tags",
            "source_label": "本地题材库主线",
            "reason": "优先采用本地题材库主线首位 canonical theme。",
        }
    if primary_hits:
        return primary_hits[0], merge_theme_lists(primary_hits, stock_primary_hits, supplemental_hits), {
            "source": "theme_tags",
            "source_label": "QMT题材/概念标签",
            "reason": "本地题材库主线缺失，回退到 QMT 显式题材/概念标签。",
        }
    if supplemental_hits:
        return supplemental_hits[0], supplemental_hits, {
            "source": "cross_theme_tags",
            "source_label": "交叉题材/板块补充",
            "reason": "显式主线缺失，使用交叉题材或板块补充信号。",
        }
    tags = row.get("sector_tags") or []
    if tags:
        raw = str(tags[0])
        if raw in {"上证A股", "深证A股", "沪深A股", "A股"}:
            return "泛市场", [raw], {
                "source": "sector_tags",
                "source_label": "板块兜底",
                "reason": "缺少可用 canonical theme，仅保留泛市场标签兜底。",
            }
        return raw, [raw], {
            "source": "sector_tags",
            "source_label": "板块兜底",
            "reason": "缺少可用 canonical theme，仅保留板块首标签兜底。",
        }
    return "未知题材", [], {
        "source": "unknown",
        "source_label": "未知题材",
        "reason": "缺少可用题材标签。",
    }


def auction_amount(row: dict) -> float:
    bid_px = float(row.get("bid1", 0) or 0)
    ask_px = float(row.get("ask1", 0) or 0)
    bid_amt = bid_px * float(row.get("bid1_vol", 0) or 0)
    ask_amt = ask_px * float(row.get("ask1_vol", 0) or 0)
    return max(bid_amt + ask_amt, 0.0)


def bid_ask_ratio(row: dict) -> float:
    """计算买卖比（买一金额 / 卖一金额）"""
    bid_px = float(row.get("bid1", 0) or 0)
    ask_px = float(row.get("ask1", 0) or 0)
    bid_amt = bid_px * float(row.get("bid1_vol", 0) or 0)
    ask_amt = ask_px * float(row.get("ask1_vol", 0) or 0)
    if ask_amt <= 0:
        return 999.0 if bid_amt > 0 else 1.0
    return round(bid_amt / ask_amt, 2)


def classify_auction_strength(row: dict) -> tuple[str, int]:
    """
    竞价强度分类
    返回：(类型名称, 得分)
    """
    auction_amt = auction_amount(row)
    ba_ratio = bid_ask_ratio(row)
    
    if auction_amt > 50_000_000 and ba_ratio > 3.0:
        return "封单型", 8
    elif auction_amt > 20_000_000 and ba_ratio > 1.5:
        return "活跃型", 5
    elif auction_amt > 5_000_000 and ba_ratio > 1.0:
        return "观望型", 3
    elif ba_ratio < 1.0:
        return "分歧型", -2
    else:
        return "弱势型", 0


def classify_open_position(row: dict) -> tuple[str, int]:
    """
    开盘位置分类
    返回：(区间名称, 得分)
    """
    open_pct = float(row.get("open_pct", 0) or 0)
    
    if 1.0 < open_pct < 3.5:
        return "黄金区", 6
    elif 0.0 < open_pct < 5.0:
        return "可接受", 4
    elif -0.5 < open_pct < 0.0:
        return "观察区", 2
    elif open_pct > 5.5:
        return "高开过高", -3
    elif open_pct < -1.0:
        return "低开过多", -2
    else:
        return "中性", 1


def load_previous_candidate_baseline(payload_path: str | None) -> tuple[dict[str, dict], str | None]:
    if not payload_path:
        return {}, None

    path = Path(payload_path)
    trade_date = path.parent.name
    if len(trade_date) != 8 or not trade_date.isdigit():
        return {}, None

    reports_root = path.parent.parent
    if not reports_root.exists():
        return {}, None

    candidate_paths = sorted(
        (
            day_dir / path.name
            for day_dir in reports_root.iterdir()
            if day_dir.is_dir()
            and day_dir.name.isdigit()
            and day_dir.name < trade_date
            and (day_dir / path.name).exists()
        ),
        key=lambda item: item.parent.name,
        reverse=True,
    )
    if not candidate_paths:
        return {}, None

    previous_path = candidate_paths[0]
    try:
        previous_payload = json.loads(previous_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}, None

    previous_rows = previous_payload.get("strategy_candidate_pool") or previous_payload.get("candidates", [])
    baseline = {
        str(row.get("code") or row.get("ts_code") or "").strip(): row
        for row in previous_rows
        if str(row.get("code") or row.get("ts_code") or "").strip()
    }
    return baseline, previous_path.parent.name


def annotate_relative_activity(row: dict, previous_row: dict | None) -> dict:
    current = dict(row)
    amount = float(current.get("amount", 0) or 0)
    volume = float(current.get("volume", 0) or 0)
    previous_amount = float((previous_row or {}).get("amount", 0) or 0)
    previous_volume = float((previous_row or {}).get("volume", 0) or 0)
    previous_pct = float((previous_row or {}).get("pct", 0) or 0)

    amount_ratio = round(amount / previous_amount, 4) if previous_amount > 0 else None
    volume_ratio = round(volume / previous_volume, 4) if previous_volume > 0 else None
    incremental_amount = round(amount - previous_amount, 2) if previous_row else None
    incremental_volume = round(volume - previous_volume, 2) if previous_row else None

    current["previous_amount"] = previous_amount if previous_row else None
    current["previous_volume"] = previous_volume if previous_row else None
    current["amount_ratio_vs_prev"] = amount_ratio
    current["volume_ratio_vs_prev"] = volume_ratio
    current["incremental_amount"] = incremental_amount
    current["incremental_volume"] = incremental_volume
    current["first_board_like"] = float(current.get("pct", 0) or 0) >= 9.8 and previous_pct < 9.8
    return current


def relative_activity_score(row: dict) -> int:
    thresholds = THRESHOLDS["relative_activity"]
    amount_ratio = row.get("amount_ratio_vs_prev")
    volume_ratio = row.get("volume_ratio_vs_prev")
    incremental_amount = float(row.get("incremental_amount", 0) or 0)

    observed_ratios = [value for value in (amount_ratio, volume_ratio) if value is not None]
    if not observed_ratios and row.get("incremental_amount") is None:
        return 2

    max_ratio = max(observed_ratios, default=0.0)
    if max_ratio >= thresholds["score_a_ratio"] or incremental_amount >= thresholds["score_a_incremental_amount"]:
        return 3
    if max_ratio >= thresholds["score_b_ratio"] or incremental_amount >= thresholds["score_b_incremental_amount"]:
        return 2
    return 1


def has_weak_relative_activity(row: dict, board_count: int | None) -> bool:
    thresholds = THRESHOLDS["relative_activity"]
    amount_ratio = row.get("amount_ratio_vs_prev")
    volume_ratio = row.get("volume_ratio_vs_prev")
    if amount_ratio is None or volume_ratio is None:
        return False
    if board_count == 1 or row.get("first_board_like"):
        return False
    pct = float(row.get("pct", 0) or 0)
    incremental_amount = float(row.get("incremental_amount", 0) or 0)
    return (
        amount_ratio < thresholds["veto_min_amount_ratio"]
        and volume_ratio < thresholds["veto_min_volume_ratio"]
        and pct < thresholds["veto_min_pct"]
        and incremental_amount < thresholds["score_b_incremental_amount"]
    )


def dynamic_cluster_score(row: dict, theme: str, limit_theme_counter: Counter, theme_enrichment: dict | None = None) -> float:
    board_count = int(row.get("board_count", 0) or 0)
    pct = float(row.get("pct", 0) or 0)
    amount = float(row.get("amount", 0) or 0)
    open_pct = float(row.get("open_pct", 0) or 0)
    ratio = float(row.get("bid_ask_ratio", 0) or 0)
    info = (theme_enrichment or {}).get(theme, {})
    score = 0.0
    score += min(amount / 1_000_000_000, 8)
    score += max(board_count, 0) * 2
    score += limit_theme_counter.get(theme, 0) * 3
    score += min(float(info.get("strength_score", 0) or 0) / 3, 6)
    score += min(float(info.get("money_score", 0) or 0) / 4, 4)
    score += min(float(info.get("breadth_score", 0) or 0) / 4, 3)
    if pct >= 9.8:
        score += 3
    elif pct >= 5:
        score += 1.5
    
    # 使用新的竞价强度分类
    auction_strength_name, auction_strength_score = classify_auction_strength(row)
    score += auction_strength_score * 0.5  # 权重调整
    row["auction_strength"] = auction_strength_name
    row["auction_strength_score"] = auction_strength_score
    
    # 使用新的开盘位置分类
    open_position_name, open_position_score = classify_open_position(row)
    score += open_position_score * 0.5  # 权重调整
    row["open_position"] = open_position_name
    row["open_position_score"] = open_position_score
    
    # 相对活跃度评分
    rel_score = relative_activity_score(row)
    if rel_score == 3:
        score += 2.0
    elif rel_score == 2:
        score += 1.0
    return score


def hard_filter(row: dict):
    theme, _, _ = infer_trade_theme(row)
    reasons = []
    amount = float(row.get("amount", 0) or 0)
    open_pct = float(row.get("open_pct", 0) or 0)
    ratio = row.get("bid_ask_ratio")
    thresholds = THRESHOLDS["hard_filter"]
    auction_amt = auction_amount(row)

    if amount < thresholds["min_amount"]:
        reasons.append("成交额不足5亿")
    if auction_amt < thresholds["min_auction_amount"]:
        reasons.append("竞价挂单金额不足10万")
    if open_pct < thresholds["min_open_pct"]:
        reasons.append("低开过深")
    if open_pct > thresholds["max_open_pct"]:
        reasons.append("高开过高")
    if ratio is not None and ratio < thresholds["min_bid_ask_ratio"]:
        reasons.append("竞价承接弱")
    if float(row.get("ask1_vol", 0) or 0) == 0 and float(row.get("pct", 0) or 0) >= 9.8:
        reasons.append("一字顶死")
    if theme in {"泛市场", "未知题材"}:
        reasons.append("交易题材不清晰")
    if row.get("name") in GENERIC_NAMES and theme == "泛市场":
        reasons.append("权重白马非短线主线")
    return len(reasons) == 0, reasons


def compact(row: dict, semantics=None, extras=None):
    payload = {
        "code": row.get("code"),
        "name": row.get("name", ""),
        "pct": row.get("pct", row.get("metrics", {}).get("pct", 0)),
        "amount": row.get("amount", row.get("metrics", {}).get("amount", 0)),
        "board_count": row.get("board_count"),
        "streak": row.get("streak") or "",
        "limit_up_type": row.get("limit_up_type") or "",
        "limit_up_time": row.get("limit_up_time") or "",
    }
    if semantics:
        payload.update({
            "theme": semantics.get("trade_theme"),
            "role": semantics.get("chain_role"),
            "sector_rank": semantics.get("sector_rank"),
        })
    if extras:
        payload.update(extras)
    return payload


def explain_entry_reasons(theme, cluster_score, role, total, yes_count, open_pct, ratio, amount, amount_ratio=None, volume_ratio=None, incremental_amount=None, auction_strength=None, open_position=None):
    reasons = [
        f"题材归类={theme}",
        f"题材簇分={cluster_score:.2f}",
        f"链路角色={role}",
        f"总分={total}",
        f"龙头三问通过={yes_count}/3",
        f"高开={open_pct}%",
        f"承接比={ratio}",
        f"成交额={amount}",
    ]
    if auction_strength:
        reasons.append(f"竞价强度={auction_strength}")
    if open_position:
        reasons.append(f"开盘位置={open_position}")
    if amount_ratio is not None:
        reasons.append(f"成交额相对前日={amount_ratio}")
    if volume_ratio is not None:
        reasons.append(f"量能相对前日={volume_ratio}")
    if incremental_amount is not None:
        reasons.append(f"增量成交额={incremental_amount}")
    return reasons


def explain_no_primary_reason(environment, primary, backup, observe):
    if primary:
        return "存在有效主攻"
    if backup:
        return f"{environment}下存在备选但无唯一主攻"
    if observe:
        return f"{environment}下仅剩观察级机会，未达可执行标准"
    return f"{environment}下无有效交易机会，空仓更优"


def build_stock_theme_context(entry: dict | None) -> dict:
    entry = dict(entry or {})
    if not entry:
        return {}
    return {
        "industry": str(entry.get("industry") or ""),
        "industry_signal_themes": merge_theme_lists(entry.get("industry_signal_themes")),
        "primary_signal_themes": merge_theme_lists(entry.get("primary_signal_themes")),
        "signal_themes": merge_theme_lists(entry.get("signal_themes")),
    }


def summarize_row_risk_reason(row: dict, max_items: int = 2) -> str:
    reasons = []
    for item in (row.get("downgrade_reasons") or []):
        if item and item not in reasons:
            reasons.append(str(item))
    for item in (row.get("vetoes") or []):
        if item and item not in reasons:
            reasons.append(str(item))
    if not reasons and int(row.get("dragon_yes_count", 0) or 0) <= 1:
        reasons.append("龙头三问不足")
    return "、".join(reasons[:max_items]) if reasons else "当前未达可执行标准"


def build_state_action_template(row: dict) -> dict:
    action = str(row.get("final_action") or "回避")
    risk_reason = summarize_row_risk_reason(row)
    reason_tags = classify_reason_tags((row.get("downgrade_reasons") or []) + (row.get("vetoes") or []))
    if int(row.get("dragon_yes_count", 0) or 0) <= 2 and "龙头三问" not in reason_tags:
        reason_tags.append("龙头三问")
    if action == "主攻":
        return {
            "action_label": "主攻",
            "action_reason": "题材地位与执行条件同步满足。",
            "action_plan": "只按主攻节奏跟踪承接，不做追高偏离。",
            "action_reason_tags": [],
        }
    if action == "备选":
        return {
            "action_label": "备选",
            "action_reason": risk_reason if risk_reason != "当前未达可执行标准" else "当前无唯一主攻，需继续确认。",
            "action_plan": "只保留备选，等唯一性和承接进一步确认，不抢先上仓。",
            "action_reason_tags": reason_tags,
        }
    if action == "禁追观察":
        return {
            "action_label": "禁追观察",
            "action_reason": risk_reason,
            "action_plan": "只观察不追高，等回踩承接确认后再评估。",
            "action_reason_tags": reason_tags,
        }
    return {
        "action_label": "回避",
        "action_reason": risk_reason,
        "action_plan": "直接回避，除非承接与题材地位明显修复。",
        "action_reason_tags": reason_tags,
    }


def build_bucket_action_template(row: dict, bucket: str) -> dict:
    risk_reason = summarize_row_risk_reason(row)
    reason_tags = classify_reason_tags((row.get("downgrade_reasons") or []) + (row.get("vetoes") or []))
    if not reason_tags and int(row.get("dragon_yes_count", 0) or 0) <= 1:
        reason_tags = ["龙头三问"]
    if bucket == "low_absorb_watch":
        return {
            "action_label": "低吸观察",
            "action_reason": risk_reason if risk_reason != "当前未达可执行标准" else "当前无唯一主攻，且尚未脱离观察位。",
            "action_plan": "只等回踩承接确认后的低吸，不追高、不抢封。",
            "action_reason_tags": reason_tags,
        }
    if bucket == "do_not_chase":
        reason = "封死不给换手。" if float(row.get("metrics", {}).get("ask1", row.get("ask1", 0)) or 0) == 0 and float(row.get("metrics", {}).get("pct", row.get("pct", 0)) or 0) >= 9.8 else risk_reason
        return {
            "action_label": "禁追",
            "action_reason": reason,
            "action_plan": "禁止追价，等炸板回封或次日弱转强再评估。",
            "action_reason_tags": classify_reason_tags([reason]) or reason_tags,
        }
    return build_state_action_template(row)


def apply_cross_theme_hints(rows: list[dict], code_theme_map: dict[str, list[str]] | None) -> list[dict]:
    enriched = []
    for raw in rows:
        row = dict(raw)
        code = str(row.get("code") or row.get("ts_code") or "").strip()
        stock_theme_entry = get_stock_theme_entry(code)
        stock_themes = get_stock_themes(code)
        cross = merge_theme_lists((code_theme_map or {}).get(code, []), stock_themes)
        if stock_themes:
            row["stock_theme_tags"] = stock_themes
        stock_theme_context = build_stock_theme_context(stock_theme_entry)
        if stock_theme_context:
            row["stock_theme_context"] = stock_theme_context
        if cross:
            row["cross_theme_tags"] = cross
        enriched.append(row)
    return enriched


def build_qmt_realtime_context(raw_candidates: list[dict], limit_up_pool: list[dict], scored: list[dict]) -> dict:
    intraday_count = len(raw_candidates)
    auction_strength_count = sum(
        1 for row in raw_candidates
        if float(row.get("bid_ask_ratio", 0) or 0) >= THRESHOLDS["dragon"]["min_bid_ask_ratio"]
    )
    high_open_count = sum(
        1 for row in raw_candidates
        if float(row.get("open_pct", 0) or 0) > THRESHOLDS["hard_filter"]["max_open_pct"]
    )
    low_open_count = sum(
        1 for row in raw_candidates
        if float(row.get("open_pct", 0) or 0) < 0
    )
    has_board_meta = any(row.get("board_count") not in (None, "") for row in limit_up_pool)
    if has_board_meta:
        first_board_count = sum(1 for row in limit_up_pool if int(row.get("board_count", 0) or 0) == 1)
        multi_board_count = sum(1 for row in limit_up_pool if int(row.get("board_count", 0) or 0) >= 2)
        highest_board = max((int(row.get("board_count", 0) or 0) for row in limit_up_pool), default=0)
    else:
        first_board_count = None
        multi_board_count = None
        highest_board = None

    blowup_count = sum(
        1 for row in raw_candidates
        if str(row.get("limit_up_type", "")).strip() == "炸板"
        or (4 <= float(row.get("pct", 0) or 0) < 9.8 and float(row.get("ask1", 0) or 0) > 0)
    )
    sealed_limit_up_count = sum(
        1 for row in raw_candidates
        if float(row.get("pct", 0) or 0) >= 9.8 and float(row.get("ask1_vol", 0) or 0) == 0
    )
    active_amount_total = sum(float(row.get("amount", 0) or 0) for row in raw_candidates)
    strongest_codes = []
    for item in scored[:5]:
        code = item.get("code")
        if code and code not in strongest_codes:
            strongest_codes.append(code)
    action_counts = Counter(item.get("final_action", "回避") for item in scored)
    role_counts = Counter(item.get("semantics", {}).get("chain_role", "未知") for item in scored)
    actionable_candidate_count = sum(1 for item in scored if item.get("final_action") in {"主攻", "备选", "禁追观察"})
    return {
        "source": "qmt_realtime",
        "candidate_snapshot_count": intraday_count,
        "auction_strength_count": auction_strength_count,
        "auction_strength_ratio": round(auction_strength_count / intraday_count, 4) if intraday_count else 0.0,
        "high_open_count": high_open_count,
        "low_open_count": low_open_count,
        "limit_up_count": len(limit_up_pool),
        "first_board_count": first_board_count,
        "multi_board_count": multi_board_count,
        "highest_board": highest_board,
        "blowup_count": blowup_count,
        "sealed_limit_up_count": sealed_limit_up_count,
        "active_amount_total": round(active_amount_total, 2),
        "strongest_candidate_codes": strongest_codes,
        "action_counts": dict(action_counts),
        "role_counts": dict(role_counts),
        "actionable_candidate_count": actionable_candidate_count,
    }


def build_intraday_dynamics(scored: list[dict], primary: list[dict], backup: list[dict], observe: list[dict], avoid: list[dict]) -> dict:
    order = {"主攻": 0, "备选": 1, "禁追观察": 2, "回避": 3}
    sorted_scored = sorted(
        scored,
        key=lambda x: (
            order.get(x.get("final_action", "回避"), 9),
            -float(x.get("total_score", 0) or 0),
            -float(x.get("cluster_score", 0) or 0),
        ),
    )
    leaders = [item.get("code") for item in sorted_scored[:3] if item.get("code")]
    upgrade_watch = [
        compact(item, item.get("semantics"), {"action": item.get("final_action")})
        for item in sorted_scored
        if item.get("final_action") == "备选" and item.get("dragon_yes_count", 0) >= 2
    ][:3]
    downgrade_watch = [
        compact(item, item.get("semantics"), {"action": item.get("final_action")})
        for item in sorted_scored
        if item.get("downgrade_reasons")
    ][:3]
    return {
        "leader_codes": leaders,
        "primary_count": len(primary),
        "backup_count": len(backup),
        "observe_count": len(observe),
        "avoid_count": len(avoid),
        "upgrade_watch": upgrade_watch,
        "downgrade_watch": downgrade_watch,
    }


def build_qmt_timeline_score(intraday_dynamics: dict, qmt_realtime_context: dict) -> dict:
    actionable_count = int(qmt_realtime_context.get("actionable_candidate_count", 0) or 0)
    focus_count = len(intraday_dynamics.get("leader_codes") or [])
    downgrade_count = len(intraday_dynamics.get("downgrade_watch") or [])
    upgrade_count = len(intraday_dynamics.get("upgrade_watch") or [])
    stability_bonus = 2 if focus_count == 1 else 1 if focus_count <= 2 else 0
    actionable_bonus = 2 if actionable_count >= 2 else 1 if actionable_count == 1 else 0
    downgrade_penalty = min(downgrade_count, 2)
    score = max(0, stability_bonus + actionable_bonus + min(upgrade_count, 2) - downgrade_penalty)
    return {
        "focus_count": focus_count,
        "upgrade_count": upgrade_count,
        "downgrade_count": downgrade_count,
        "score": score,
    }


def normalize_payload(payload: dict, top_n: int = 12, payload_path: str | None = None) -> dict:
    if payload.get("strategy_result"):
        result = payload["strategy_result"]
        if top_n != 12:
            result = dict(result)
            result["top_ranked"] = result.get("strategy_candidate_pool", [])[:top_n]
        return result

    raw_candidates = payload.get("strategy_candidate_pool") or payload.get("candidates", [])
    limit_up_pool = payload.get("limit_up_pool", [])
    trade_date = str(payload.get("trade_date") or payload.get("date") or "").replace('-', '')
    if not trade_date and payload_path:
        parts = Path(payload_path).parts
        for part in parts:
            if len(part) == 8 and part.isdigit():
                trade_date = part
                break
    environment = classify_environment(payload.get("limit_up_count", len(limit_up_pool)))
    previous_baseline, previous_trade_date = load_previous_candidate_baseline(payload_path)
    tushare_theme = fetch_tushare_theme_enrichment(trade_date) if trade_date else {"success": False, "reason": "missing_trade_date"}
    code_theme_map = tushare_theme.get("code_theme_map") or {}
    raw_candidates = apply_cross_theme_hints(raw_candidates, code_theme_map)
    limit_up_pool = apply_cross_theme_hints(limit_up_pool, code_theme_map)
    enriched_payload = dict(payload)
    enriched_payload["candidates"] = raw_candidates
    enriched_payload["strategy_candidate_pool"] = raw_candidates
    enriched_payload["limit_up_pool"] = limit_up_pool
    theme_enrichment, enrichment_meta = merge_theme_enrichment(enriched_payload, payload_path)
    enrichment_summary = summarize_theme_enrichment(theme_enrichment)

    limit_theme_counter = Counter()
    for row in limit_up_pool:
        theme, _, _ = infer_trade_theme(row)
        limit_theme_counter[theme] += 1

    filtered = []
    rejected = []
    for row in raw_candidates:
        row = annotate_relative_activity(
            row,
            previous_baseline.get(str(row.get("code") or row.get("ts_code") or "").strip()),
        )
        theme, theme_hits, theme_selection = infer_trade_theme(row)
        row["trade_theme"] = theme
        row["trade_theme_selection"] = theme_selection
        row["theme_hits"] = theme_hits
        row["theme_tags"] = merge_theme_lists(row.get("cross_theme_tags"), row.get("theme_tags"), [theme] if theme not in {"泛市场", "未知题材"} else [])
        row["concept_tags"] = merge_theme_lists(row.get("cross_theme_tags"), row.get("concept_tags"))
        row["auction_amount"] = auction_amount(row)
        row["cluster_score"] = dynamic_cluster_score(row, theme, limit_theme_counter, theme_enrichment)
        row["theme_enrichment"] = theme_enrichment.get(theme, {})
        passed, reasons = hard_filter(row)
        if passed:
            filtered.append(row)
        else:
            rejected.append({
                "code": row["code"],
                "name": row["name"],
                "trade_theme": theme,
                "reject_reasons": reasons,
            })

    theme_groups = defaultdict(list)
    trade_theme_counter = Counter()
    sector_counter = Counter()
    cluster_strength_counter = Counter()
    for row in filtered:
        theme_groups[row["trade_theme"]].append(row)
        trade_theme_counter[row["trade_theme"]] += float(row.get("amount", 0) or 0)
        cluster_strength_counter[row["trade_theme"]] += float(row.get("cluster_score", 0) or 0)
        for tag in row.get("sector_tags") or []:
            sector_counter[tag] += float(row.get("amount", 0) or 0)

    top_themes = [name for name, _ in cluster_strength_counter.most_common(3)]

    scored = []
    sc = THRESHOLDS["scoring"]
    dg = THRESHOLDS["dragon"]
    for theme, members in theme_groups.items():
        members.sort(key=lambda x: (float(x.get("cluster_score", 0) or 0), int(x.get("board_count", 0) or 0), float(x.get("amount", 0) or 0), float(x.get("auction_amount", 0) or 0), float(x.get("open_pct", 0) or 0)), reverse=True)
        for idx, row in enumerate(members, start=1):
            role = "非核心"
            if idx == 1 and theme in top_themes[:1]:
                role = "主线龙头候选"
            elif idx <= 2 and theme in top_themes:
                role = "主线前排"
            elif idx <= 4:
                role = "跟风前排"

            amount = float(row.get("amount", 0) or 0)
            open_pct = float(row.get("open_pct", 0) or 0)
            ratio = float(row.get("bid_ask_ratio", 0) or 0)
            board_count_raw = row.get("board_count")
            board_count = int(board_count_raw or 0) if board_count_raw not in (None, "") else None
            cluster_score = float(row.get("cluster_score", 0) or 0)
            amount_score = 3 if amount >= sc["amount_a"] else 2 if amount >= sc["amount_b"] else 1
            open_score = 3 if sc["open_a_low"] <= open_pct <= sc["open_a_high"] else 2 if sc["open_b_low"] <= open_pct < sc["open_a_low"] or sc["open_a_high"] < open_pct <= sc["open_b_high"] else 1
            bidask_score = 3 if ratio >= sc["bidask_a"] else 2 if ratio >= sc["bidask_b"] else 1
            relative_score = relative_activity_score(row)
            rank_score = 3 if idx == 1 else 2 if idx <= 2 else 1
            board_score = 2 if board_count is None else 3 if board_count >= 2 else 2 if board_count == 1 else 1
            theme_score = 3 if theme in top_themes[:1] else 2 if theme in top_themes else 1
            premium_score = 3 if role == "主线龙头候选" and open_pct <= dg["max_premium_open_pct"] else 2 if role in {"主线龙头候选", "主线前排"} else 1
            cluster_bonus = 3 if cluster_score >= 12 else 2 if cluster_score >= 6 else 1
            theme_info = theme_enrichment.get(theme, {})
            strength_score = float(theme_info.get("strength_score", 0) or 0)
            money_score = float(theme_info.get("money_score", 0) or 0)
            breadth_score = float(theme_info.get("breadth_score", 0) or 0)
            total = amount_score + open_score + bidask_score + relative_score + rank_score + board_score + theme_score + premium_score + cluster_bonus
            if strength_score >= 12:
                total += 2
            elif strength_score >= 8:
                total += 1
            if money_score >= 10:
                total += 1

            vetoes = []
            downgrade_reasons = []
            if role == "非核心":
                vetoes.append("题材链路非核心")
            if theme in {"泛市场", "未知题材"}:
                vetoes.append("交易题材不清晰")
            if open_pct > sc["open_b_high"]:
                vetoes.append("高开过热")
            if ratio < 1.0:
                vetoes.append("承接不足")
            if has_weak_relative_activity(row, board_count):
                vetoes.append("相对量能不足")
            if float(row.get("ask1_vol", 0) or 0) == 0 and float(row.get("pct", 0) or 0) >= 9.8:
                vetoes.append("封死不给换手")

            dragon_questions = {
                "辨识度": idx == 1 or (idx == 2 and role == "主线前排"),
                "同身位资金偏好": amount >= dg["min_amount"] and float(row.get("auction_amount", 0) or 0) >= dg["min_auction_amount"] and ratio >= dg["min_bid_ask_ratio"] and not has_weak_relative_activity(row, board_count),
                "次日溢价优先给它": role == "主线龙头候选" and theme in top_themes[:1] and open_pct <= dg["max_premium_open_pct"],
            }
            yes_count = sum(1 for v in dragon_questions.values() if v)

            final_action = "回避"
            if environment == "强势日":
                if total >= 20 and yes_count >= 3 and role == "主线龙头候选" and not vetoes:
                    final_action = "主攻"
                elif total >= 17 and yes_count >= 2 and role in {"主线龙头候选", "主线前排"}:
                    final_action = "备选"
                elif total >= 14:
                    final_action = "禁追观察"
            elif environment == "分歧日":
                if total >= 21 and yes_count >= 3 and role == "主线龙头候选" and not vetoes and (board_count is None or board_count >= 1) and open_pct >= 0:
                    final_action = "主攻"
                elif total >= 18 and yes_count >= 2 and role in {"主线龙头候选", "主线前排"} and len(vetoes) <= 1 and open_pct >= -0.5:
                    final_action = "备选"
                elif total >= 15:
                    final_action = "禁追观察"
            else:
                if total >= 22 and yes_count >= 3 and role == "主线龙头候选" and not vetoes and (board_count is None or board_count >= 2):
                    final_action = "主攻"
                elif total >= 19 and yes_count >= 2 and role == "主线龙头候选" and len(vetoes) <= 1:
                    final_action = "备选"
                elif total >= 15:
                    final_action = "禁追观察"

            if len(vetoes) >= 2 or yes_count <= 1:
                final_action = "回避"
            if yes_count <= 1:
                downgrade_reasons.append("龙头三问不足")
            if len(vetoes) >= 2:
                downgrade_reasons.append("否决项过多")
            if environment == "分歧日" and open_pct < 0 and final_action in {"备选", "主攻", "禁追观察"}:
                downgrade_reasons.append("分歧日低开，仅保留观察")
            if environment == "分歧日" and open_pct < 0 and final_action in {"备选", "主攻"}:
                final_action = "禁追观察"
            if environment == "分歧日" and open_pct < 0 and final_action == "禁追观察":
                downgrade_reasons.append("未达分歧日可执行开盘要求")

            semantics = {
                "primary_sector": (row.get("sector_tags") or [theme])[0],
                "sector_rank": idx,
                "sector_member_count": len(members),
                "chain_role": role,
                "is_main_sector": theme in top_themes,
                "trade_theme": theme,
                "theme_hits": row.get("theme_hits", []),
                "theme_source": row.get("trade_theme_selection", {}).get("source", ""),
                "theme_source_label": row.get("trade_theme_selection", {}).get("source_label", ""),
                "trade_theme_reason": row.get("trade_theme_selection", {}).get("reason", ""),
                "is_main_theme": theme in top_themes,
            }

            action_template = build_state_action_template({
                "final_action": final_action,
                "vetoes": vetoes,
                "downgrade_reasons": downgrade_reasons + [f"开盘位置={open_pct:.2f}%"],
                "dragon_yes_count": yes_count,
            })
            scored.append({
                "code": row["code"],
                "name": row.get("name", ""),
                "total_score": total,
                "cluster_score": cluster_score,
                "auction_snapshot": {
                    "auction_amount": row.get("auction_amount", 0),
                    "bid_ask_ratio": ratio,
                    "open_pct": open_pct,
                },
                "metrics": {
                    "open_pct": open_pct,
                    "pct": float(row.get("pct", 0) or 0),
                    "amount": amount,
                    "volume": float(row.get("volume", 0) or 0),
                    "previous_amount": row.get("previous_amount"),
                    "previous_volume": row.get("previous_volume"),
                    "amount_ratio_vs_prev": row.get("amount_ratio_vs_prev"),
                    "volume_ratio_vs_prev": row.get("volume_ratio_vs_prev"),
                    "incremental_amount": row.get("incremental_amount"),
                    "incremental_volume": row.get("incremental_volume"),
                    "bid_ask_ratio": ratio,
                    "bid1": float(row.get("bid1", 0) or 0),
                    "ask1": float(row.get("ask1", 0) or 0),
                    "bid1_vol": float(row.get("bid1_vol", 0) or 0),
                    "ask1_vol": float(row.get("ask1_vol", 0) or 0),
                    "first_board_like": bool(row.get("first_board_like")),
                },
                "grades": {
                    "amount": amount_score,
                    "open": open_score,
                    "bidask": bidask_score,
                    "relative_activity": relative_score,
                    "theme_rank": rank_score,
                    "board": board_score,
                    "theme": theme_score,
                    "premium": premium_score,
                    "cluster": cluster_bonus,
                    "theme_strength": round(strength_score, 2),
                    "theme_money": round(money_score, 2),
                    "theme_breadth": round(breadth_score, 2),
                },
                "theme": theme,
                "theme_rank": idx,
                "rank_idx": idx,
                "dragon_yes_count": yes_count,
                "dragon_questions": dragon_questions,
                "vetoes": vetoes,
                "entry_reasons": explain_entry_reasons(
                    theme,
                    cluster_score,
                    role,
                    total,
                    yes_count,
                    open_pct,
                    ratio,
                    amount,
                    row.get("amount_ratio_vs_prev"),
                    row.get("volume_ratio_vs_prev"),
                    row.get("incremental_amount"),
                    row.get("auction_strength"),
                    row.get("open_position"),
                ),
                "downgrade_reasons": downgrade_reasons,
                "final_action": final_action,
                "sector_tags": row.get("sector_tags", []),
                "stock_theme_tags": row.get("stock_theme_tags", []),
                "stock_theme_context": row.get("stock_theme_context", {}),
                "action_label": action_template["action_label"],
                "action_reason": action_template["action_reason"],
                "action_plan": action_template["action_plan"],
                "action_reason_tags": action_template["action_reason_tags"],
                "semantics": semantics,
                "theme_enrichment": theme_info,
                "board_count": board_count_raw if board_count_raw not in (None, "") else None,
                "streak": row.get("streak") or "",
                "limit_up_type": row.get("limit_up_type") or "",
                "limit_up_time": row.get("limit_up_time") or "",
                "pct": float(row.get("pct", 0) or 0),
                "amount": amount,
            })

    reason_tag_codes = defaultdict(set)
    for item in scored:
        tags = item.get("action_reason_tags") or []
        if "开盘" in tags and "龙头三问" in tags:
            if int(item.get("dragon_yes_count", 0) or 0) <= 1:
                tags_for_counts = ["龙头三问"]
            else:
                tags_for_counts = ["开盘"]
        else:
            tags_for_counts = tags
        code = item.get("code") or item.get("ts_code") or item.get("name") or str(id(item))
        for tag in tags_for_counts:
            reason_tag_codes[tag].add(code)

    order = {"主攻": 0, "备选": 1, "禁追观察": 2, "回避": 3}
    scored.sort(key=lambda x: (order.get(x["final_action"], 9), -x["cluster_score"], -x["total_score"], -x["dragon_yes_count"], x["theme_rank"], -x["amount"]))
    primary = [x for x in scored if x["final_action"] == "主攻"][:1]
    backup = [x for x in scored if x["final_action"] == "备选"][:3]
    observe = [x for x in scored if x["final_action"] == "禁追观察"][:5]
    avoid = [x for x in scored if x["final_action"] == "回避"][:5]

    qmt_realtime_context = build_qmt_realtime_context(raw_candidates, limit_up_pool, scored)
    intraday_dynamics = build_intraday_dynamics(scored, primary, backup, observe, avoid)
    qmt_timeline_score = build_qmt_timeline_score(intraday_dynamics, qmt_realtime_context)
    theme_library_summary = summarize_theme_library([
        *(row.get("code") or row.get("ts_code") for row in raw_candidates),
        *(row.get("code") or row.get("ts_code") for row in limit_up_pool),
    ])

    market_map = {
        "environment_summary": f"{environment}，硬筛后候选{len(filtered)}只，涨停池{len(limit_up_pool)}只",
        "qmt_realtime": qmt_realtime_context,
        "intraday_dynamics": intraday_dynamics,
        "qmt_timeline_score": qmt_timeline_score,
        "top_trade_themes": trade_theme_counter.most_common(5),
        "top_sectors": trade_theme_counter.most_common(5),
        "top_limit_up_themes": limit_theme_counter.most_common(5),
        "candidate_pool_theme_heat": trade_theme_counter.most_common(5),
        "theme_cluster_heat": cluster_strength_counter.most_common(5),
        "reason_tag_counts": [(tag, len(reason_tag_codes[tag])) for tag in REASON_TAG_ORDER if reason_tag_codes[tag]],
        "theme_strength": enrichment_summary["theme_strength"],
        "theme_money": enrichment_summary["theme_money"],
        "theme_breadth": enrichment_summary["theme_breadth"],
        "theme_enrichment_meta": enrichment_meta,
        "tushare_theme": tushare_theme,
        "canonical_hot_themes": tushare_theme.get("canonical_hot_theme_rank") or [],
        "stock_theme_library": theme_library_summary,
    }

    profiles = []
    for theme, members in sorted(theme_groups.items(), key=lambda kv: cluster_strength_counter.get(kv[0], 0), reverse=True)[:8]:
        theme_scored = [x for x in scored if x["theme"] == theme]
        blowups = [x for x in theme_scored if x.get("limit_up_type") == "炸板" or (x.get("pct", 0) < 9.8 and x.get("pct", 0) >= 4)][:3]
        leader = theme_scored[0] if theme_scored else {"code": "", "name": ""}
        profile_has_board_meta = any(x.get("board_count") not in (None, "") for x in theme_scored)
        profiles.append({
            "theme": theme,
            "member_count": len(theme_scored),
            "limit_up_count": limit_theme_counter.get(theme, 0),
            "highest_board": max((int(x.get("board_count", 0) or 0) for x in theme_scored), default=0) if profile_has_board_meta else None,
            "leader_code": leader.get("code", ""),
            "leader_name": leader.get("name", ""),
            "strength_score": round(float(theme_enrichment.get(theme, {}).get("strength_score", 0) or 0), 2),
            "money_score": round(float(theme_enrichment.get(theme, {}).get("money_score", 0) or 0), 2),
            "breadth_score": round(float(theme_enrichment.get(theme, {}).get("breadth_score", 0) or 0), 2),
            "front_rows": [compact(x, x.get("semantics")) for x in theme_scored[:3]],
            "blowups": [compact(x, x.get("semantics")) for x in blowups],
            "strength": "主升" if limit_theme_counter.get(theme, 0) >= 3 else "分歧" if blowups else "轮动",
        })

    actionable_buckets = {
        "best_in_market": [compact(x, x.get("semantics"), {"action": x.get("final_action"), **build_state_action_template(x)}) for x in scored[:5]],
        "actionable_primary": [compact(x, x.get("semantics"), {"action": x.get("final_action"), **build_state_action_template(x)}) for x in primary if x.get("pct", 0) < 9.8],
        "low_absorb_watch": [compact(x, x.get("semantics"), {"action": x.get("final_action"), **build_bucket_action_template(x, "low_absorb_watch")}) for x in backup + observe if x.get("pct", 0) < 5][:5],
        "rebound_sell_watch": [],
        "do_not_chase": [compact(x, x.get("semantics"), {"action": x.get("final_action"), **build_bucket_action_template(x, "do_not_chase")}) for x in scored if x.get("metrics", {}).get("ask1", 0) == 0 and x.get("pct", 0) >= 9.8][:8],
    }

    ifind_board_context = build_ifind_board_context(scored[:20])
    for item in scored:
        code = item.get("code")
        confirm = (ifind_board_context.get("by_code") or {}).get(code, {})
        item.setdefault("ifind_confirmation", confirm)
        item.setdefault("semantics", {})["ifind_industry_name"] = confirm.get("industry_name", "")
        item.setdefault("semantics", {})["ifind_theme_match"] = confirm.get("theme_match", False)
        item.setdefault("semantics", {})["ifind_is_sse_scope"] = confirm.get("is_sse_scope", False)
        item.setdefault("grades", {})["board_alignment"] = confirm.get("board_alignment_score", 0)

    if ifind_board_context.get("theme_leaderboard"):
        for profile in profiles:
            leaderboard = (ifind_board_context.get("theme_leaderboard") or {}).get(profile.get("theme"), [])
            if leaderboard:
                profile["ifind_leaderboard"] = leaderboard[:5]

    no_primary_reason = explain_no_primary_reason(environment, primary, backup, observe)
    intraday_strongest = scored[:1]
    theme_leaders = [theme_scored[0] for theme_scored in ([x for x in scored if x["theme"] == theme] for theme, _ in cluster_strength_counter.most_common(5)) if theme_scored]
    thematic_strongest = theme_leaders[:1]
    actionable_strongest = primary[:1] or backup[:1] or observe[:1]

    return {
        "environment": environment,
        "candidate_count": len(filtered),
        "limit_up_count": payload.get("limit_up_count", len(limit_up_pool)),
        "top_sectors_by_amount": trade_theme_counter.most_common(5),
        "top_trade_themes_by_amount": trade_theme_counter.most_common(5),
        "intraday_strongest": intraday_strongest,
        "thematic_strongest": thematic_strongest,
        "actionable_strongest": actionable_strongest,
        "market_map": market_map,
        "qmt_realtime_context": qmt_realtime_context,
        "intraday_dynamics": intraday_dynamics,
        "qmt_timeline_score": qmt_timeline_score,
        "ifind_board_context": ifind_board_context,
        "sector_profiles": profiles,
        "actionable_buckets": actionable_buckets,
        "primary": primary,
        "backup": backup,
        "observe": observe,
        "avoid": avoid,
        "top_ranked": scored[:top_n],
        "strategy_candidate_pool": scored,
        "rejected_count": len(rejected),
        "rejected_samples": rejected[:50],
        "thresholds": THRESHOLDS,
        "no_primary_reason": no_primary_reason,
    }


def score_payload(payload: dict, top_n: int = 12, payload_path: str | None = None) -> dict:
    return normalize_payload(payload, top_n=top_n, payload_path=payload_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_path", help="Path to auction_candidates_main_board_non_st.json")
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()

    path = Path(args.json_path)
    payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    result = normalize_payload(payload, top_n=args.top, payload_path=str(path))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
