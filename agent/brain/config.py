"""Brain configuration — all tuning parameters centralized."""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class Layer0Config:
    max_context_threshold: int = 100000     # tokens — above this → complex
    token_estimate_mode: str = "char_ratio" # "char_ratio" | "tiktoken"


@dataclass
class Layer05Config:
    enabled: bool = True
    ttl_seconds: int = 3600                 # 1 hour
    max_entries: int = 1000


@dataclass
class Layer2Config:
    model: str = "deepseek-v4-flash"
    provider: str = "auto"                 # "auto" = try all available providers
    timeout: int = 5                        # seconds
    temperature: float = 0.0
    max_retries: int = 1
    max_context: int = 16000                # planner's context window
    fallback_model: str = "qwen3.6-flash"   # fallback when primary is circuit-broken
    fallback_provider: str = "dashscope"
    fallback_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"


@dataclass
class AffinityConfig:
    enabled: bool = False
    mode: str = "dynamic"                    # "dynamic" | "sticky"
    min_confidence: float = 0.85
    lockable_routes: List[str] = field(default_factory=lambda: ["coding", "complex", "vision"])
    idle_timeout: int = 1800                # seconds — release after idle (ignored in sticky mode)


@dataclass
class RouteTarget:
    model: str
    max_tokens: int = 4096
    temperature: float = 0.7
    provider: str = ""
    base_url: str = ""
    auto_upgrade_max_tokens: int = 0        # 0 = disabled
    auto_upgrade_max_turns: int = 0
    auto_upgrade_on_truncation: bool = False


@dataclass
class ExecutionConfig:
    routes: dict = field(default_factory=lambda: {
        "simple": RouteTarget(
            model="deepseek-v4-flash",
            max_tokens=4096,
            auto_upgrade_max_tokens=16000,
            auto_upgrade_max_turns=5,
            auto_upgrade_on_truncation=True,
        ),
        "coding": RouteTarget(
            model="deepseek-v4-pro",
            max_tokens=16384,
            temperature=0.3,
        ),
        "complex": RouteTarget(
            model="deepseek-v4-pro",
            max_tokens=24576,
        ),
        "vision": RouteTarget(
            model="qwen3-vl-plus",
            provider="openai-compatible",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            max_tokens=4096,
            temperature=0.3,
        ),
        "doc_extract": RouteTarget(
            model="deepseek-v4-flash",
            max_tokens=8192,
            temperature=0.0,
        ),
    })
    max_reroute_depth: int = 2


@dataclass
class CircuitBreakerConfig:
    threshold: int = 3                      # failures to open
    cooldown: int = 300                     # seconds before half-open probe
    scope: str = "provider+model"           # "provider" | "provider+model"
    provider_threshold: int = 5
    provider_cooldown: int = 600
    state_file: str = "~/.hermes/state/circuit_breakers.json"


@dataclass
class FallbackConfig:
    chains: dict = field(default_factory=lambda: {
        "simple":   ["deepseek-v4-flash", "qwen3.6-flash", "GLM-4.7-Flash"],
        "coding":   ["deepseek-v4-pro", "deepseek-v4-flash", "qwen3.6-plus"],
        "complex":  ["deepseek-v4-pro", "deepseek-v4-flash", "qwen3.6-plus"],
        "vision":   ["qwen3-vl-plus", "gemini-2.5-flash", "deepseek-v4-pro"],
        "doc_extract": ["deepseek-v4-flash", "qwen3.6-flash", "GLM-4.7-Flash"],
    })
    timeout: dict = field(default_factory=lambda: {
        "simple": 10, "coding": 30, "complex": 60, "vision": 30, "doc_extract": 30,
    })
    retry_same_max: int = 1
    retry_backoff_base: float = 1.0
    retry_backoff_max: float = 8.0
    retry_on: List[int] = field(default_factory=lambda: [500, 502, 503])
    no_retry_on: List[int] = field(default_factory=lambda: [400, 401, 403])


