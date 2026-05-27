"""
Yuanbao sticker (TIMFaceElem) support.

Ported from yuanbao-openclaw-plugin/src/sticker/.

TIMFaceElem wire format:
    {
        "msg_type": "TIMFaceElem",
        "msg_content": {
            "index": 0,          # always 0 per Yuanbao convention
            "data": "<json>",    # serialised sticker metadata
        }
    }

The `data` field carries a JSON string with the sticker's metadata so the
receiver can look up the correct asset in the emoji pack.
"""

from __future__ import annotations

import json
import random
import re
import unicodedata
from typing import Optional

# ---------------------------------------------------------------------------
# Sticker catalogue – ported from builtin-stickers.json
# Key   : canonical name (Chinese)
# Value : {sticker_id, package_id, name, description, width, height, formats}
# ---------------------------------------------------------------------------
STICKER_MAP: dict[str, dict] = {
    "六六六": {
        "sticker_id": "278", "package_id": "1003", "name": "六六六",
        "description": t('yuanbao_sticker.666.awesome'),
        "width": 128, "height": 128, "formats": "png",
    },
    "我想开了": {
        "sticker_id": "262", "package_id": "1003", "name": "我想开了",
        "description": t('yuanbao_sticker.'),
        "width": 128, "height": 128, "formats": "png",
    },
    "害羞": {
        "sticker_id": "130", "package_id": "1003", "name": "害羞",
        "description": t('yuanbao_sticker._1'),
        "width": 128, "height": 128, "formats": "png",
    },
    "比心": {
        "sticker_id": "252", "package_id": "1003", "name": "比心",
        "description": t('yuanbao_sticker.love.heart'),
        "width": 128, "height": 128, "formats": "png",
    },
    "委屈": {
        "sticker_id": "125", "package_id": "1003", "name": "委屈",
        "description": t('yuanbao_sticker._2'),
        "width": 128, "height": 128, "formats": "png",
    },
    "亲亲": {
        "sticker_id": "146", "package_id": "1003", "name": "亲亲",
        "description": t('yuanbao_sticker.mua.kiss'),
        "width": 128, "height": 128, "formats": "png",
    },
    "酷": {
        "sticker_id": "131", "package_id": "1003", "name": "酷",
        "description": t('yuanbao_sticker.cool.swagger'),
        "width": 128, "height": 128, "formats": "png",
    },
    "睡": {
        "sticker_id": "145", "package_id": "1003", "name": "睡",
        "description": t('yuanbao_sticker.zzz.sleepy'),
        "width": 128, "height": 128, "formats": "png",
    },
    "发呆": {
        "sticker_id": "152", "package_id": "1003", "name": "发呆",
        "description": t('yuanbao_sticker._3'),
        "width": 128, "height": 128, "formats": "png",
    },
    "可怜": {
        "sticker_id": "157", "package_id": "1003", "name": "可怜",
        "description": t('yuanbao_sticker._4'),
        "width": 128, "height": 128, "formats": "png",
    },
    "摊手": {
        "sticker_id": "200", "package_id": "1003", "name": "摊手",
        "description": t('yuanbao_sticker.whatever'),
        "width": 128, "height": 128, "formats": "png",
    },
    "头大": {
        "sticker_id": "213", "package_id": "1003", "name": "头大",
        "description": t('yuanbao_sticker._5'),
        "width": 128, "height": 128, "formats": "png",
    },
    "吓": {
        "sticker_id": "256", "package_id": "1003", "name": "吓",
        "description": t('yuanbao_sticker._6'),
        "width": 128, "height": 128, "formats": "png",
    },
    "吐血": {
        "sticker_id": "203", "package_id": "1003", "name": "吐血",
        "description": t('yuanbao_sticker._7'),
        "width": 128, "height": 128, "formats": "png",
    },
    "哼": {
        "sticker_id": "185", "package_id": "1003", "name": "哼",
        "description": t('yuanbao_sticker._8'),
        "width": 128, "height": 128, "formats": "png",
    },
    "嘿嘿": {
        "sticker_id": "220", "package_id": "1003", "name": "嘿嘿",
        "description": t('yuanbao_sticker._9'),
        "width": 128, "height": 128, "formats": "png",
    },
    "头秃": {
        "sticker_id": "218", "package_id": "1003", "name": "头秃",
        "description": t('yuanbao_sticker._10'),
        "width": 128, "height": 128, "formats": "png",
    },
    "暗中观察": {
        "sticker_id": "221", "package_id": "1003", "name": "暗中观察",
        "description": t('yuanbao_sticker._11'),
        "width": 128, "height": 128, "formats": "png",
    },
    "我酸了": {
        "sticker_id": "224", "package_id": "1003", "name": "我酸了",
        "description": t('yuanbao_sticker._12'),
        "width": 128, "height": 128, "formats": "png",
    },
    t('yuanbao_sticker.call'): {
        "sticker_id": "246", "package_id": "1003", "name": "打call",
        "description": t('yuanbao_sticker.call_1'),
        "width": 128, "height": 128, "formats": "png",
    },
    "庆祝": {
        "sticker_id": "251", "package_id": "1003", "name": "庆祝",
        "description": t('yuanbao_sticker.party'),
        "width": 128, "height": 128, "formats": "png",
    },
    "奋斗": {
        "sticker_id": "151", "package_id": "1003", "name": "奋斗",
        "description": t('yuanbao_sticker._13'),
        "width": 128, "height": 128, "formats": "png",
    },
    "惊讶": {
        "sticker_id": "143", "package_id": "1003", "name": "惊讶",
        "description": t('yuanbao_sticker.omg'),
        "width": 128, "height": 128, "formats": "png",
    },
    "疑问": {
        "sticker_id": "144", "package_id": "1003", "name": "疑问",
        "description": t('yuanbao_sticker._14'),
        "width": 128, "height": 128, "formats": "png",
    },
    "仔细分析": {
        "sticker_id": "248", "package_id": "1003", "name": "仔细分析",
        "description": t('yuanbao_sticker._15'),
        "width": 128, "height": 128, "formats": "png",
    },
    "撅嘴": {
        "sticker_id": "184", "package_id": "1003", "name": "撅嘴",
        "description": t('yuanbao_sticker._16'),
        "width": 128, "height": 128, "formats": "png",
    },
    "泪奔": {
        "sticker_id": "199", "package_id": "1003", "name": "泪奔",
        "description": t('yuanbao_sticker._17'),
        "width": 128, "height": 128, "formats": "png",
    },
    "尊嘟假嘟": {
        "sticker_id": "276", "package_id": "1003", "name": "尊嘟假嘟",
        "description": t('yuanbao_sticker._18'),
        "width": 128, "height": 128, "formats": "png",
    },
    "略略略": {
        "sticker_id": "113", "package_id": "1003", "name": "略略略",
        "description": t('yuanbao_sticker._19'),
        "width": 128, "height": 128, "formats": "png",
    },
    "困": {
        "sticker_id": "180", "package_id": "1003", "name": "困",
        "description": t('yuanbao_sticker.sleepy'),
        "width": 128, "height": 128, "formats": "png",
    },
    "折磨": {
        "sticker_id": "181", "package_id": "1003", "name": "折磨",
        "description": t('yuanbao_sticker._20'),
        "width": 128, "height": 128, "formats": "png",
    },
    "抠鼻": {
        "sticker_id": "182", "package_id": "1003", "name": "抠鼻",
        "description": t('yuanbao_sticker._21'),
        "width": 128, "height": 128, "formats": "png",
    },
    "鼓掌": {
        "sticker_id": "183", "package_id": "1003", "name": "鼓掌",
        "description": t('yuanbao_sticker.666'),
        "width": 128, "height": 128, "formats": "png",
    },
    "斜眼笑": {
        "sticker_id": "204", "package_id": "1003", "name": "斜眼笑",
        "description": t('yuanbao_sticker.doge'),
        "width": 128, "height": 128, "formats": "png",
    },
    "辣眼睛": {
        "sticker_id": "216", "package_id": "1003", "name": "辣眼睛",
        "description": t('yuanbao_sticker.cringe'),
        "width": 128, "height": 128, "formats": "png",
    },
    "哦哟": {
        "sticker_id": "217", "package_id": "1003", "name": "哦哟",
        "description": t('yuanbao_sticker._22'),
        "width": 128, "height": 128, "formats": "png",
    },
    "吃瓜": {
        "sticker_id": "222", "package_id": "1003", "name": "吃瓜",
        "description": t('yuanbao_sticker._23'),
        "width": 128, "height": 128, "formats": "png",
    },
    "狗头": {
        "sticker_id": "225", "package_id": "1003", "name": "狗头",
        "description": t('yuanbao_sticker.doge_1'),
        "width": 128, "height": 128, "formats": "png",
    },
    "敬礼": {
        "sticker_id": "227", "package_id": "1003", "name": "敬礼",
        "description": t('yuanbao_sticker.salute'),
        "width": 128, "height": 128, "formats": "png",
    },
    "哦": {
        "sticker_id": "231", "package_id": "1003", "name": "哦",
        "description": t('yuanbao_sticker._24'),
        "width": 128, "height": 128, "formats": "png",
    },
    "拿到红包": {
        "sticker_id": "236", "package_id": "1003", "name": "拿到红包",
        "description": t('yuanbao_sticker._25'),
        "width": 128, "height": 128, "formats": "png",
    },
    "牛吖": {
        "sticker_id": "239", "package_id": "1003", "name": "牛吖",
        "description": t('yuanbao_sticker.666_1'),
        "width": 128, "height": 128, "formats": "png",
    },
    "贴贴": {
        "sticker_id": "272", "package_id": "1003", "name": "贴贴",
        "description": t('yuanbao_sticker._26'),
        "width": 128, "height": 128, "formats": "png",
    },
    "爱心": {
        "sticker_id": "138", "package_id": "1003", "name": "爱心",
        "description": t('yuanbao_sticker.love'),
        "width": 128, "height": 128, "formats": "png",
    },
    "晚安": {
        "sticker_id": "170", "package_id": "1003", "name": "晚安",
        "description": t('yuanbao_sticker.night.moon'),
        "width": 128, "height": 128, "formats": "png",
    },
    "太阳": {
        "sticker_id": "176", "package_id": "1003", "name": "太阳",
        "description": t('yuanbao_sticker.morning'),
        "width": 128, "height": 128, "formats": "png",
    },
    "柠檬": {
        "sticker_id": "266", "package_id": "1003", "name": "柠檬",
        "description": t('yuanbao_sticker._27'),
        "width": 128, "height": 128, "formats": "png",
    },
    "大冤种": {
        "sticker_id": "267", "package_id": "1003", "name": "大冤种",
        "description": t('yuanbao_sticker._28'),
        "width": 128, "height": 128, "formats": "png",
    },
    "吐了": {
        "sticker_id": "132", "package_id": "1003", "name": "吐了",
        "description": t('yuanbao_sticker.yue'),
        "width": 128, "height": 128, "formats": "png",
    },
    "怒": {
        "sticker_id": "134", "package_id": "1003", "name": "怒",
        "description": t('yuanbao_sticker._29'),
        "width": 128, "height": 128, "formats": "png",
    },
    "玫瑰": {
        "sticker_id": "165", "package_id": "1003", "name": "玫瑰",
        "description": t('yuanbao_sticker._30'),
        "width": 128, "height": 128, "formats": "png",
    },
    "凋谢": {
        "sticker_id": "119", "package_id": "1003", "name": "凋谢",
        "description": t('yuanbao_sticker._31'),
        "width": 128, "height": 128, "formats": "png",
    },
    "点赞": {
        "sticker_id": "159", "package_id": "1003", "name": "点赞",
        "description": t('yuanbao_sticker.good.like'),
        "width": 128, "height": 128, "formats": "png",
    },
    "握手": {
        "sticker_id": "164", "package_id": "1003", "name": "握手",
        "description": t('yuanbao_sticker.hello.deal'),
        "width": 128, "height": 128, "formats": "png",
    },
    "抱拳": {
        "sticker_id": "163", "package_id": "1003", "name": "抱拳",
        "description": t('yuanbao_sticker._32'),
        "width": 128, "height": 128, "formats": "png",
    },
    "ok": {
        "sticker_id": "169", "package_id": "1003", "name": "ok",
        "description": t('yuanbao_sticker.okay'),
        "width": 128, "height": 128, "formats": "png",
    },
    "拳头": {
        "sticker_id": "174", "package_id": "1003", "name": "拳头",
        "description": t('yuanbao_sticker.fight'),
        "width": 128, "height": 128, "formats": "png",
    },
    "鞭炮": {
        "sticker_id": "191", "package_id": "1003", "name": "鞭炮",
        "description": t('yuanbao_sticker._33'),
        "width": 128, "height": 128, "formats": "png",
    },
    "烟花": {
        "sticker_id": "258", "package_id": "1003", "name": "烟花",
        "description": t('yuanbao_sticker._34'),
        "width": 128, "height": 128, "formats": "png",
    },
}


