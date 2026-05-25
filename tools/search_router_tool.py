#!/usr/bin/env python3
"""Native search-router tool for Hermes.

Routes public/external search tasks to the dedicated ``search-worker`` profile,
normalizes its output into a validated evidence packet, and returns both the raw
packet and a compact assistant brief for the parent agent to synthesize.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from hermes_constants import get_default_hermes_root
from tools.registry import registry, tool_error, tool_result

REQUIRED_KEYS = [
    "query_intent",
    "searches_performed",
    "sources",
    "key_findings",
    "conflicts",
    "unknowns",
    "recommended_next_step",
]

DEFAULT_SEARCH_WORKER_TIMEOUT_SECONDS = 120

_DEF_REPO_ROOT = Path(__file__).resolve().parent.parent

_QUOTA_PATTERNS = (
    r"HTTP\s*432",
    r"usage limit exceeded",
    r"exceeds your plan(?:'s)? set usage limit",
    r"plan usage limit",
    r"quota exhausted",
    r"quota exceeded",
)


SEARCH_ROUTER_SCHEMA = {
    "name": "search_router",
    "description": (
        "Route a public/external search task to the dedicated search-worker profile and return "
        "a normalized evidence packet plus a compact Chinese brief. Use this as the DEFAULT "
        "tool for broad web research, official-source checks, multi-source evidence gathering, "
        "and tasks needing official + community / Chinese + international cross-checks. Prefer "
        "this over direct web_search/web_extract when the task is not a trivial one-shot lookup."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task_goal": {
                "type": "string",
                "description": "What the search-worker should find or verify.",
            },
            "coverage": {
                "type": "string",
                "description": "Coverage requirements such as official source + Chinese public discussion.",
            },
            "min_sources": {
                "type": "integer",
                "description": "Minimum number of sources required.",
                "default": 2,
            },
            "model": {
                "type": "string",
                "description": "Optional worker model override. Defaults to DeepSeek-V4-Flash.",
            },
            "provider": {
                "type": "string",
                "description": "Optional worker provider override. Defaults to ctyun.",
            },
            "profile": {
                "type": "string",
                "description": "Worker profile name. Defaults to search-worker.",
            },
            "debug": {
                "type": "boolean",
                "description": "Include debug fields such as prompt and raw stdout snippets.",
                "default": False,
            },
        },
        "required": ["task_goal"],
    },
}


def check_search_router_requirements() -> bool:
    """Expose the tool unconditionally; runtime errors are returned explicitly."""
    return True


def _build_prompt(task_goal: str, coverage: str, min_sources: int) -> str:
    coverage = (coverage or "").strip() or "至少覆盖 1 条官方/一手来源；如主题涉及中文公开讨论，也覆盖至少 1 条中文公开来源；已知 URL/正文抽取/多页抓取优先走 Firecrawl，docs/code/security/英文技术资料 first-pass 优先 AnySearch。"
    min_sources = max(1, int(min_sources or 2))
    return (
        "你是 search-worker。\n\n"
        f"任务目标：\n{task_goal.strip()}\n\n"
        "搜索约束：\n"
        "- 中文实时/国内信息：优先用本地百度搜索脚本；必要时补 Tavily / AnySearch / 官方站点，但不要默认先走 AnySearch 或 Firecrawl。\n"
        "- docs / code / security / URL extract / 英文技术资料 first-pass：优先 AnySearch；但如果任务明显会很快进入正文抽取、官网页面读取或多页抓取，尽早切 Firecrawl。\n"
        "- Firecrawl 已在当前体系验证可用，优先把它用于：URL extract / 已知站点正文 / multi-page crawl / extract-heavy research / docs discovery 后大概率还要拉正文。\n"
        "- 强规则：只要任务已进入 URL extract / 已知站点正文 / docs discovery 后马上要拉正文 这类场景，默认必须先尝试 Firecrawl 抽取；只有 Firecrawl 失败、被目标站点拦截、或证据明确不足时，才回退 AnySearch extract / 其他抽取链。\n"
        "- 通用公网未知问题：优先走 Tavily 做 first-hop；拿到候选 URL 后尽快切抽取链，不要在同一问题上长时间重复 search。\n"
        "- 如果需要平台/CLI 搜索，可通过 terminal 调本机工具，但只限搜索/读取/抽取相关命令。\n"
        "- 对 academic 主研究链、中文主搜索链、平台原生搜索，不要默认让 AnySearch 或 Firecrawl 抢 first-hop。\n"
        "- 默认不要上 browser；只有静态搜索不足时，才把升级建议写进 recommended_next_step。\n"
        "- 当 Firecrawl 被使用时，在 searches_performed 里明确记录 web_search(firecrawl)、web_extract(firecrawl)、web_crawl(firecrawl) 或等价描述，避免主 agent 无法判断是否真的命中该路由。\n\n"
        "- 成本纪律：默认串行取证，同一轮不要并发开多个搜索/抽取工具调用；先做 1 次 first-hop，再决定下一步。\n"
        "- 预算纪律：除非任务天然需要宽覆盖，单任务默认控制在 最多 3 次 search + 2 次 extract 的量级。\n"
        "- 达到 min_sources 且已有官方/一手源后优先停止，不要继续横向扩张相近来源。\n"
        "- 如果 2~3 条高质量来源已经足够支撑核心判断，直接收口；剩余缺口写进 unknowns / recommended_next_step。\n\n"
        "结果要求：\n"
        "- 只输出 evidence packet 所需内容。\n"
        f"- 必须覆盖：{coverage}\n"
        "- 如果证据不足，不要硬下结论，把缺口写进 unknowns。\n"
        "- 如果有冲突来源，把冲突写进 conflicts。\n"
        "- 必须输出严格 JSON，对象字段固定为：\n"
        "  query_intent, searches_performed, sources, key_findings, conflicts, unknowns, recommended_next_step\n"
        "- 如果输出任何 JSON 之外的前言、总结、解释、markdown 代码块或围栏，视为失败。\n\n"
        "质量要求：\n"
        "- 尽量包含一手源/官方源\n"
        "- 找到链接不等于完成验证，能抽正文就抽正文\n"
        f"- sources 至少 {min_sources} 条\n"
        "- 达到 min_sources 且已有官方/一手源时，优先停止，不继续横向扩张。\n"
        "- 不要为了“更完整”而无限追加相近来源。\n"
        "- 不要为了“更完整”把同类型 search 连续铺开；每多一次 search/extract 都要有明确新增价值。\n"
        "- 如果还需深挖，把缺口写进 recommended_next_step，不要自行继续扩题。\n"
        "- 结果交给主 agent，不需要替最终用户拍板\n"
    ).strip()


def _extract_first_json_object(text: str) -> str:
    start = text.find("{")
    if start == -1:
        raise ValueError("stdout 中未找到 JSON 起始符 {")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    raise ValueError("stdout 中找到 { 但未找到完整闭合 JSON 对象")


def _detect_non_json_wrapper_text(text: str, json_text: str) -> List[str]:
    start = text.find(json_text)
    if start == -1:
        return []
    prefix = text[:start].strip()
    suffix = text[start + len(json_text) :].strip()
    issues: List[str] = []
    if prefix:
        issues.append("stdout 在 JSON 前包含额外文本")
    if suffix:
        issues.append("stdout 在 JSON 后包含额外文本")
    return issues


def _validate_packet(obj: Dict[str, Any]) -> List[str]:
    missing = [k for k in REQUIRED_KEYS if k not in obj]
    type_errors = []
    if "searches_performed" in obj and not isinstance(obj["searches_performed"], list):
        type_errors.append("searches_performed 不是数组")
    if "sources" in obj and not isinstance(obj["sources"], list):
        type_errors.append("sources 不是数组")
    if "key_findings" in obj and not isinstance(obj["key_findings"], list):
        type_errors.append("key_findings 不是数组")
    if "conflicts" in obj and not isinstance(obj["conflicts"], list):
        type_errors.append("conflicts 不是数组")
    if "unknowns" in obj and not isinstance(obj["unknowns"], list):
        type_errors.append("unknowns 不是数组")
    if "recommended_next_step" in obj and not isinstance(obj["recommended_next_step"], (str, dict, list)):
        type_errors.append("recommended_next_step 类型不合法")
    return missing + type_errors


def _looks_like_quota_exhausted(*texts: Any) -> bool:
    parts: List[str] = []
    for t in texts:
        if isinstance(t, bytes):
            parts.append(t.decode("utf-8", errors="ignore"))
        elif isinstance(t, str):
            parts.append(t)
    haystack = "\n".join(parts).lower()
    if not haystack:
        return False
    return any(re.search(pattern, haystack, flags=re.IGNORECASE) for pattern in _QUOTA_PATTERNS)


def _bulletize(item: Any) -> List[str]:
    if isinstance(item, str):
        text = item.strip()
        return [text] if text else []
    if isinstance(item, dict):
        vals = [str(v).strip() for v in item.values() if str(v).strip()]
        return vals or [json.dumps(item, ensure_ascii=False)]
    if isinstance(item, list):
        out: List[str] = []
        for x in item:
            out.extend(_bulletize(x))
        return out
    text = str(item).strip()
    return [text] if text else []


def _summarize_packet(packet: Dict[str, Any]) -> str:
    lines: List[str] = ["**结论**"]
    bullets: List[str] = []
    for item in (packet.get("key_findings") or [])[:6]:
        bullets.extend(_bulletize(item))
    if bullets:
        for item in bullets[:6]:
            lines.append(f"- {item}")
    else:
        lines.append("- 暂无足够结论")

    srcs = packet.get("sources") or []
    if srcs:
        lines.extend(["", "**关键信源**"])
        for s in srcs[:5]:
            if isinstance(s, dict):
                title = s.get("title", "未命名来源")
                stype = s.get("source_type", "")
                url = s.get("url", "")
                lines.append(f"- {title}｜{stype}｜{url}")
            else:
                lines.append(f"- {s}")

    conflict_bullets: List[str] = []
    for item in (packet.get("conflicts") or [])[:4]:
        conflict_bullets.extend(_bulletize(item))
    if conflict_bullets:
        lines.extend(["", "**冲突/注意点**"])
        for item in conflict_bullets[:4]:
            lines.append(f"- {item}")

    unknown_bullets: List[str] = []
    for item in (packet.get("unknowns") or [])[:4]:
        unknown_bullets.extend(_bulletize(item))
    if unknown_bullets:
        lines.extend(["", "**未确认**"])
        for item in unknown_bullets[:4]:
            lines.append(f"- {item}")

    next_bullets = _bulletize(packet.get("recommended_next_step"))[:4]
    if next_bullets:
        lines.extend(["", "**建议下一步**"])
        for item in next_bullets:
            lines.append(f"- {item}")
    return "\n".join(lines).strip()


def _select_worker_python(repo_root: Path = _DEF_REPO_ROOT) -> str:
    candidates = [
        repo_root / "venv" / "bin" / "python",
        repo_root / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return sys.executable


def _run_worker(
    prompt: str,
    profile: str,
    provider: str,
    model: str,
    timeout_seconds: int = DEFAULT_SEARCH_WORKER_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess:
    root = get_default_hermes_root()
    profile = (profile or "").strip() or "search-worker"
    provider = (provider or "").strip()
    model = (model or "").strip()

    profile_dir = root / "profiles" / profile
    if not profile_dir.exists():
        raise FileNotFoundError(f"search-worker profile 不存在: {profile_dir}")

    env = dict(os.environ)
    env["HERMES_HOME"] = str(root / "profiles" / profile)

    worker_python = _select_worker_python()

    cmd = [
        worker_python,
        "-m",
        "hermes_cli.main",
        "chat",
        "-q",
        prompt,
        "-Q",
    ]
    if provider:
        cmd.extend(["--provider", provider])
    if model:
        cmd.extend(["-m", model])
    return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout_seconds)


def search_router_tool(
    task_goal: str,
    coverage: str = None,
    min_sources: int = 2,
    model: str = "DeepSeek-V4-Flash",
    provider: str = "ctyun",
    profile: str = "search-worker",
    debug: bool = False,
) -> str:
    task_goal = (task_goal or "").strip()
    if not task_goal:
        return tool_error("task_goal is required", success=False)

    prompt = _build_prompt(task_goal, coverage or "", min_sources)

    try:
        proc = _run_worker(prompt=prompt, profile=profile, provider=provider, model=model)
    except FileNotFoundError as e:
        return tool_error(str(e), success=False, error_type="profile_missing")
    except subprocess.TimeoutExpired as e:
        stdout_head = ((e.stdout or "")[:2000] if isinstance(e.stdout, str) else "")
        stderr_tail = ((e.stderr or "")[-1000:] if isinstance(e.stderr, str) else "")
        quota_exhausted = _looks_like_quota_exhausted(stdout_head, stderr_tail, str(e))
        return tool_result(
            success=False,
            error_type="quota_exhausted" if quota_exhausted else "worker_timeout",
            message=str(e),
            stdout_head=stdout_head,
            stderr_tail=stderr_tail,
            worker_profile=profile,
            worker_provider=provider,
            worker_model=model,
            quota_exhausted=quota_exhausted,
            recommended_fallback=(
                "Install/use ddgs or configure searxng/exa/firecrawl/parallel; avoid hard-locking search_backend=tavily"
                if quota_exhausted
                else "Inspect worker logs / provider rate limits / backend availability"
            ),
        )
    except Exception as e:
        return tool_error(f"search-worker 调用失败: {e}", success=False, error_type="spawn_failed")

    if proc.returncode != 0:
        stdout_head = (proc.stdout or "")[:2000]
        stderr_tail = (proc.stderr or "")[-2000:]
        quota_exhausted = _looks_like_quota_exhausted(stdout_head, stderr_tail)
        return tool_result(
            success=False,
            error_type="quota_exhausted" if quota_exhausted else "worker_process_failed",
            exit_code=proc.returncode,
            stderr=stderr_tail,
            stdout_head=stdout_head,
            quota_exhausted=quota_exhausted,
            recommended_fallback=(
                "Install/use ddgs or configure searxng/exa/firecrawl/parallel; avoid hard-locking search_backend=tavily"
                if quota_exhausted
                else "Inspect worker stderr/stdout and router-vs-profile runtime"
            ),
        )

    try:
        json_text = _extract_first_json_object(proc.stdout or "")
        obj = json.loads(json_text)
        validation_issues = _validate_packet(obj)
        wrapper_warnings = _detect_non_json_wrapper_text(proc.stdout or "", json_text)
        payload: Dict[str, Any] = {
            "success": len(validation_issues) == 0,
            "issues": validation_issues,
            "warnings": wrapper_warnings,
            "packet": obj,
            "assistant_brief": _summarize_packet(obj),
            "worker_profile": profile,
            "worker_provider": provider,
            "worker_model": model,
        }
        if debug:
            payload["debug"] = {
                "prompt": prompt,
                "raw_stdout_head": (proc.stdout or "")[:2000],
                "raw_stderr_tail": (proc.stderr or "")[-1000:],
            }
        return tool_result(payload)
    except Exception as e:
        return tool_result(
            success=False,
            error_type="json_extract_or_parse_failed",
            message=str(e),
            stdout_head=(proc.stdout or "")[:2000],
            stderr_tail=(proc.stderr or "")[-1000:],
        )


registry.register(
    name="search_router",
    toolset="web",
    schema=SEARCH_ROUTER_SCHEMA,
    handler=lambda args, **kw: search_router_tool(
        task_goal=args.get("task_goal", ""),
        coverage=args.get("coverage"),
        min_sources=args.get("min_sources", 2),
        model=args.get("model", "DeepSeek-V4-Flash"),
        provider=args.get("provider", "ctyun"),
        profile=args.get("profile", "search-worker"),
        debug=bool(args.get("debug", False)),
    ),
    check_fn=check_search_router_requirements,
    emoji="🧭",
)
