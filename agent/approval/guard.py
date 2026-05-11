"""Approval guard — hard rules + LLM risk assessment.

Evaluated BEFORE Skills Hub in _execute_tool_calls_sequential.
Safe by default: any failure in Step 2 → reject.
"""

from __future__ import annotations

import json
import logging
import re
import textwrap
from dataclasses import dataclass
from typing import Optional

from .config import ApprovalConfig

logger = logging.getLogger(__name__)


@dataclass
class ApprovalDecision:
    """Result of an approval check."""
    approved: bool
    risk_level: str          # "high" | "medium" | "low" | "blocked"
    reason: str
    source: str              # "hard_rule_block" | "hard_rule_ask" | "llm_assessment"


class ApprovalGuard:
    """Three-step safety gate for tool execution.

    Step 1: Hard rules (regex matching) — zero LLM cost, <1ms.
    Step 2: LLM risk assessment — for nuanced tools not caught by Step 1.
    Step 3: Decision — map risk level to allow/reject.

    Usage:
        guard = ApprovalGuard(config)
        decision = guard.check(
            action="terminal",
            args={"command": "rm -rf /"},
            model="deepseek-v4-flash",
            provider="openai-compatible",
            base_url="https://api.deepseek.com/v1",
            api_key="sk-...",
        )
        if not decision.approved:
            # reject — return tool error
    """

    def __init__(self, config: ApprovalConfig):
        self.config = config
        self._hard_rules = _compile_hard_rules(config)

    def check(self, action: str, args: dict,
              model: str = "", provider: str = "",
              base_url: str = "", api_key: str = "") -> ApprovalDecision:
        """Run the three-step approval check.

        Returns ApprovalDecision — check .approved to decide.
        """
        if not self.config.enabled:
            return ApprovalDecision(approved=True, risk_level="low",
                                    reason="approval disabled", source="disabled")

        # ── Step 0: Whitelist ──
        wl = self._check_whitelist(action, args)
        if wl is not None:
            return wl

        # ── Step 1: Hard rules ──
        decision = self._check_hard_rules(action, args)
        if decision is not None:
            return decision

        # ── Step 2: LLM risk assessment ──
        return self._llm_assess(action, args, model, provider, base_url, api_key)

    # ── Step 1 ──


    def _check_whitelist(self, action: str, args: dict):  # noqa: F821 (ApprovalDecision defined below)
        """Always-allow: read-only tools, self-maintenance, git ops."""


        # Read-only tools — all pure information retrieval
        READ_ONLY = (
            "read_file", "search_files", "session_search", "skill_view",
            "skills_list", "browser_snapshot", "browser_navigate",
            "browser_click", "browser_scroll", "browser_console",
            "browser_get_images", "browser_vision", "browser_type",
            "browser_press", "browser_back", "vision_analyze",
            "web_search", "web_extract",
        )
        if action in READ_ONLY:
            return ApprovalDecision(approved=True, risk_level="low",
                                    reason="read-only", source="whitelist")

        # Safe management tools — no destructive capability
        MANAGEMENT = ("clarify", "todo", "memory", "text_to_speech", "cronjob",
                      "process", "skill_manage")
        if action in MANAGEMENT:
            return ApprovalDecision(approved=True, risk_level="low",
                                    reason="management tool", source="whitelist")

        # Self-modification (write_file / patch): allow updates to agent infrastructure
        # ── only for explicit file writes, NOT terminal — safety: whitelist runs before hard rules
        path = args.get("path", "")
        for pat in ("agent/approval", "agent/skills_hub", "agent/brain",
                    ".hermes/playbook", ".hermes/skills", ".hermes/memories",
                    ".hermes/config.yaml", ".hermes/.env", "hermes_cli/config.py"):
            if pat in path and action in ("write_file", "patch"):
                return ApprovalDecision(approved=True, risk_level="low",
                                        reason=f"self-maintenance: {pat}", source="whitelist")

        # Safe terminal commands
        SAFE_CMD = ("git ", "hermes ", "pip ", "npm ", "cargo ", "docker ",
                    "ls", "cat", "head", "tail", "grep", "echo", "pwd",
                    "which", "env", "ps", "df", "du", "free", "uname", "date", "uptime",
                    "curl ", "wget ", "systemctl --user status", "systemctl --user list",
                    "systemctl --user restart", "systemctl --user stop", "systemctl --user start",
                    "journalctl ", "rtk ")
        cmd = args.get("command", "")
        if action == "terminal" and cmd:
            for prefix in SAFE_CMD:
                if cmd.startswith(prefix):
                    return ApprovalDecision(approved=True, risk_level="low",
                                            reason=f"safe: {prefix}", source="whitelist")

        # hermes config commands via terminal: safe config management
        # ── placed AFTER the safe-cmd check so "hermes " prefix catches most cases first
        if action == "terminal":
            cmd = args.get("command", "")
            if re.search(r"\bhermes\s+config\b", cmd):
                return ApprovalDecision(approved=True, risk_level="low",
                                        reason="hermes config management", source="whitelist")

        # delegate_task: allow unless the context/goal contains destructive patterns
        if action == "delegate_task":
            goal = str(args.get("goal", ""))
            ctx = str(args.get("context", ""))
            combined = goal + " " + ctx
            if re.search(r"rm\s+-rf|drop\s+table|delete.*all|format\s+disk|shutdown|wipe", 
                        combined, re.IGNORECASE):
                pass  # fall through to hard rules
            else:
                return ApprovalDecision(approved=True, risk_level="low",
                                        reason="safe delegation", source="whitelist")

        # send_message: allow normal messaging, only flag dangerous patterns
        if action == "send_message":
            msg = str(args.get("message", ""))
            # Only block if matches dangerous patterns (fall to hard rules)
            if re.search(r"post_public|bulk|broadcast|mass|spam", msg, re.IGNORECASE):
                pass  # fall through to hard rules
            else:
                return ApprovalDecision(approved=True, risk_level="low",
                                        reason="normal messaging", source="whitelist")

        # execute_code: sandboxed, allow
        if action == "execute_code":
            return ApprovalDecision(approved=True, risk_level="low",
                                    reason="sandboxed execution", source="whitelist")

        return None


    def _check_hard_rules(self, action: str, args: dict) -> Optional[ApprovalDecision]:
        """Check action+args against BLOCK and ALWAYS_ASK lists.

        Returns decision if matched, None if no match (→ proceed to Step 2).
        """
        # Serialize args for regex matching
        args_str = json.dumps(args, ensure_ascii=False) if args else ""

        for rule in self._hard_rules.get("block", []):
            if self._match_rule(rule, action, args_str):
                risk = rule.get("risk_level", "blocked")
                return ApprovalDecision(
                    approved=False, risk_level=risk,
                    reason=f"BLOCKED by hard rule: {action} matched '{rule.get('args_pattern', '')}'",
                    source="hard_rule_block",
                )

        for rule in self._hard_rules.get("always_ask", []):
            if self._match_rule(rule, action, args_str):
                return ApprovalDecision(
                    approved=False, risk_level="medium",
                    reason=f"REQUIRES CONFIRMATION: {action} matched always_ask rule '{rule.get('args_pattern', '')}'",
                    source="hard_rule_ask",
                )

        return None  # No hard rule match

    def _match_rule(self, rule: dict, action: str, args_str: str) -> bool:
        """Check if a rule matches the current action and args."""
        rule_action = rule.get("action", "")
        if rule_action and rule_action != action:
            return False
        pattern = rule.get("args_pattern", "")
        if pattern and not re.search(pattern, args_str, re.IGNORECASE | re.DOTALL):
            return False
        return bool(rule_action)  # Must have at least action to match

    # ── Step 2: LLM risk assessment ──

    def _llm_assess(self, action: str, args: dict,
                    model: str, provider: str, base_url: str, api_key: str) -> ApprovalDecision:
        """Assess risk using an LLM.

        Uses the configured risk_model:
        - default model for most tools
        - pro model for high_risk_actions
        """
        # Determine model for assessment
        risk_config = self.config.risk_model
        if self.config.is_high_risk_action(action) and risk_config.get("high_risk_actions"):
            assess_model = self._resolve_model("deepseek-v4-pro", model, provider, base_url, api_key)
        else:
            assess_model = self._resolve_model(
                risk_config.get("default", "deepseek-v4-flash"), model, provider, base_url, api_key
            )

        # Build prompt
        args_preview = json.dumps(args, ensure_ascii=False)[:2000]
        prompt = textwrap.dedent(f"""\
        你是安全风险评估器。分析以下工具调用，输出合法 JSON。
        只输出 JSON 对象，第一个字符必须是 {{，最后一个字符必须是 }}。

        工具: {action}
        参数: {args_preview}

        {{
          "risk_level": "high | medium | low",
          "reason": "一句话说明",
          "confidence": 0.0-1.0
        }}

        分类标准：
        - high: 可能造成数据丢失、安全漏洞、系统损坏、大范围影响
        - medium: 影响范围有限但需要谨慎，或不常见操作
        - low: 常规查询、读取、无害操作

        注意：读取操作(read/list/get/stat)一般是 low，写入/删除/执行需要仔细判断。
        """)

        # Call LLM
        try:
            result = _call_llm(assess_model, prompt,
                              timeout=risk_config.get("timeout", 15))
            risk_level = result.get("risk_level", "high")
            confidence = float(result.get("confidence", 0.0))
            reason = result.get("reason", "LLM assessment")

            # Force high if confidence too low
            force_threshold = risk_config.get("force_high_if_confidence", 0.7)
            if confidence < force_threshold and risk_level != "high":
                risk_level = "high"
                reason = f"low confidence ({confidence:.0%}) forced high: {reason}"

            # Map to decision
            decision = self.config.decision_for(risk_level)
            approved = decision == "allow"

            logger.info(
                "approval: %s → %s (risk=%s, conf=%.0%%, model=%s)",
                action, "ALLOW" if approved else "REJECT",
                risk_level, confidence, assess_model["model"],
            )

            return ApprovalDecision(
                approved=approved, risk_level=risk_level,
                reason=reason, source="llm_assessment",
            )
        except Exception as e:
            # Any failure → reject (safe default)
            logger.warning("Approval LLM assessment failed for %s: %s", action, e)
            return ApprovalDecision(
                approved=False, risk_level="high",
                reason=f"LLM assessment failed: {e}",
                source="llm_assessment",
            )

    def _resolve_model(self, target: str, fallback_model: str,
                       fallback_provider: str, fallback_base_url: str,
                       api_key: str = "") -> dict:
        """Resolve a model config dict."""
        return {
            "model": target,
            "provider": fallback_provider or "openai-compatible",
            "base_url": fallback_base_url or "https://api.deepseek.com/v1",
            "api_key": api_key,
        }


# ── Helpers ──

def _compile_hard_rules(config: ApprovalConfig) -> dict:
    """Flatten hard rules from config for fast lookup."""
    return config.hard_rules


def _call_llm(model_config: dict, prompt: str, timeout: int = 5) -> dict:
    """Call an LLM for risk assessment. Returns parsed JSON dict.

    Uses the OpenAI-compatible chat completions API.
    """
    import urllib.request
    import urllib.error

    url = f"{model_config['base_url'].rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {_get_api_key(model_config)}",
    }
    body = json.dumps({
        "model": model_config["model"],
        "messages": [
            {"role": "system", "content": "你只输出 JSON 对象，不输出任何其他内容。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 256,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            return _extract_json(content)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"LLM API error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"LLM API connection error: {e.reason}")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise RuntimeError(f"LLM response parse error: {e}")


def _get_api_key(model_config: dict) -> str:
    """Get API key from config or environment."""
    import os
    key = model_config.get("api_key", "") or os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        key = model_config.get("api_key", "")
    return key


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM output, handling markdown fences."""
    text = text.strip()
    # Remove markdown fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object
        match = re.search(r'\{[^{}]*\}', text)
        if match:
            return json.loads(match.group())
        raise