def get_sticker_by_name(name: str) -> Optional[dict]:
    """
    按名称查找贴纸，支持模糊匹配。

    匹配优先级：
      1. 完全相等（name）
      2. name 包含查询词（前缀/子串）
      3. description 包含查询词（同义词搜索）
      4. 通用模糊评分（与 sticker-search 同算法），命中即返回得分最高的一条

    返回 sticker dict，找不到返回 None。
    """
    if not name:
        return None

    query = name.strip()

    if query in STICKER_MAP:
        return STICKER_MAP[query]

    for key, sticker in STICKER_MAP.items():
        if query in key or key in query:
            return sticker

    for sticker in STICKER_MAP.values():
        desc = sticker.get("description", "")
        if query in desc:
            return sticker

    matches = search_stickers(query, limit=1)
    return matches[0] if matches else None


def get_random_sticker(category: str = None) -> dict:
    """
    随机返回一个贴纸。

    若指定 category，则在 description 中含有该关键词的贴纸里随机选取；
    category 为 None 时从全表随机。
    """
    if category:
        candidates = [
            s for s in STICKER_MAP.values()
            if category in s.get("description", "") or category in s.get("name", "")
        ]
        if candidates:
            return random.choice(candidates)
    return random.choice(list(STICKER_MAP.values()))


