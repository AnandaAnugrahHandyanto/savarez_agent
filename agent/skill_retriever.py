"""
skill_retriever.py — 按意图动态检索 Skills，替代全量注入
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
v2.0: Embedding 语义检索 (DashScope text-embedding-v3, 1024d)
  策略:
    1. 加载预生成的 embeddings (~/.hermes/.skills_embeddings.json, 4.8MB)
    2. 用户消息 → DashScope embedding API → 1024d 向量
    3. Cosine 相似度排序 → Top 5 + always_on
    4. 构建精简 <available_skills> XML (~250-500t)
  降级: 关键词匹配 (embeddings 文件缺失时回退)
  Token 节省: 8,400t → ~300t (96%)
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 常驻基础 Skills（永远注入）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ALWAYS_ON_SKILLS: Set[str] = {
    "four-eyes-scheduler",
    "hermes-agent",
    "polya-problem-solving",
    "systematic-debugging",
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Embedding 缓存
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_EMBEDDINGS_CACHE: Optional[dict] = None
_EMBEDDINGS_CACHE_TS: float = 0.0
_EMBEDDINGS_CACHE_TTL: float = 3600.0  # 1 小时重载

# DashScope API
_EMBEDDING_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
_EMBEDDING_MODEL = "text-embedding-v3"
_EMBEDDING_DIMS = 1024


def _get_api_key() -> str:
    """从 config.yaml 读取 dashscope api_key。"""
    try:
        import yaml
        config_path = get_hermes_home() / "config.yaml"
        if config_path.exists():
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
            return (
                cfg.get("providers", {}).get("dashscope", {}).get("api_key", "")
                or cfg.get("auxiliary", {}).get("vision", {}).get("api_key", "")
                or os.environ.get("DASHSCOPE_API_KEY", "")
            )
    except Exception:
        pass
    return os.environ.get("DASHSCOPE_API_KEY", "")


def _load_embeddings() -> Optional[dict]:
    """加载预生成的 embeddings 文件。带 TTL 缓存。"""
    global _EMBEDDINGS_CACHE, _EMBEDDINGS_CACHE_TS
    now = time.time()
    if _EMBEDDINGS_CACHE is not None and (now - _EMBEDDINGS_CACHE_TS) < _EMBEDDINGS_CACHE_TTL:
        return _EMBEDDINGS_CACHE

    path = get_hermes_home() / ".skills_embeddings.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            _EMBEDDINGS_CACHE = json.load(f)
        _EMBEDDINGS_CACHE_TS = now
        return _EMBEDDINGS_CACHE
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Embeddings 加载失败: %s", e)
        return None


def _embed_text(text: str) -> Optional[List[float]]:
    """调用 DashScope embedding API，返回 1024d 向量。"""
    api_key = _get_api_key()
    if not api_key:
        logger.debug("无 DashScope API key，跳过 embedding")
        return None

    try:
        import requests
        resp = requests.post(
            _EMBEDDING_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": _EMBEDDING_MODEL, "input": text},
            timeout=5,
        )
        if resp.status_code != 200:
            logger.debug("Embedding API 返回 %d: %s", resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        return data["data"][0]["embedding"]
    except Exception as e:
        logger.debug("Embedding API 调用失败: %s", e)
        return None


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """两个 1024d 向量的余弦相似度。"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 降级: 关键词匹配（v1.0 逻辑，embeddings 不可用时回退）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import re as _re

_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "boss|招聘|简历|面试|求职|投递|猎聘|智联": [
        "boss-auto-greet", "boss-scanner", "job-tracker",
        "job-reporter", "job-quality-engine", "recruitment-specialist",
        "liepin-scanner", "liepin-auto-apply",
        "zhilian-scanner", "zhilian-auto-apply", "unified-scanner",
    ],
    "架构|设计|系统|design|bible|架构图": [
        "hermes-design-bible", "software-architect",
        "architecture-diagram", "ux-architect",
        "hermes-playbook-knowledge", "agent-routing-architecture",
    ],
    "代码|编程|code|开发|实现|function|class|debug|fix|bug": [
        "systematic-debugging", "codebase-inspection",
        "test-driven-development", "engineering-code-reviewer",
        "subagent-driven-development", "writing-plans",
        "plan", "spike", "requesting-code-review",
    ],
    "部署|deploy|docker|container|k8s|kubernetes|重启|restart|服务": [
        "docker-management", "hermes-update-safety",
        "self-healing-agent-infrastructure",
        "devops-automator", "engineering-sre",
    ],
    "成本|cost|token|花费|账单|价格|定价|消费": [
        "daily-cost-report",
    ],
    "文档|doc|笔记|note|记录|报告|report|写作|write": [
        "obsidian", "technical-writer", "document-generator",
    ],
    "子agent|subagent|delegate|委托|编排|orchestrat": [
        "subagent-orchestrator", "autonomous-ai-agents",
        "agents-orchestrator",
    ],
    "记忆|memory|session|会话|hindsight|历史|过去|上次": [
        "session-search-architecture",
        "agent-memory-architecture",
        "agent-memory-research-synthesis",
    ],
    "图片|image|视频|video|音频|audio|音乐|music|画图|生成": [
        "comfyui", "pixel-art", "ascii-art",
        "ascii-video", "songwriting-and-ai-music",
        "spotify", "youtube-content",
    ],
}

_COMPILED_DOMAINS = [
    (_re.compile(k, _re.IGNORECASE), v) for k, v in _DOMAIN_KEYWORDS.items()
]


