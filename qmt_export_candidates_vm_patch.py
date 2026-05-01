#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QMT auction candidates exporter + strategy-native candidate pool builder.

Pipeline:
1. 主板非ST全量
2. 竞价硬筛
3. 题材归类
4. 龙头优先
5. 次日溢价导向排序
6. 输出真正候选池 + 原始样本池
"""

import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

BASE_URL = "http://127.0.0.1:8000"
API_KEY = "***"
OUT_DIR = Path(r"C:\Users\mac\Desktop\qmt_runtime\exports")

MAIN_BOARD_PREFIXES = (
    "600", "601", "603", "605",
    "000", "001", "002",
)
EXCLUDE_PREFIXES = (
    "300", "301", "688", "689", "8", "4",
)
PREFERRED_SECTORS = ("沪深A股", "上证A股", "深证A股")
THEME_RULES = {
    "AI算力": ["寒武纪", "海光", "中际", "新易盛", "天孚", "工业富联", "浪潮信息", "中科曙光", "算力", "cpo", "光模块", "液冷", "服务器", "aigc", "人工智能", "数据中心", "东数西算", "gpu"],
    "铜缆高速连接": ["中天科技", "沃尔核材", "神宇", "华丰科技", "胜蓝", "铜缆", "高速连接", "连接器", "线缆", "高速线", "dac"],
    "半导体": ["生益科技", "沪电股份", "深南电路", "胜宏科技", "寒武纪", "半导体", "芯片", "存储", "封测", "晶圆", "光刻", "eda", "第三代半导体", "pcb", "fpc"],
    "消费电子": ["环旭电子", "立讯精密", "歌尔股份", "鹏鼎控股", "消费电子", "苹果", "ai手机", "折叠屏", "mr", "vr"],
    "机器人": ["埃斯顿", "绿的谐波", "机器人", "人形", "减速器", "机器视觉", "自动化", "工业母机"],
    "固态电池": ["天齐锂业", "赣锋锂业", "宁德时代", "固态电池", "锂电", "电池", "储能", "钠电", "磷酸铁锂"],
    "新能源汽车": ["比亚迪", "赛力斯", "拓普集团", "新能源车", "汽车零部件", "整车", "智能驾驶", "无人驾驶", "汽配"],
    "医药": ["药明康德", "恒瑞医药", "百济神州", "片仔癀", "医药", "创新药", "中药", "医疗器械", "减肥药", "cro", "cxo"],
    "军工": ["中航成飞", "中国卫星", "中无人机", "军工", "卫星", "商业航天", "航天", "低空", "无人机"],
    "有色资源": ["华友钴业", "包钢股份", "洛阳钼业", "北方稀土", "江西铜业", "南山铝业", "盛和资源", "西部矿业", "中金黄金", "有色", "稀土", "钴", "锂", "小金属", "黄金", "铜", "铝"],
}


def api_get(path: str, **params: Any) -> dict:
    params["key"] = API_KEY
    resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def is_main_board(code: str, name: str) -> bool:
    pure = code.split(".")[0]
    if any(pure.startswith(p) for p in EXCLUDE_PREFIXES):
        return False
    if not any(pure.startswith(p) for p in MAIN_BOARD_PREFIXES):
        return False
    upper_name = (name or "").upper()
    if "ST" in upper_name or "*ST" in upper_name:
        return False
    return True


def pick_sector_names() -> list[str]:
    payload = api_get("/sector/list")
    sectors = payload.get("sectors", [])
    preferred = [s for s in sectors if s in PREFERRED_SECTORS]
    return preferred or sectors[:3]


def build_sector_rank_map(sector_names: list[str]) -> dict[str, list[str]]:
    rank_map: dict[str, list[str]] = {}
    for sector in sector_names:
        payload = api_get("/sector", sector=sector)
        stocks = payload.get("stocks", [])
        for item in stocks:
            code = item.get("code", "")
            if not code:
                continue
            rank_map.setdefault(code, []).append(sector)
    return rank_map


def infer_trade_theme(name: str, sector_tags: list[str]) -> tuple[list[str], list[str]]:
    texts = [str(name or "")] + [str(tag) for tag in sector_tags]
    lowered = [text.lower() for text in texts if text]
    hits: list[str] = []
    for theme, keywords in THEME_RULES.items():
        for keyword in keywords:
            key = keyword.lower()
            if any(key in text for text in lowered):
                hits.append(theme)
                break
    unique_hits = list(dict.fromkeys(hits))
    if unique_hits:
        return unique_hits, unique_hits[:3]
    return [], []


def infer_limit_up_type(item: dict, quote: dict) -> str:
    ask1 = quote.get("ask1", item.get("ask1", 0))
    pct = float(quote.get("pct", item.get("pct", 0)) or 0)
    open_price = float(quote.get("open", item.get("open", 0)) or 0)
    high = float(quote.get("high", item.get("high", 0)) or 0)
    low = float(quote.get("low", item.get("low", 0)) or 0)
    if ask1 == 0 and pct >= 9.8:
        if open_price == high == low and high > 0:
            return "一字板"
        return "换手涨停"
    if pct >= 4:
        return "炸板"
    return "趋势票"


def infer_limit_up_time(item: dict) -> str:
    for key in ("first_limit_time", "limit_up_time", "time"):
        value = item.get(key)
        if value:
            return str(value)
    return ""


def infer_board_count(item: dict) -> int:
    for key in ("board_count", "连板数", "板数", "open_count"):
        value = item.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return 1 if float(item.get("pct", 0) or 0) >= 9.8 else 0


def infer_streak(item: dict, board_count: int) -> str:
    for key in ("streak", "几天几板"):
        value = item.get(key)
        if value:
            return str(value)
    if board_count > 0:
        return f"{board_count}天{board_count}板"
    return "0天0板"


def build_candidate_row(item: dict, quote: dict, sector_map: dict[str, list[str]]) -> dict:
    code = item["code"]
    sector_tags = sector_map.get(code, [])
    theme_tags, concept_tags = infer_trade_theme(item.get("name", ""), sector_tags)
    preclose = float(quote.get("preclose", 0) or 0)
    open_price = float(quote.get("open", 0) or 0)
    open_pct = round((open_price / preclose - 1) * 100, 2) if preclose else 0
    bid1_vol = int(quote.get("bid1_vol", 0) or 0)
    ask1_vol = int(quote.get("ask1_vol", 0) or 0)
    bid1 = float(quote.get("bid1", 0) or 0)
    ask1 = float(quote.get("ask1", 0) or 0)
    bid_ask_ratio = round(bid1_vol / ask1_vol, 4) if ask1_vol else None
    amount = float(quote.get("amount", 0) or 0)
    volume = float(quote.get("volume", 0) or 0)
    board_count = infer_board_count(item)
    return {
        "code": code,
        "name": item.get("name", ""),
        "board": "main",
        "is_st": False,
        "sector_tags": sector_tags,
        "theme_tags": theme_tags,
        "concept_tags": concept_tags,
        "price": float(quote.get("price", 0) or 0),
        "preclose": preclose,
        "open": open_price,
        "high": float(quote.get("high", item.get("high", 0)) or 0),
        "low": float(quote.get("low", item.get("low", 0)) or 0),
        "open_pct": open_pct,
        "pct": float(quote.get("pct", 0) or 0),
        "amount": amount,
        "volume": volume,
        "stock_status": quote.get("stockStatus", item.get("stockStatus", 0)),
        "bid1": bid1,
        "ask1": ask1,
        "bid1_vol": bid1_vol,
        "ask1_vol": ask1_vol,
        "bid_ask_ratio": bid_ask_ratio,
        "limit_up_time": infer_limit_up_time(item),
        "limit_up_type": infer_limit_up_type(item, quote),
        "board_count": board_count,
        "streak": infer_streak(item, board_count),
    }


def auction_amount(row: dict) -> float:
    bid_px = float(row.get("bid1", 0) or 0)
    ask_px = float(row.get("ask1", 0) or 0)
    bid_amt = bid_px * float(row.get("bid1_vol", 0) or 0)
    ask_amt = ask_px * float(row.get("ask1_vol", 0) or 0)
    return max(bid_amt + ask_amt, 0.0)


def normalize_theme(row: dict) -> str:
    tags = row.get("theme_tags") or row.get("concept_tags") or []
    if tags:
        return str(tags[0])
    sector_tags = row.get("sector_tags") or []
    if sector_tags:
        raw = str(sector_tags[0])
        if raw in {"上证A股", "深证A股", "沪深A股", "A股"}:
            return "泛市场"
        return raw
    return "未知题材"


def passes_auction_hard_filter(row: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    amount = float(row.get("amount", 0) or 0)
    open_pct = float(row.get("open_pct", 0) or 0)
    ratio = row.get("bid_ask_ratio")
    ask1_vol = float(row.get("ask1_vol", 0) or 0)
    bid1_vol = float(row.get("bid1_vol", 0) or 0)
    auction_amt = auction_amount(row)
    theme = normalize_theme(row)

    if amount < 500_000_000:
        reasons.append("成交额不足5亿")
    if auction_amt < 100_000:
        reasons.append("竞价挂单金额不足10万")
    if open_pct < -1.5:
        reasons.append("低开过深")
    if open_pct > 6.5:
        reasons.append("高开过高")
    if ratio is not None and ratio < 0.8:
        reasons.append("竞价承接弱")
    if ask1_vol == 0 and float(row.get("pct", 0) or 0) >= 9.8:
        reasons.append("一字顶死")
    if bid1_vol <= 0:
        reasons.append("买一挂单为空")
    if theme in {"泛市场", "未知题材"}:
        reasons.append("交易题材不清晰")
    return len(reasons) == 0, reasons


def classify_environment(limit_up_count: int) -> str:
    if limit_up_count >= 60:
        return "强势日"
    if limit_up_count >= 25:
        return "分歧日"
    return "退潮日"


def build_theme_context(rows: list[dict]) -> tuple[dict, dict, Counter]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    theme_turnover: Counter = Counter()
    for row in rows:
        theme = normalize_theme(row)
        row["trade_theme"] = theme
        grouped[theme].append(row)
        theme_turnover[theme] += float(row.get("amount", 0) or 0)

    theme_meta: dict[str, dict] = {}
    rank_by_code: dict[str, int] = {}
    for theme, members in grouped.items():
        sorted_members = sorted(
            members,
            key=lambda r: (
                int(r.get("board_count", 0) or 0),
                float(r.get("amount", 0) or 0),
                auction_amount(r),
                float(r.get("open_pct", 0) or 0),
                float(r.get("pct", 0) or 0),
            ),
            reverse=True,
        )
        leader = sorted_members[0] if sorted_members else None
        highest_board = max((int(x.get("board_count", 0) or 0) for x in sorted_members), default=0)
        meta = {
            "theme": theme,
            "members": sorted_members,
            "leader_code": leader.get("code") if leader else "",
            "leader_name": leader.get("name") if leader else "",
            "highest_board": highest_board,
            "member_count": len(sorted_members),
            "amount": float(theme_turnover[theme]),
        }
        theme_meta[theme] = meta
        for idx, item in enumerate(sorted_members, start=1):
            rank_by_code[item["code"]] = idx
    return theme_meta, rank_by_code, theme_turnover


def build_limit_up_context(limit_up_pool: list[dict]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in limit_up_pool:
        theme = normalize_theme(row)
        grouped[theme].append(row)
    stats: dict[str, dict] = {}
    for theme, members in grouped.items():
        stats[theme] = {
            "limit_up_count": len(members),
            "highest_board": max((int(x.get("board_count", 0) or 0) for x in members), default=0),
        }
    return stats


def theme_strength(limit_up_stats: dict, theme: str, theme_turnover: Counter) -> float:
    info = limit_up_stats.get(theme, {})
    return (
        info.get("limit_up_count", 0) * 3
        + info.get("highest_board", 0) * 2
        + (theme_turnover.get(theme, 0) / 1_000_000_000)
    )


def score_strategy_candidates(strategy_rows: list[dict], limit_up_pool: list[dict], environment: str) -> dict:
    theme_meta, rank_by_code, theme_turnover = build_theme_context(strategy_rows)
    limit_up_stats = build_limit_up_context(limit_up_pool)
    theme_scores = {
        theme: theme_strength(limit_up_stats, theme, theme_turnover)
        for theme in theme_meta
    }
    ranked_themes = sorted(theme_scores.items(), key=lambda kv: kv[1], reverse=True)
    top_themes = [name for name, _ in ranked_themes[:3]]

    scored = []
    for row in strategy_rows:
        code = row["code"]
        theme = row["trade_theme"]
        theme_rank = rank_by_code.get(code, 99)
        row["theme_rank"] = theme_rank
        role = "非核心"
        if theme_rank == 1 and theme in top_themes[:1]:
            role = "主线龙头候选"
        elif theme_rank <= 2 and theme in top_themes:
            role = "主线前排"
        elif theme_rank <= 4:
            role = "跟风前排"
        row["chain_role"] = role

        amount = float(row.get("amount", 0) or 0)
        open_pct = float(row.get("open_pct", 0) or 0)
        ratio = row.get("bid_ask_ratio") or 0
        board_count = int(row.get("board_count", 0) or 0)
        auction_amt = auction_amount(row)
        limit_info = limit_up_stats.get(theme, {})

        amount_score = 3 if amount >= 3_000_000_000 else 2 if amount >= 1_500_000_000 else 1
        open_score = 3 if 1.0 <= open_pct <= 4.0 else 2 if 0.3 <= open_pct < 1.0 or 4.0 < open_pct <= 5.5 else 1
        bidask_score = 3 if ratio >= 1.8 else 2 if ratio >= 1.1 else 1
        theme_rank_score = 3 if theme_rank == 1 else 2 if theme_rank <= 2 else 1
        board_score = 3 if board_count >= 2 else 2 if board_count == 1 else 1
        theme_score = 3 if theme in top_themes[:1] else 2 if theme in top_themes else 1
        premium_score = 3 if role == "主线龙头候选" and open_pct <= 4.5 else 2 if role in {"主线龙头候选", "主线前排"} else 1

        total = amount_score + open_score + bidask_score + theme_rank_score + board_score + theme_score + premium_score
        vetoes = []
        if role == "非核心":
            vetoes.append("题材链路非核心")
        if theme in {"泛市场", "未知题材"}:
            vetoes.append("交易题材不清晰")
        if open_pct > 5.5:
            vetoes.append("高开过热")
        if ratio < 1.0:
            vetoes.append("承接不足")
        if ask1_vol := float(row.get("ask1_vol", 0) or 0):
            pass
        if float(row.get("ask1_vol", 0) or 0) == 0 and float(row.get("pct", 0) or 0) >= 9.8:
            vetoes.append("封死不给换手")
        if amount < 1_000_000_000 and theme_rank > 2:
            vetoes.append("量能与排序不匹配")

        dragon_questions = {
            "辨识度": theme_rank == 1 or (theme_rank == 2 and role == "主线前排"),
            "同身位资金偏好": amount >= 1_500_000_000 and auction_amt >= 20_000_000 and ratio >= 1.1,
            "次日溢价优先给它": role == "主线龙头候选" and theme in top_themes[:1] and open_pct <= 4.5,
        }
        yes_count = sum(1 for v in dragon_questions.values() if v)

        final_action = "回避"
        if environment == "强势日":
            if total >= 18 and yes_count >= 3 and role == "主线龙头候选" and not vetoes:
                final_action = "主攻"
            elif total >= 15 and yes_count >= 2 and role in {"主线龙头候选", "主线前排"}:
                final_action = "备选"
            elif total >= 12:
                final_action = "禁追观察"
        elif environment == "分歧日":
            if total >= 19 and yes_count >= 3 and role == "主线龙头候选" and len(vetoes) == 0 and board_count >= 1:
                final_action = "主攻"
            elif total >= 16 and yes_count >= 2 and role in {"主线龙头候选", "主线前排"} and len(vetoes) <= 1:
                final_action = "备选"
            elif total >= 13:
                final_action = "禁追观察"
        else:
            if total >= 20 and yes_count >= 3 and role == "主线龙头候选" and len(vetoes) == 0 and board_count >= 2:
                final_action = "主攻"
            elif total >= 17 and yes_count >= 2 and role == "主线龙头候选" and len(vetoes) <= 1:
                final_action = "备选"
            elif total >= 14:
                final_action = "禁追观察"

        if len(vetoes) >= 2 or yes_count <= 1:
            final_action = "回避"

        scored.append({
            "code": code,
            "name": row.get("name", ""),
            "total_score": total,
            "auction_snapshot": {
                "auction_amount": auction_amt,
                "bid_ask_ratio": ratio,
                "open_pct": open_pct,
            },
            "metrics": {
                "open_pct": open_pct,
                "pct": float(row.get("pct", 0) or 0),
                "amount": amount,
                "bid_ask_ratio": ratio,
                "ask1": float(row.get("ask1", 0) or 0),
            },
            "grades": {
                "amount": amount_score,
                "open": open_score,
                "bidask": bidask_score,
                "theme_rank": theme_rank_score,
                "board": board_score,
                "theme": theme_score,
                "premium": premium_score,
            },
            "theme": theme,
            "theme_rank": theme_rank,
            "rank_idx": theme_rank,
            "dragon_yes_count": yes_count,
            "dragon_questions": dragon_questions,
            "vetoes": vetoes,
            "final_action": final_action,
            "sector_tags": row.get("sector_tags", []),
            "semantics": {
                "primary_sector": (row.get("sector_tags") or ["未知"])[0] if row.get("sector_tags") else "未知",
                "sector_rank": theme_rank,
                "sector_member_count": theme_meta.get(theme, {}).get("member_count", 0),
                "chain_role": role,
                "is_main_sector": theme in top_themes,
                "trade_theme": theme,
                "theme_hits": row.get("theme_tags") or row.get("concept_tags") or [],
                "is_main_theme": theme in top_themes,
            },
            "board_count": board_count,
            "streak": row.get("streak", "0天0板"),
            "limit_up_type": row.get("limit_up_type", ""),
            "limit_up_time": row.get("limit_up_time", ""),
            "pct": float(row.get("pct", 0) or 0),
            "amount": amount,
        })

    action_order = {"主攻": 0, "备选": 1, "禁追观察": 2, "回避": 3}
    scored.sort(
        key=lambda x: (
            action_order.get(x["final_action"], 9),
            -x["total_score"],
            -x["dragon_yes_count"],
            x["theme_rank"],
            -x["amount"],
        )
    )

    primary = [x for x in scored if x["final_action"] == "主攻"][:1]
    backup = [x for x in scored if x["final_action"] == "备选"][:3]
    observe = [x for x in scored if x["final_action"] == "禁追观察"][:5]
    avoid = [x for x in scored if x["final_action"] == "回避"][:5]

    actionable_buckets = {
        "best_in_market": [
            {
                "code": x["code"],
                "name": x["name"],
                "pct": x["pct"],
                "amount": x["amount"],
                "board_count": x["board_count"],
                "streak": x["streak"],
                "limit_up_type": x["limit_up_type"],
                "limit_up_time": x["limit_up_time"],
                "theme": x["theme"],
                "role": x["semantics"]["chain_role"],
                "theme_rank": x["theme_rank"],
                "action": x["final_action"],
            }
            for x in scored[:5]
        ],
        "actionable_primary": [
            {
                "code": x["code"],
                "name": x["name"],
                "pct": x["pct"],
                "amount": x["amount"],
                "board_count": x["board_count"],
                "streak": x["streak"],
                "limit_up_type": x["limit_up_type"],
                "limit_up_time": x["limit_up_time"],
                "theme": x["theme"],
                "role": x["semantics"]["chain_role"],
                "theme_rank": x["theme_rank"],
                "action": x["final_action"],
            }
            for x in primary if x["pct"] < 9.8
        ],
        "low_absorb_watch": [
            {
                "code": x["code"],
                "name": x["name"],
                "pct": x["pct"],
                "amount": x["amount"],
                "board_count": x["board_count"],
                "streak": x["streak"],
                "limit_up_type": x["limit_up_type"],
                "limit_up_time": x["limit_up_time"],
                "theme": x["theme"],
                "role": x["semantics"]["chain_role"],
                "theme_rank": x["theme_rank"],
                "action": x["final_action"],
            }
            for x in backup + observe if x["pct"] < 5
        ][:5],
        "rebound_sell_watch": [],
        "do_not_chase": [
            {
                "code": x["code"],
                "name": x["name"],
                "pct": x["pct"],
                "amount": x["amount"],
                "board_count": x["board_count"],
                "streak": x["streak"],
                "limit_up_type": x["limit_up_type"],
                "limit_up_time": x["limit_up_time"],
                "theme": x["theme"],
                "role": x["semantics"]["chain_role"],
                "theme_rank": x["theme_rank"],
                "action": x["final_action"],
            }
            for x in scored if float(x["metrics"].get("ask1", 0) or 0) == 0 and x["pct"] >= 9.8
        ][:8],
    }

    market_map = {
        "environment_summary": f"{environment}，硬筛后{len(strategy_rows)}只，涨停池{len(limit_up_pool)}只",
        "top_trade_themes": Counter({k: v for k, v in theme_turnover.items()}).most_common(5),
        "top_sectors": Counter({k: v for k, v in theme_turnover.items()}).most_common(5),
        "top_limit_up_themes": Counter({k: v.get('limit_up_count', 0) for k, v in limit_up_stats.items()}).most_common(5),
    }

    sector_profiles = []
    for theme, info in sorted(theme_meta.items(), key=lambda kv: theme_scores.get(kv[0], 0), reverse=True)[:8]:
        members = info["members"]
        leader = members[0] if members else {"code": "", "name": ""}
        blowups = [m for m in members if m.get("limit_up_type") == "炸板" or (float(m.get("pct", 0) or 0) >= 4 and float(m.get("pct", 0) or 0) < 9.8)][:3]
        sector_profiles.append({
            "theme": theme,
            "member_count": len(members),
            "limit_up_count": limit_up_stats.get(theme, {}).get("limit_up_count", 0),
            "highest_board": info.get("highest_board", 0),
            "leader_code": leader.get("code", ""),
            "leader_name": leader.get("name", ""),
            "front_rows": [
                {
                    "code": x.get("code"),
                    "name": x.get("name", ""),
                    "pct": x.get("pct", 0),
                    "amount": x.get("amount", 0),
                    "board_count": x.get("board_count", 0),
                    "streak": x.get("streak", "0天0板"),
                    "limit_up_type": x.get("limit_up_type", ""),
                    "limit_up_time": x.get("limit_up_time", ""),
                    "theme": theme,
                    "role": "主线龙头候选" if idx == 0 else "主线前排" if idx <= 2 else "跟风前排",
                    "theme_rank": idx,
                }
                for idx, x in enumerate(members[:3], start=1)
            ],
            "blowups": [
                {
                    "code": x.get("code"),
                    "name": x.get("name", ""),
                    "pct": x.get("pct", 0),
                    "amount": x.get("amount", 0),
                    "board_count": x.get("board_count", 0),
                    "streak": x.get("streak", "0天0板"),
                    "limit_up_type": x.get("limit_up_type", ""),
                    "limit_up_time": x.get("limit_up_time", ""),
                    "theme": theme,
                    "role": "分歧炸板",
                    "theme_rank": rank_by_code.get(x.get("code", ""), 99),
                }
                for x in blowups
            ],
            "strength": "主升" if limit_up_stats.get(theme, {}).get("highest_board", 0) >= 3 or limit_up_stats.get(theme, {}).get("limit_up_count", 0) >= 3 else "分歧" if blowups else "轮动",
        })

    return {
        "environment": environment,
        "candidate_count": len(strategy_rows),
        "limit_up_count": len(limit_up_pool),
        "top_sectors_by_amount": Counter({k: v for k, v in theme_turnover.items()}).most_common(5),
        "top_trade_themes_by_amount": Counter({k: v for k, v in theme_turnover.items()}).most_common(5),
        "market_map": market_map,
        "sector_profiles": sector_profiles,
        "actionable_buckets": actionable_buckets,
        "primary": primary,
        "backup": backup,
        "observe": observe,
        "avoid": avoid,
        "top_ranked": scored[:12],
        "strategy_candidate_pool": scored,
        "top_themes": top_themes,
    }


def main() -> None:
    started = time.time()
    date_str = datetime.now().strftime("%Y%m%d")
    export_dir = OUT_DIR / date_str
    export_dir.mkdir(parents=True, exist_ok=True)

    stocks_payload = api_get("/stock_list")
    stocks = stocks_payload.get("stocks", [])

    sector_names = pick_sector_names()
    sector_map = build_sector_rank_map(sector_names)

    full_universe = []
    codes = []
    for item in stocks:
        code = item.get("code", "")
        name = item.get("name", "")
        if not is_main_board(code, name):
            continue
        full_universe.append(item)
        codes.append(code)

    quotes = []
    if codes:
        quote_payload = api_get("/quote", codes=",".join(codes))
        quotes = quote_payload.get("quotes", [])
    quote_map = {q.get("code"): q for q in quotes}

    all_candidates = [build_candidate_row(item, quote_map.get(item["code"], {}), sector_map) for item in full_universe]
    all_candidates.sort(key=lambda x: (x.get("amount", 0), auction_amount(x), x.get("open_pct", 0)), reverse=True)

    limit_up_payload = api_get("/limit_up_pool")
    limit_up_pool = []
    for item in limit_up_payload.get("limit_up", []):
        code = item.get("code", "")
        if not code or not is_main_board(code, item.get("name", "")):
            continue
        row = build_candidate_row(item, item, sector_map)
        row["stock_status"] = item.get("stockStatus", row.get("stock_status", 0))
        limit_up_pool.append(row)

    hard_filtered = []
    rejected = []
    for row in all_candidates:
        passed, reasons = passes_auction_hard_filter(row)
        row["trade_theme"] = normalize_theme(row)
        row["auction_amount"] = auction_amount(row)
        if passed:
            hard_filtered.append(row)
        else:
            rejected.append({
                "code": row["code"],
                "name": row["name"],
                "trade_theme": row["trade_theme"],
                "reject_reasons": reasons,
                "amount": row["amount"],
                "open_pct": row["open_pct"],
                "bid_ask_ratio": row.get("bid_ask_ratio"),
                "auction_amount": row["auction_amount"],
            })

    environment = classify_environment(len(limit_up_pool))
    result = score_strategy_candidates(hard_filtered, limit_up_pool, environment)

    output = {
        "generated_at": datetime.now().isoformat(),
        "source": BASE_URL,
        "strategy_scope": "main_board_non_st_full_universe_auction_leader",
        "sector_names_used": sector_names,
        "full_universe_count": len(all_candidates),
        "candidate_count": len(hard_filtered),
        "rejected_count": len(rejected),
        "limit_up_count": len(limit_up_pool),
        "theme_mapping_enabled": True,
        "review_fields_enabled": True,
        "selection_pipeline": [
            "主板非ST全量",
            "竞价硬筛",
            "题材归类",
            "龙头优先",
            "次日溢价导向排序",
        ],
        "candidates": hard_filtered,
        "strategy_candidate_pool": result["strategy_candidate_pool"],
        "rejected_samples": rejected[:200],
        "limit_up_pool": limit_up_pool,
        "strategy_result": result,
        "elapsed_seconds": round(time.time() - started, 3),
    }

    out_file = export_dir / "auction_candidates_main_board_non_st.json"
    out_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out_file))
    print(json.dumps({
        "full_universe_count": len(all_candidates),
        "candidate_count": len(hard_filtered),
        "rejected_count": len(rejected),
        "limit_up_count": len(limit_up_pool),
        "top_themes": result.get("top_themes", []),
        "selection_pipeline": output["selection_pipeline"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