def get_sticker_by_id(sticker_id: str) -> Optional[dict]:
    """按 sticker_id 精确查找贴纸。"""
    if not sticker_id:
        return None
    sid = str(sticker_id).strip()
    for sticker in STICKER_MAP.values():
        if sticker.get("sticker_id") == sid:
            return sticker
    return None


# ---------------------------------------------------------------------------
# 模糊搜索（对齐 chatbot-web yuanbao-openclaw-plugin/sticker-cache.ts.searchStickers）
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[\s\u3000\-_·.,，。!！?？\"“”'‘’、/\\]+")


def _normalize_text(raw: str) -> str:
    return unicodedata.normalize("NFKC", str(raw or "")).strip().lower()


def _compact_text(raw: str) -> str:
    return _PUNCT_RE.sub("", _normalize_text(raw))


def _multiset_char_hit_ratio(needle: str, haystack: str) -> float:
    if not needle:
        return 0.0
    bag: dict[str, int] = {}
    for ch in haystack:
        bag[ch] = bag.get(ch, 0) + 1
    hits = 0
    for ch in needle:
        n = bag.get(ch, 0)
        if n > 0:
            hits += 1
            bag[ch] = n - 1
    return hits / len(needle)


def _bigram_jaccard(a: str, b: str) -> float:
    if len(a) < 2 or len(b) < 2:
        return 0.0
    A = {a[i:i + 2] for i in range(len(a) - 1)}
    B = {b[i:i + 2] for i in range(len(b) - 1)}
    inter = len(A & B)
    union = len(A) + len(B) - inter
    return inter / union if union else 0.0