def _retrieve_keyword(user_intent: str, top_k: int, always_on: Set[str]) -> List[Tuple[str, str, int]]:
    """关键词降级检索。"""
    from agent.skill_retriever import _load_skills_snapshot as _load_snapshot
    # 使用本地 snapshot
    snapshot_path = get_hermes_home() / ".skills_prompt_snapshot.json"
    if not snapshot_path.exists():
        return [(name, "", 99) for name in always_on]

    with open(snapshot_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    skill_map: Dict[str, str] = {}
    for entry in data.get("skills", []):
        name = entry.get("skill_name") or entry.get("frontmatter_name") or ""
        if name:
            skill_map[name] = entry.get("description", "")

    scores: Dict[str, int] = {}
    for pattern, skill_names in _COMPILED_DOMAINS:
        if pattern.search(user_intent):
            for sn in skill_names:
                if sn in skill_map:
                    scores[sn] = scores.get(sn, 0) + 10

    query_lower = user_intent.lower()
    for skill_name, description in skill_map.items():
        score = scores.get(skill_name, 0)
        name_parts = _re.split(r"[-_]", skill_name)
        for kw in _re.findall(r"[\u4e00-\u9fff]{2,4}|[a-zA-Z]{3,}", user_intent):
            if kw.lower() in skill_name.lower():
                score += 5
            for part in name_parts:
                if kw.lower() in part.lower():
                    score += 3
            if kw.lower() in description.lower():
                score += 2
        if score > 0:
            scores[skill_name] = score

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top = [(name, skill_map[name], score) for name, score in ranked[:top_k]]
    seen = {s[0] for s in top}
    for name in always_on:
        if name not in seen and name in skill_map:
            top.append((name, skill_map[name], 99))
    return top


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 主检索函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def retrieve_skills(
    user_intent: str,
    top_k: int = 5,
    always_on: Optional[Set[str]] = None,
) -> List[Tuple[str, str, int]]:
    """根据用户意图检索最相关的 skills。

    Embedding 语义相似度 + 关键词领域加权融合。

    Returns:
        List of (skill_name, description, relevance_score × 100), sorted desc.
    """
    if always_on is None:
        always_on = ALWAYS_ON_SKILLS

    # 加载 skill 元数据
    snapshot_path = get_hermes_home() / ".skills_prompt_snapshot.json"
    skill_map: Dict[str, str] = {}
    if snapshot_path.exists():
        with open(snapshot_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data.get("skills", []):
            n = entry.get("skill_name") or entry.get("frontmatter_name") or ""
            if n:
                skill_map[n] = entry.get("description", "")
    if not skill_map:
        return [(name, "", 99) for name in always_on]

    # ── Layer 1: Embedding 语义相似度 (基础分 0-100) ──
    base_scores: Dict[str, float] = {}
    emb_data = _load_embeddings()
    query_vec = _embed_text(user_intent) if emb_data else None

    if query_vec and emb_data and emb_data.get("skills"):
        for name, info in emb_data["skills"].items():
            vec = info.get("vec")
            if vec and len(vec) == _EMBEDDING_DIMS:
                base_scores[name] = _cosine_similarity(query_vec, vec) * 100

    # ── Layer 2: 关键词领域加权 (加分 0-30) ──
    keyword_bonus: Dict[str, int] = {}
    for pattern, skill_names in _COMPILED_DOMAINS:
        if pattern.search(user_intent):
            for sn in skill_names:
                if sn in skill_map:
                    keyword_bonus[sn] = keyword_bonus.get(sn, 0) + 20

    # ── 融合排序 ──
    combined: List[Tuple[str, float]] = []
    for name in skill_map:
        score = base_scores.get(name, 0.0) + keyword_bonus.get(name, 0)
        if score > 0:
            combined.append((name, score))

    combined.sort(key=lambda x: x[1], reverse=True)

    top = []
    seen = set()
    for name, score in combined[:top_k]:
        top.append((name, skill_map.get(name, ""), int(score)))
        seen.add(name)

    # 追加 always_on
    for name in always_on:
        if name not in seen and name in skill_map:
            top.append((name, skill_map.get(name, ""), 99))

    logger.debug(
        "Skill retrieval: embedding=%s keyword=%s → %d skills (query=%.30s...)",
        "hit" if query_vec else "miss", "hit" if keyword_bonus else "miss",
        len(top), user_intent,
    )
    return top


def build_dynamic_skills_prompt(skills: List[Tuple[str, str, int]]) -> str:
    """从检索结果构建精简 <available_skills> XML 块。

    Token 预算: ~250-500t (vs 全量 7,400t)
    """
    if not skills:
        return (
            "<available_skills>\n"
            "  Note: No skills matched your current task.\n"
            "  Use skill_view(name='hermes-agent') to see the full catalog.\n"
            "  Always-on skills loaded.\n"
            "</available_skills>\n"
        )

    lines = ["<available_skills>"]
    for skill_name, description, _score in skills:
        desc = description.strip()
        if len(desc) > 120:
            desc = desc[:117] + "..."
        lines.append(f"  - {skill_name}: {desc}")

    lines.append("")
    lines.append(
        "  Note: Context-aware subset. If a needed skill is not listed, "
        "use skill_view(name='hermes-agent') for the full catalog."
    )
    lines.append("</available_skills>")
    return "\n".join(lines) + "\n"


def estimate_skills_tokens(skills: List[Tuple[str, str, int]]) -> int:
    """估算动态 skills 列表的 token 数 (~2.75 chars/token)。"""
    prompt = build_dynamic_skills_prompt(skills)
    return len(prompt) * 100 // 275