@dataclass
class BrainConfig:
    enabled: bool = False
    layer0: Layer0Config = field(default_factory=Layer0Config)
    layer0_5: Layer05Config = field(default_factory=Layer05Config)
    layer2: Layer2Config = field(default_factory=Layer2Config)
    affinity: AffinityConfig = field(default_factory=AffinityConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    fallback: FallbackConfig = field(default_factory=FallbackConfig)
    shadow_mode: bool = False
    trace_log_dir: str = "~/.hermes/logs/brain/"

    @classmethod
    def from_dict(cls, d: dict) -> "BrainConfig":
        """Parse from config.yaml's 'brain' section."""
        if not d:
            return cls()
        c = cls()
        c.enabled = d.get("enabled", False)
        c.shadow_mode = d.get("shadow_mode", False)

        # Layer 0
        l0 = d.get("layer0", {})
        if l0:
            if "max_context_threshold" in l0:
                c.layer0.max_context_threshold = l0["max_context_threshold"]

        # Layer 0.5
        l05 = d.get("layer0_5", {})
        if l05:
            if "enabled" in l05:
                c.layer0_5.enabled = l05["enabled"]
            if "ttl" in l05:
                c.layer0_5.ttl_seconds = l05["ttl"]
            if "max_entries" in l05:
                c.layer0_5.max_entries = l05["max_entries"]

        # Layer 2
        l2 = d.get("layer2", {})
        if l2:
            for k in ("model", "provider", "timeout", "temperature", "max_retries", "max_context",
                      "fallback_model", "fallback_provider", "fallback_base_url"):
                if k in l2:
                    setattr(c.layer2, k, l2[k])

        # Affinity
        aff = d.get("session_affinity", {})
        if aff:
            if "enabled" in aff:
                c.affinity.enabled = aff["enabled"]
            if "min_confidence" in aff:
                c.affinity.min_confidence = aff["min_confidence"]
            if "lockable_routes" in aff:
                c.affinity.lockable_routes = aff["lockable_routes"]
            if "idle_timeout" in aff:
                c.affinity.idle_timeout = aff["idle_timeout"]
            if "mode" in aff:
                c.affinity.mode = aff["mode"]

        # Fallback
        fb = d.get("fallback", {})
        if fb:
            if "chains" in fb:
                c.fallback.chains = fb["chains"]
            if "timeout" in fb:
                c.fallback.timeout = fb["timeout"]

        # Circuit breaker
        cb = d.get("circuit_breaker", {})
        if cb:
            for k in ("threshold", "cooldown", "scope", "provider_threshold", "provider_cooldown"):
                if k in cb:
                    setattr(c.circuit_breaker, k, cb[k])

        # Execution routes
        exec_cfg = d.get("execution", {})
        routes_cfg = exec_cfg.get("routes", {})
        for route_name, rt in routes_cfg.items():
            if route_name in c.execution.routes:
                existing = c.execution.routes[route_name]
                if "model" in rt:
                    existing.model = rt["model"]
                if "max_tokens" in rt:
                    existing.max_tokens = rt["max_tokens"]
                if "temperature" in rt:
                    existing.temperature = rt["temperature"]
                if "provider" in rt:
                    existing.provider = rt["provider"]
                if "base_url" in rt:
                    existing.base_url = rt["base_url"]
                if "auto_upgrade" in rt:
                    au = rt["auto_upgrade"]
                    existing.auto_upgrade_max_tokens = au.get("max_est_tokens", 0)
                    existing.auto_upgrade_max_turns = au.get("max_turns", 0)
                    existing.auto_upgrade_on_truncation = au.get("on_truncation", False)
            else:
                # New route from config
                c.execution.routes[route_name] = RouteTarget(
                    model=rt.get("model", "deepseek-v4-pro"),
                    max_tokens=rt.get("max_tokens", 4096),
                    temperature=rt.get("temperature", 0.7),
                    provider=rt.get("provider", ""),
                    base_url=rt.get("base_url", ""),
                )

        return c