def _longest_subsequence_ratio(needle: str, haystack: str) -> float:
    if not needle:
        return 0.0
    j = 0
    for ch in haystack:
        if j >= len(needle):
            break
        if ch == needle[j]:
            j += 1
    return j / len(needle)


def _score_field(haystack: str, query: str) -> float:
    hay = _normalize_text(haystack)
    q = _normalize_text(query)
    if not hay or not q:
        return 0.0
    hay_c = _compact_text(haystack)
    q_c = _compact_text(query)
    best = 0.0
    if hay == q:
        best = max(best, 100.0)
    if q in hay:
        best = max(best, 92 + min(6, len(q)))
    if len(q) >= 2 and hay.startswith(q):
        best = max(best, 88.0)
    if q_c and q_c in hay_c:
        best = max(best, 86.0)
    best = max(best, _multiset_char_hit_ratio(q_c, hay_c) * 62)
    best = max(best, _bigram_jaccard(q_c, hay_c) * 58)
    best = max(best, _longest_subsequence_ratio(q_c, hay_c) * 52)
    if len(q) == 1 and q in hay:
        best = max(best, 68.0)
    return best


def search_stickers(query: str, limit: int = 10) -> list[dict]:
    """
    在内置贴纸表中按模糊匹配排序返回前 N 条结果。

    评分综合 name/description 字段的子串、字符多重集覆盖、bigram Jaccard、子序列比例。
    name 权重略高于 description（×0.88）。空 query 时按字典顺序返回前 N 条。
    """
    safe_limit = max(1, min(500, int(limit) if limit else 10))
    if not query or not _normalize_text(query):
        return list(STICKER_MAP.values())[:safe_limit]

    scored: list[tuple[float, dict]] = []
    for sticker in STICKER_MAP.values():
        name_s = _score_field(sticker.get("name", ""), query)
        desc_s = _score_field(sticker.get("description", ""), query) * 0.88
        sid = str(sticker.get("sticker_id", "")).strip()
        q_norm = _normalize_text(query)
        id_s = 0.0
        if sid and q_norm:
            sid_norm = _normalize_text(sid)
            if sid_norm == q_norm:
                id_s = 100.0
            elif q_norm in sid_norm:
                id_s = 84.0
        scored.append((max(name_s, desc_s, id_s), sticker))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[0][0] if scored else 0
    if top <= 0:
        return [s for _, s in scored[:safe_limit]]

    if top >= 22:
        floor = 18.0
    elif top >= 12:
        floor = max(10.0, top * 0.5)
    else:
        floor = max(6.0, top * 0.35)

    filtered = [pair for pair in scored if pair[0] >= floor]
    out = filtered if filtered else scored
    return [s for _, s in out[:safe_limit]]


def build_face_msg_body(
    face_index: int,
    face_type: int = 1,
    data: Optional[str] = None,
) -> list:
    """
    构造 TIMFaceElem 消息体。

    Yuanbao 约定：
      - index 固定传 0（服务端通过 data 字段识别具体表情）
      - data 为 JSON 字符串，包含 sticker_id / package_id 等字段

    Args:
        face_index: 保留字段，暂时不影响 wire format（Yuanbao 固定 index=0）。
                    当 face_index > 0 时视为旧版 QQ 表情 ID，直接放入 index。
        face_type:  保留字段（兼容旧接口，当前未使用）。
        data:       已序列化的 JSON 字符串；为 None 时仅传 index。

    Returns:
        符合 Yuanbao TIM 协议的 msg_body list，如::

            [{"msg_type": "TIMFaceElem", "msg_content": {"index": 0, "data": "..."}}]
    """
    msg_content: dict = {"index": face_index}
    if data is not None:
        msg_content["data"] = data
    return [{"msg_type": "TIMFaceElem", "msg_content": msg_content}]


def build_sticker_msg_body(sticker: dict) -> list:
    """
    从 STICKER_MAP 中的 sticker dict 直接构造 TIMFaceElem 消息体。

    这是 send_sticker() 的内部辅助，确保 data 字段与原始 JS 插件一致。
    """
    data_payload = json.dumps(
        {
            "sticker_id": sticker["sticker_id"],
            "package_id": sticker["package_id"],
            "width": sticker.get("width", 128),
            "height": sticker.get("height", 128),
            "formats": sticker.get("formats", "png"),
            "name": sticker["name"],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return build_face_msg_body(face_index=0, data=data_payload)
