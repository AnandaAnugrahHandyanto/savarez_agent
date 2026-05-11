# Multi-Layer Intelligent Brain Router — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a multi-layer intelligent model routing system (Brain) that classifies every user query and routes it to the optimal model/provider — Layer 0 preprocessing → Layer 0.5 fingerprint cache → Layer 1 heuristic → Session Affinity → Layer 2 planner → Execution with fallback and circuit breaker. Every layer fails safe.

**Architecture:** New `agent/brain/` module with 11 files. Integration into `run_agent.py` via a single hook call at the start of each turn in `run_conversation()`. Opt-in via `brain.enabled: true` in config — zero risk to existing users.

**Tech Stack:** Python 3.10+, dataclasses, hashlib (SHA256), re, json, openai (planner API), json, time, pathlib, threading (circuit breaker persistence). No new dependencies.

**Principles:** Stability > Cost > Performance > Latency. Every layer fails safe. Never crash the agent.

---

## Task 0: Create module directory and types

**Objective:** Create the `agent/brain/` directory and the shared data types that all layers depend on.

**Files:**
- Create: `agent/brain/__init__.py`
- Create: `agent/brain/types.py`

**Step 1: Write `agent/brain/types.py`**

```python
"""Shared data types for the Brain routing system."""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class RouteDecision:
    """Output from any routing layer. Execution layer fills resolved_model/provider."""
    route: str                          # "simple" | "coding" | "complex" | "vision" | "doc_extract"
    confidence: float                   # 0.0 – 1.0
    source: str                         # "l0_image" | "l05_fingerprint" | "l1_greeting" | "l2_planner" | ...
    resolved_model: Optional[str] = None
    resolved_provider: Optional[str] = None
    resolved_base_url: Optional[str] = None
    resolved_api_key: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.90

    @property
    def is_terminal(self) -> bool:
        """Routes that should NOT be re-evaluated by later layers."""
        return self.route in ("vision", "doc_extract")


@dataclass
class LayerTrace:
    """One entry in the full routing trace for observability."""
    layer: str                          # "l0" | "l05" | "l1" | "affinity" | "l2" | "exec"
    decision: Optional[str] = None      # route or None if pass-through
    confidence: Optional[float] = None
    source: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionAffinityState:
    """Persistent session affinity — locked model for current session."""
    route: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    confidence: float = 0.0
    consecutive_failures: int = 0
    locked_at: float = 0.0


EMPTY_DECISION = RouteDecision("complex", 0.1, "none")
LOCKABLE_ROUTES = frozenset({"coding", "complex", "vision"})
```

**Step 2: Write `agent/brain/__init__.py`**

```python
"""Brain — Multi-layer intelligent model routing for Hermes Agent.

Layers:
  Layer 0:   Preprocessing (multimodal detection, token estimation)
  Layer 0.5: Fingerprint Cache (SHA256 exact match)
  Layer 1:   Heuristic Classifier (regex rules)
  Affinity:  Session Affinity (lock model for ongoing tasks)
  Layer 2:   Lightweight Planner (cheap LLM classifier)
  Execution: Model resolution + fallback chain + circuit breaker

Integration:
  from agent.brain.pipeline import route_message

  decision = route_message(user_input, session, config)
  # decision.resolved_model, .resolved_provider, .resolved_base_url are set
"""

# Re-export public API
from agent.brain.types import RouteDecision, SessionAffinityState, LayerTrace, EMPTY_DECISION
from agent.brain.pipeline import route_message, BrainConfig
```

**Step 3: Verify**

```bash
cd ~/.hermes/hermes-agent && source venv/bin/activate
python -c "from agent.brain import RouteDecision; print(RouteDecision('simple', 0.9, 'test'))"
```

---

## Task 1: Configuration module

**Objective:** Define BrainConfig dataclass with defaults. All tuning parameters centralized.

**Files:**
- Create: `agent/brain/config.py`

**Step 1: Write `agent/brain/config.py`**

```python
"""Brain configuration — all tuning parameters centralized."""

from dataclasses import dataclass, field
from typing import List


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
    provider: str = "deepseek"
    timeout: int = 5                        # seconds
    temperature: float = 0.0
    max_retries: int = 1
    max_context: int = 16000                # planner's context window


@dataclass
class AffinityConfig:
    enabled: bool = False
    min_confidence: float = 0.85
    lockable_routes: List[str] = field(default_factory=lambda: ["coding", "complex", "vision"])
    idle_timeout: int = 1800                # seconds — release after idle


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
        "simple": RouteTarget(model="deepseek-v4-flash", max_tokens=4096,
                              auto_upgrade_max_tokens=16000, auto_upgrade_max_turns=5,
                              auto_upgrade_on_truncation=True),
        "coding": RouteTarget(model="deepseek-v4-pro", max_tokens=16384, temperature=0.3),
        "complex": RouteTarget(model="deepseek-v4-pro", max_tokens=32768),
        "vision": RouteTarget(model="qwen3-vl-plus", provider="openai-compatible",
                              base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                              max_tokens=4096, temperature=0.3),
        "doc_extract": RouteTarget(model="deepseek-v4-flash", max_tokens=8192, temperature=0.0),
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
        "simple":   ["deepseek-v4-flash", "kimi-k2.6", "deepseek-v4-pro"],
        "coding":   ["deepseek-v4-pro", "kimi-k2.6", "deepseek-v4-pro"],
        "complex":  ["deepseek-v4-pro", "kimi-k2.6", "deepseek-v4-pro"],
        "vision":   ["qwen3-vl-plus", "gemini-2.5-flash", "deepseek-v4-pro"],
        "doc_extract": ["deepseek-v4-flash", "kimi-k2.6", "deepseek-v4-pro"],
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
    shadow_mode: bool = False               # log decisions but don't apply them
    trace_log_dir: str = "~/.hermes/logs/brain/"

    @classmethod
    def from_dict(cls, d: dict) -> "BrainConfig":
        """Parse from config.yaml's 'brain' section."""
        # Minimal: just set enabled + override defaults from keys
        c = cls()
        if d:
            c.enabled = d.get("enabled", False)
            c.shadow_mode = d.get("shadow_mode", False)
            # ... nested overrides in later tasks
        return c
```

**Step 2: Verify**

```bash
python -c "from agent.brain.config import BrainConfig; c=BrainConfig(); print(c.enabled, c.execution.routes['simple'].model)"
```

---

## Task 2: Layer 0 — Preprocessing

**Objective:** Implement multimodal detection and token estimation. <2ms, no API calls.

**Files:**
- Create: `agent/brain/layer0.py`

**Step 1: Write failing test**

Create `tests/brain/test_layer0.py`:

```python
import pytest
from agent.brain.layer0 import layer0_preprocess, token_estimate
from agent.brain.types import RouteDecision
from agent.brain.config import BrainConfig


class TestTokenEstimate:
    def test_english(self):
        assert token_estimate("hello world") == 2  # 11/4 ≈ 2

    def test_chinese(self):
        # 你好世界 = 4 CJK chars / 1.5 ≈ 2
        assert token_estimate("你好世界") == 2

    def test_mixed(self):
        text = "hello 你好"
        # 5 english chars / 4 = 1, 2 CJK / 1.5 = 1 → 2
        assert token_estimate(text) == 2

    def test_empty(self):
        assert token_estimate("") == 0


class TestLayer0:
    def test_image_upload_detected(self):
        result = layer0_preprocess(
            "Look at this image ![img](photo.jpg)", [], BrainConfig()
        )
        assert result is not None
        assert result.route == "vision"
        assert result.confidence == 0.95

    def test_no_special_input_returns_none(self):
        result = layer0_preprocess("Hello, how are you?", [], BrainConfig())
        assert result is None  # Pass through to next layer

    def test_long_context_detected(self):
        long_text = "word " * 50000  # ~100k tokens
        result = layer0_preprocess(long_text, [], BrainConfig())
        assert result is not None
        assert result.route == "complex"
```

**Step 2: Run test failure**

```bash
python -m pytest tests/brain/test_layer0.py -v
# Expected: FAIL — module not found
```

**Step 3: Write `agent/brain/layer0.py`**

```python
"""Layer 0: Preprocessing — multimodal detection, token estimation. <2ms, no API."""

from agent.brain.types import RouteDecision
from agent.brain.config import BrainConfig
from typing import List, Dict, Any, Optional

# Image indicator patterns
IMAGE_PATTERNS = [
    r'!\[.*?\]\(.*?\.(png|jpg|jpeg|gif|webp|bmp)(\?.*)?\)',
    r'https?://[^\s]+\.(png|jpg|jpeg|gif|webp)(\?[^\s]*)?',
    r'data:image/',
]

# Document indicator patterns
DOCUMENT_PATTERNS = [
    r'!\[.*?\]\(.*?\.(pdf|docx?|pptx?|xlsx?|txt|csv)(\?.*)?\)',
    r'https?://[^\s]+\.(pdf|docx?|pptx?)(\?[^\s]*)?',
]


def token_estimate(text: str) -> int:
    """Fast token estimation using character ratios. <0.1ms."""
    if not text:
        return 0
    cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff')
    other = len(text) - cjk
    return max(1, int(cjk / 1.5 + other / 4))


def _has_image(text: str) -> bool:
    import re
    return any(re.search(p, text) for p in IMAGE_PATTERNS)


def _has_document(text: str) -> bool:
    import re
    return any(re.search(p, text) for p in DOCUMENT_PATTERNS)


def layer0_preprocess(
    user_input: str,
    history: List[Dict[str, Any]],
    config: BrainConfig,
) -> Optional[RouteDecision]:
    """
    Layer 0: Preprocessing. Must complete in <2ms. No API calls.
    Returns RouteDecision for early-exit signals (image, document, long-context).
    Returns None to pass through to Layer 0.5.
    """

    # 1. Multimodal detection — strong signal, exit early
    if _has_image(user_input):
        return RouteDecision(
            route="vision", confidence=0.95, source="l0_image",
            metadata={"check_code_context": True}
        )

    if _has_document(user_input):
        return RouteDecision(
            route="doc_extract", confidence=0.95, source="l0_document",
            metadata={"reroute_after_extract": True}
        )

    # 2. Lightweight token estimation
    input_tokens = token_estimate(user_input)
    history_text = " ".join(
        m.get("content", "") for m in history
        if isinstance(m.get("content"), str)
    )
    history_tokens = token_estimate(history_text)
    total_estimated = input_tokens + history_tokens

    # 3. Long-context gate
    if total_estimated > config.layer0.max_context_threshold:
        return RouteDecision(
            route="complex", confidence=0.85, source="l0_long_context",
            metadata={"estimated_tokens": total_estimated}
        )

    # 4. Attach metadata for downstream layers
    return None  # Continue to Layer 0.5
```

**Step 4: Run tests**

```bash
python -m pytest tests/brain/test_layer0.py -v
```

**Step 5: Commit**

```bash
git add agent/brain/__init__.py agent/brain/types.py agent/brain/config.py agent/brain/layer0.py tests/brain/test_layer0.py
git commit -m "feat: add Brain Layer 0 — preprocessing (multimodal detection, token estimation)"
```

---

## Task 3: Layer 0.5 — Fingerprint Cache

**Objective:** SHA256 exact-match cache. Reuses routing decisions for semantically identical messages. LRU eviction, TTL-based expiry.

**Files:**
- Create: `agent/brain/layer0_5.py`

**Step 1: Write failing test**

Append to `tests/brain/test_layer0.py`:

```python
from agent.brain.layer0_5 import FingerprintCache
from agent.brain.types import RouteDecision


class TestFingerprintCache:
    def test_cache_hit(self):
        cache = FingerprintCache(max_entries=10, ttl=3600)
        decision = RouteDecision("simple", 0.95, "test")
        cache.set("Hello world", decision)
        cached = cache.get("Hello world")
        assert cached is not None
        assert cached.route == "simple"

    def test_cache_normalization(self):
        cache = FingerprintCache(max_entries=10, ttl=3600)
        decision = RouteDecision("simple", 0.95, "test")
        cache.set("  Hello   World  ", decision)
        assert cache.get("hello world") is not None
        assert cache.get("Hello World") is not None

    def test_cache_miss(self):
        cache = FingerprintCache(max_entries=10, ttl=3600)
        assert cache.get("nonexistent") is None

    def test_cache_ttl_expiry(self):
        cache = FingerprintCache(max_entries=10, ttl=-1)  # already expired
        cache.set("test", RouteDecision("simple", 0.95, "test"))
        assert cache.get("test") is None

    def test_cache_lru_eviction(self):
        cache = FingerprintCache(max_entries=2, ttl=3600)
        cache.set("a", RouteDecision("simple", 0.9, "test"))
        cache.set("b", RouteDecision("coding", 0.9, "test"))
        cache.set("c", RouteDecision("complex", 0.9, "test"))
        assert cache.get("a") is None  # evicted
        assert cache.get("b") is not None
        assert cache.get("c") is not None
```

**Step 2: Write `agent/brain/layer0_5.py`**

```python
"""Layer 0.5: Fingerprint Cache — SHA256 exact-match cache for routing decisions."""

import hashlib
import time
import re
import threading
from typing import Optional
from agent.brain.types import RouteDecision


def _normalize(text: str) -> str:
    """Normalize text for fingerprinting: lowercase, collapse whitespace, strip."""
    return re.sub(r'\s+', ' ', text.lower().strip())


def _fingerprint(text: str) -> str:
    """SHA256 fingerprint of normalized text."""
    return hashlib.sha256(_normalize(text).encode('utf-8')).hexdigest()


class FingerprintCache:
    """LRU cache keyed by SHA256 of normalized input. Thread-safe."""

    def __init__(self, max_entries: int = 1000, ttl: int = 3600):
        self._max = max_entries
        self._ttl = ttl
        self._data: dict = {}           # fp → (RouteDecision, timestamp, access_time)
        self._lock = threading.Lock()

    def get(self, text: str) -> Optional[RouteDecision]:
        fp = _fingerprint(text)
        with self._lock:
            entry = self._data.get(fp)
            if entry is None:
                return None
            decision, stored_at, _ = entry
            if self._ttl > 0 and time.time() - stored_at > self._ttl:
                del self._data[fp]
                return None
            # Update access time for LRU
            self._data[fp] = (decision, stored_at, time.time())
            return decision

    def set(self, text: str, decision: RouteDecision):
        fp = _fingerprint(text)
        now = time.time()
        with self._lock:
            # Evict if at capacity
            if len(self._data) >= self._max and fp not in self._data:
                # Remove least-recently-used
                oldest_fp = min(self._data, key=lambda k: self._data[k][2])
                del self._data[oldest_fp]
            self._data[fp] = (decision, now, now)

    def clear(self):
        with self._lock:
            self._data.clear()

    def __len__(self):
        with self._lock:
            return len(self._data)
```

**Step 3: Run tests**

```bash
python -m pytest tests/brain/test_layer0.py -v
```

**Step 4: Commit**

```bash
git add agent/brain/layer0_5.py tests/brain/test_layer0.py
git commit -m "feat: add Brain Layer 0.5 — fingerprint cache"
```

---

## Task 4: Layer 1 — Heuristic Classifier

**Objective:** Regex/keyword classifier. <5ms, no API. High-precision rules with fail-safe ordering.

**Files:**
- Create: `agent/brain/layer1.py`

**Step 1: Write failing test**

Create `tests/brain/test_layer1.py`:

```python
import pytest
from agent.brain.layer1 import layer1_heuristic, is_greeting, is_chitchat, is_translation_request
from agent.brain.types import RouteDecision


class TestDetectors:
    def test_greeting_true(self):
        assert is_greeting("你好") is True
        assert is_greeting("hi there") is True
        assert is_greeting("hello") is True

    def test_greeting_false(self):
        assert is_greeting("你好，帮我写个函数") is False
        assert is_greeting("hello world, help me code") is False

    def test_chitchat_true(self):
        assert is_chitchat("好的") is True
        assert is_chitchat("ok") is True
        assert is_chitchat("知道了，谢谢") is True

    def test_translation(self):
        assert is_translation_request("翻译这段") is True
        assert is_translation_request("translate this") is True
        assert is_translation_request("把这段话翻成英文") is True


class TestLayer1:
    def test_greeting_first_turn(self):
        result = layer1_heuristic("你好", [], turns=1, est_tokens=5)
        assert result is not None
        assert result.route == "simple"
        assert result.confidence == 1.0
        assert result.source == "l1_greeting"

    def test_greeting_not_first_turn(self):
        # Greeting in turn 3 is not a strong signal
        result = layer1_heuristic("你好", [], turns=3, est_tokens=5)
        assert result is None or result.source != "l1_greeting"

    def test_code_detection(self):
        result = layer1_heuristic("写个函数 import numpy as np def main():", [], turns=2, est_tokens=30)
        assert result is not None
        assert result.route == "coding"

    def test_simple_intent(self):
        result = layer1_heuristic("帮我查一下天气", [], turns=2, est_tokens=20)
        assert result is not None
        assert result.route == "simple"

    def test_code_before_simple_keyword(self):
        # "帮我查一下 import 怎么用" — should NOT be routed to coding
        result = layer1_heuristic("帮我查一下 import 怎么用", [], turns=2, est_tokens=25)
        # code_score should be < 2 (only 'import' keyword, no code block/extension)
        assert result is None or result.route != "coding"

    def test_no_match_returns_none(self):
        result = layer1_heuristic("中等长度的复杂问题需要多步推理分析", [], turns=4, est_tokens=120)
        assert result is None  # Escalate to Layer 2
```

**Step 2: Write `agent/brain/layer1.py`**

```python
"""Layer 1: Heuristic fast classifier. <5ms, no API calls."""

import re
from typing import List, Dict, Any, Optional
from agent.brain.types import RouteDecision


# === Detectors ===

_GREETING_PATTERNS = [
    r'^(你好|您好|hi|hey|hello|哈喽|嗨|good\s*(morning|afternoon|evening)|早上好|晚上好|下午好)[\s!！。.]*$',
]

_CHITCHAT_PATTERNS = [
    r'^(好的|ok|知道了|thanks|谢谢|thank you|got it|明白了|收到|嗯嗯|哦哦|好嘞|没问题)[\s!！。.]*$',
]

_TRANSLATION_PATTERNS = [
    r'(翻译|translate|翻成|译成|用.*说|转成.*文)',
]

_CODE_STRONG = re.compile(
    r'(```|`[^`]+`|\.py\b|\.js\b|\.ts\b|\.rs\b|\.go\b|'
    r'\bimport\s+\w+\b|\bfrom\s+\w+\s+import\b|'
    r'\bdef\s+\w+\s*\(|\bclass\s+\w+[:\(]|'
    r'\bfunc\s+\w+\s*\(|\basync\s+def\b|\bawait\s+\w+|'
    r'\bSELECT\s+.*\bFROM\b|\bgit\s+(commit|push|pull|clone|rebase)\b|'
    r'\bdocker\s+(run|build|compose)\b)'
)

_CODE_WEAK_KEYWORDS = ["debug", "报错", "bug", "实现", "写个脚本", "修复"]
_CODE_BLOCK_KEYWORDS = ["代码", "code", "函数", "function", "算法", "algorithm"]

_SIMPLE_INTENT_KEYWORDS = [
    "翻译", "总结一下", "是什么", "怎么读", "几个字", "帮我查",
    "解释", "定义", "意思", "含义", "有什么区别",
]

_CODE_NEGATIVE_CONTEXT = [
    "帮我查", "怎么用", "是什么意思", "介绍一下", "解释一下",
]


def is_greeting(text: str) -> bool:
    text = text.strip().lower()
    return len(text) < 30 and any(re.match(p, text) for p in _GREETING_PATTERNS)


def is_chitchat(text: str) -> bool:
    text = text.strip().lower()
    return len(text) < 20 and any(re.match(p, text) for p in _CHITCHAT_PATTERNS)


def is_translation_request(text: str) -> bool:
    return bool(re.search('|'.join(_TRANSLATION_PATTERNS), text, re.IGNORECASE))


def _has_negative_context(text: str) -> bool:
    """Check if code keywords appear in non-coding context."""
    return any(kw in text for kw in _CODE_NEGATIVE_CONTEXT)


def compute_code_score(text: str) -> int:
    """Weighted code signal scoring. Strong=2, weak=1, blocks=1."""
    score = 0
    # Strong signals (2 points each)
    if bool(re.search(r'```', text)):
        score += 2
    if bool(re.search(r'`[^`]+`', text)):
        score += 1
    if bool(re.search(r'\.(py|js|ts|rs|go|java|rb|sh)\b', text)):
        score += 2
    if bool(_CODE_STRONG.search(text)):
        score += 2
    # Weak signals (1 point each)
    if any(kw in text.lower() for kw in _CODE_WEAK_KEYWORDS):
        score += 1
    if any(kw in text.lower() for kw in _CODE_BLOCK_KEYWORDS):
        score += 1
    return score


def has_simple_intent(text: str) -> bool:
    return any(kw in text for kw in _SIMPLE_INTENT_KEYWORDS)


def layer1_heuristic(
    user_input: str,
    history: List[Dict[str, Any]],
    turns: int = 0,
    est_tokens: int = 0,
) -> Optional[RouteDecision]:
    """
    Layer 1: Heuristic classifier. Ordered by precision (highest first).
    Returns RouteDecision for high-confidence matches, None to escalate to Layer 2.
    """

    # Rule 1: Greeting (first turn only, high precision)
    if is_greeting(user_input) and turns <= 1:
        return RouteDecision("simple", confidence=1.0, source="l1_greeting")

    # Rule 2: Chitchat / acknowledgment
    if is_chitchat(user_input):
        return RouteDecision("simple", confidence=0.98, source="l1_chitchat")

    # Rule 3: Explicit translation request
    if is_translation_request(user_input):
        return RouteDecision("simple", confidence=0.95, source="l1_translation")

    # Rule 4: Very short, early turn, non-technical
    if est_tokens < 60 and turns <= 2 and not compute_code_score(user_input):
        return RouteDecision("simple", confidence=0.95, source="l1_short")

    # Rule 5: Code detection (weighted scoring)
    # Check negative context first to avoid false routing
    if not _has_negative_context(user_input):
        code_score = compute_code_score(user_input)
        if code_score >= 2:
            return RouteDecision("coding", confidence=0.90, source="l1_code")

    # Rule 6: Simple-intent keywords (after code exclusion)
    if has_simple_intent(user_input) and est_tokens < 100:
        return RouteDecision("simple", confidence=0.85, source="l1_simple_intent")

    return None
```

**Step 3: Run tests**

```bash
python -m pytest tests/brain/test_layer1.py -v
```

**Step 4: Commit**

```bash
git add agent/brain/layer1.py tests/brain/test_layer1.py
git commit -m "feat: add Brain Layer 1 — heuristic classifier"
```

---

## Task 5: Layer 2 — Lightweight Planner

**Objective:** Cheap LLM (deepseek-v4-flash) for classification when L1 misses. 5s timeout, 1 retry, structured JSON output with fail-safe.

**Files:**
- Create: `agent/brain/layer2.py`

**Step 1: Write `agent/brain/layer2.py`**

```python
"""Layer 2: Lightweight Planner — cheap LLM classifier. ~500ms, 5s timeout."""

import json
import re
import time
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI

from agent.brain.types import RouteDecision
from agent.brain.config import BrainConfig

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """你是一个路由分析器。分析用户输入，输出合法 JSON。
只输出 JSON 对象，第一个字符必须是 {，最后一个字符必须是 }。

{
  "task_type": "simple|coding|complex",
  "confidence": 0.0-1.0,
  "reason": "一句话理由"
}

分类标准：
- simple: 翻译、查资料、简单解释、闲聊、确认
- coding: 写代码、调试、代码审查、技术实现
- complex: 长上下文、多步推理、需要多个工具链、深度分析
"""


def _extract_json(raw: str) -> Optional[dict]:
    """Robust JSON extraction from LLM output."""
    if not raw or not raw.strip():
        return None

    # Try direct parse
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    cleaned = raw.strip()
    for prefix in ("```json", "```"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    # Try again after cleaning
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Extract first { ... } block
    match = re.search(r'\{[^{}]*\}', cleaned)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Repair common issues: trailing commas, unquoted keys
    repaired = re.sub(r',\s*}', '}', cleaned)
    repaired = re.sub(r',\s*]', ']', repaired)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    return None


def _trim_history(
    history: List[Dict[str, Any]],
    max_tokens: int = 14000,
) -> List[Dict[str, Any]]:
    """Trim history to fit planner's context window. Keep most recent."""
    if not history:
        return []
    result = []
    total = 0
    for msg in reversed(history):
        content = msg.get("content", "")
        if isinstance(content, str):
            est = max(1, len(content) // 4)
        else:
            est = 50  # rough estimate for non-string content
        if total + est > max_tokens:
            break
        result.insert(0, msg)
        total += est
    return result


def layer2_planner(
    user_input: str,
    history: List[Dict[str, Any]],
    config: BrainConfig,
    l1_hint: Optional[RouteDecision] = None,
) -> RouteDecision:
    """
    Layer 2: Lightweight planner. Returns RouteDecision. Never raises.
    """
    cfg = config.layer2
    trimmed_history = _trim_history(history, cfg.max_context - 2000)

    # Build context
    context_parts = []
    if l1_hint:
        context_parts.append(f"Layer 1 hint: {l1_hint.route} (confidence: {l1_hint.confidence})")
    context_str = "\n".join(context_parts) if context_parts else ""

    user_message = user_input
    if context_str:
        user_message = f"[Context: {context_str}]\n\nUser: {user_input}"

    messages = [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
    ]
    if trimmed_history:
        messages.extend(trimmed_history)
    messages.append({"role": "user", "content": user_message})

    for attempt in range(cfg.max_retries + 1):
        try:
            # Use the existing credential resolution from run_agent
            # For standalone test, create a simple client
            client = OpenAI(
                api_key="placeholder",  # Will be overridden by resolve_provider_client
                base_url="https://api.deepseek.com/v1",
                timeout=cfg.timeout,
            )

            response = client.chat.completions.create(
                model=cfg.model,
                messages=messages,
                max_tokens=200,
                temperature=cfg.temperature,
            )

            raw = response.choices[0].message.content or ""
            scores = _extract_json(raw)

            if scores is None:
                if attempt < cfg.max_retries:
                    messages.append({"role": "user", "content": "OUTPUT VALID JSON ONLY. No markdown, no prefix, just { ... }."})
                    continue
                return RouteDecision("complex", 0.2, "l2_parse_failure")

            task_type = scores.get("task_type", "complex")
            confidence = scores.get("confidence", 0.5)

            if task_type not in ("simple", "coding", "complex"):
                task_type = "complex"

            if confidence < 0.60:
                return RouteDecision("complex", confidence, "l2_low_confidence")

            return RouteDecision(
                task_type, confidence, "l2_planner",
                metadata={"reason": scores.get("reason", ""), "attempts": attempt + 1}
            )

        except Exception as e:
            logger.warning("Layer 2 planner attempt %d failed: %s", attempt + 1, e)
            if attempt < cfg.max_retries:
                time.sleep(0.5)
                continue
            return RouteDecision("complex", 0.2, "l2_error",
                                metadata={"error": str(e)[:200]})

    return RouteDecision("complex", 0.1, "l2_exhausted")
```

**Step 2: Verify basic parsing**

```bash
python -c "
from agent.brain.layer2 import _extract_json
assert _extract_json('{\"task_type\": \"simple\", \"confidence\": 0.9, \"reason\": \"test\"}')['task_type'] == 'simple'
assert _extract_json('\`\`\`json\n{\"task_type\": \"coding\", \"confidence\": 0.8, \"reason\": \"code\"}\n\`\`\`')['task_type'] == 'coding'
print('JSON extraction tests passed')
"
```

**Step 3: Commit**

```bash
git add agent/brain/layer2.py
git commit -m "feat: add Brain Layer 2 — lightweight planner"
```

---

## Task 6: Session Affinity

**Objective:** Lock model for ongoing tasks. Establish on first high-confidence non-simple route. Release on task conflict, idle timeout, or consecutive failures.

**Files:**
- Create: `agent/brain/affinity.py`

**Step 1: Write `agent/brain/affinity.py`**

```python
"""Session Affinity — lock model for ongoing task types."""

import time
import logging
from typing import Optional, Dict, Any

from agent.brain.types import RouteDecision, SessionAffinityState, LOCKABLE_ROUTES
from agent.brain.config import AffinityConfig

logger = logging.getLogger(__name__)


def check_affinity(
    affinity_state: Optional[SessionAffinityState],
    l1_decision: Optional[RouteDecision],
    config: AffinityConfig,
) -> Optional[RouteDecision]:
    """
    Check if session affinity should override routing.
    Called between Layer 1 and Layer 2.

    Returns: RouteDecision to use (skipping L2), or None to continue to L2.
    """
    if not config.enabled or affinity_state is None or not affinity_state.route:
        return None

    # Check: idle timeout release
    idle = time.time() - affinity_state.locked_at
    if config.idle_timeout > 0 and idle > config.idle_timeout:
        logger.debug("Affinity released: idle timeout (%.0fs)", idle)
        return None  # Signal to caller to clear affinity

    # Check: L1 conflict with high confidence
    if l1_decision and l1_decision.confidence >= 0.95:
        if l1_decision.route != affinity_state.route:
            logger.debug("Affinity released: L1 conflict (%s ≠ %s, conf=%.2f)",
                        l1_decision.route, affinity_state.route, l1_decision.confidence)
            return None  # Signal to clear affinity and reroute

    # Apply: reuse affinity model for same route type
    return RouteDecision(
        route=affinity_state.route,
        confidence=affinity_state.confidence,
        source="affinity_reuse",
        resolved_model=affinity_state.model,
        resolved_provider=affinity_state.provider,
        resolved_base_url=affinity_state.base_url,
        resolved_api_key=affinity_state.api_key,
    )


def establish_affinity(
    state: Optional[SessionAffinityState],
    decision: RouteDecision,
    config: AffinityConfig,
) -> Optional[SessionAffinityState]:
    """
    Attempt to establish session affinity after Layer 2 decision.
    Called after Layer 2.

    Returns new SessionAffinityState if locked, None otherwise.
    """
    if not config.enabled:
        return None

    if decision.route not in LOCKABLE_ROUTES:
        return None

    if decision.confidence < config.min_confidence:
        return None

    # Don't re-lock if already locked to same route
    if state and state.route == decision.route:
        return state

    return SessionAffinityState(
        route=decision.route,
        model=decision.resolved_model or "",
        provider=decision.resolved_provider or "",
        base_url=decision.resolved_base_url or "",
        api_key=decision.resolved_api_key or "",
        confidence=decision.confidence,
        locked_at=time.time(),
    )


def record_affinity_failure(state: Optional[SessionAffinityState]) -> bool:
    """
    Record a failure on the affinity-locked model.
    Returns True if affinity should be released (2+ consecutive failures).
    """
    if state is None or not state.route:
        return False
    state.consecutive_failures += 1
    if state.consecutive_failures >= 2:
        logger.warning("Affinity released: %d consecutive failures on %s",
                      state.consecutive_failures, state.model)
        return True
    return False


def record_affinity_success(state: Optional[SessionAffinityState]):
    """Reset failure counter on success."""
    if state:
        state.consecutive_failures = 0
```

**Step 2: Commit**

```bash
git add agent/brain/affinity.py
git commit -m "feat: add Brain Session Affinity"
```

---

## Task 7: Circuit Breaker

**Objective:** Persistent circuit breaker. Provider-level + model-level. JSON state file for cross-restart durability.

**Files:**
- Create: `agent/brain/circuit_breaker.py`

**Step 1: Write `agent/brain/circuit_breaker.py`**

```python
"""Circuit Breaker — persistent failure-aware model gating."""

import json
import os
import threading
import time
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, field, asdict

from agent.brain.config import CircuitBreakerConfig
from hermes_constants import get_hermes_home

@dataclass
class BreakerState:
    state: str = "closed"          # "closed" | "open" | "half_open"
    failure_count: int = 0
    opened_at: float = 0.0
    cooldown_until: float = 0.0
    last_failure: float = 0.0


class CircuitBreaker:
    """
    Persistent circuit breaker with provider-level and model-level scoping.
    State survives gateway restarts via JSON file.
    """

    def __init__(self, config: CircuitBreakerConfig):
        self._cfg = config
        self._state_file = Path(config.state_file.replace("~", str(Path.home())))
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._model_states: Dict[str, BreakerState] = {}  # "provider:model" → state
        self._provider_states: Dict[str, BreakerState] = {}  # "provider" → state
        self._lock = threading.Lock()
        self._load()

    def _key(self, provider: str, model: str = "") -> str:
        return f"{provider}:{model}" if model else provider

    def is_open(self, provider: str, model: str = "") -> bool:
        """Check if circuit is open for a model or provider."""
        with self._lock:
            # Check provider-level first
            prov_state = self._provider_states.get(provider)
            if prov_state and self._is_open_local(prov_state):
                return True

            if model:
                mkey = self._key(provider, model)
                model_state = self._model_states.get(mkey)
                if model_state and self._is_open_local(model_state):
                    return True

        return False

    def _is_open_local(self, bs: BreakerState) -> bool:
        if bs.state == "closed":
            return False
        if bs.state == "open":
            if time.time() >= bs.cooldown_until:
                bs.state = "half_open"
                self._save()
                return False
            return True
        # half_open: allow probe requests
        return False

    def record_failure(self, provider: str, model: str = ""):
        """Record a failure. May open the circuit."""
        now = time.time()
        with self._lock:
            # Model-level
            if model:
                mkey = self._key(provider, model)
                ms = self._model_states.setdefault(mkey, BreakerState())
                ms.failure_count += 1
                ms.last_failure = now
                if ms.failure_count >= self._cfg.threshold:
                    ms.state = "open"
                    ms.opened_at = now
                    ms.cooldown_until = now + self._cfg.cooldown

            # Provider-level
            ps = self._provider_states.setdefault(provider, BreakerState())
            ps.failure_count += 1
            ps.last_failure = now
            if ps.failure_count >= self._cfg.provider_threshold:
                ps.state = "open"
                ps.opened_at = now
                ps.cooldown_until = now + self._cfg.provider_cooldown

            self._save()

    def record_success(self, provider: str, model: str = ""):
        """Record a success. Resets the breaker if half-open."""
        with self._lock:
            if model:
                mkey = self._key(provider, model)
                ms = self._model_states.get(mkey)
                if ms and ms.state == "half_open":
                    ms.state = "closed"
                    ms.failure_count = 0

            ps = self._provider_states.get(provider)
            if ps and ps.state == "half_open":
                ps.state = "closed"
                ps.failure_count = 0

            self._save()

    def _save(self):
        try:
            data = {
                "models": {k: asdict(v) for k, v in self._model_states.items()},
                "providers": {k: asdict(v) for k, v in self._provider_states.items()},
            }
            with open(self._state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass  # Non-critical — will just lose state on restart

    def _load(self):
        if not self._state_file.exists():
            return
        try:
            with open(self._state_file) as f:
                data = json.load(f)
            for k, v in data.get("models", {}).items():
                self._model_states[k] = BreakerState(**v)
            for k, v in data.get("providers", {}).items():
                self._provider_states[k] = BreakerState(**v)
        except Exception:
            pass
```

**Step 2: Commit**

```bash
git add agent/brain/circuit_breaker.py
git commit -m "feat: add Brain Circuit Breaker"
```

---

## Task 8: Execution Layer + Fallback

**Objective:** Model resolution, route→model mapping, fallback chain execution, guard logic (auto-upgrade).

**Files:**
- Create: `agent/brain/execution.py`

**Step 1: Write `agent/brain/execution.py`**

```python
"""Execution Layer — model resolution + fallback chain."""

import logging
from typing import Dict, Any, Optional

from agent.brain.types import RouteDecision
from agent.brain.config import BrainConfig, RouteTarget
from agent.brain.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

# Guard conditions for simple route auto-upgrade
GUARD_MAX_EST_TOKENS = "max_est_tokens"
GUARD_MAX_TURNS = "max_turns"
GUARD_ON_TRUNCATION = "on_truncation"


def resolve_model(
    decision: RouteDecision,
    config: BrainConfig,
    circuit_breaker: CircuitBreaker,
    affinity_model: Optional[str] = None,
    estimated_tokens: int = 0,
    session_turns: int = 0,
) -> RouteDecision:
    """
    Resolve a RouteDecision to a concrete model/provider.

    Returns: RouteDecision with resolved_model, resolved_provider, resolved_base_url filled in.
    """
    route = decision.route
    if route not in config.execution.routes:
        logger.warning("Unknown route '%s', falling back to complex", route)
        route = "complex"

    target = config.execution.routes[route]

    # Auto-upgrade guards (simple → complex)
    if route == "simple" and _should_upgrade(target, estimated_tokens, session_turns):
        logger.debug("Auto-upgrade: simple → complex (tokens=%d, turns=%d)",
                    estimated_tokens, session_turns)
        target = config.execution.routes.get("complex", target)
        decision.route = "complex"
        decision.metadata["auto_upgraded"] = True

    # Check circuit breaker against chain
    chain = config.fallback.chains.get(route, [target.model])
    selected = _select_from_chain(chain, circuit_breaker, target.provider)

    decision.resolved_model = selected
    decision.resolved_provider = target.provider or ""
    decision.resolved_base_url = target.base_url or ""

    return decision


def _should_upgrade(target: RouteTarget, estimated_tokens: int, session_turns: int) -> bool:
    if target.auto_upgrade_max_tokens > 0 and estimated_tokens > target.auto_upgrade_max_tokens:
        return True
    if target.auto_upgrade_max_turns > 0 and session_turns > target.auto_upgrade_max_turns:
        return True
    return False


def _select_from_chain(
    chain: list,
    cb: CircuitBreaker,
    provider: str = "",
) -> str:
    """Select first available model from fallback chain, respecting circuit breaker."""
    for model in chain:
        if not cb.is_open(provider, model):
            return model
    return chain[-1]  # Last resort if all are open


def resolve_fallback_chain(
    route: str,
    config: BrainConfig,
) -> list:
    """Return ordered fallback chain for a route."""
    return config.fallback.chains.get(route, ["deepseek-v4-pro"])


def get_route_timeout(route: str, config: BrainConfig) -> int:
    """Return timeout in seconds for a given route."""
    return config.fallback.timeout.get(route, 30)
```

**Step 2: Commit**

```bash
git add agent/brain/execution.py
git commit -m "feat: add Brain Execution Layer + Fallback resolution"
```

---

## Task 9: Trace Logging

**Objective:** Record full routing trace per request for observability.

**Files:**
- Create: `agent/brain/logging.py`

**Step 1: Write `agent/brain/logging.py`**

```python
"""Brain trace logging — observability for routing decisions."""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List
from agent.brain.types import LayerTrace


class BrainTraceLogger:
    """Async-safe routing trace logger to JSONL files."""

    def __init__(self, log_dir: str = "~/.hermes/logs/brain/"):
        self._dir = Path(log_dir.replace("~", str(Path.home())))
        self._dir.mkdir(parents=True, exist_ok=True)
        self._today = datetime.now().strftime("%Y%m%d")
        self._path = self._dir / f"routing_trace_{self._today}.jsonl"

    def log(self, session_id: str, traces: List[LayerTrace], outcome: str = "success"):
        """Write a trace entry."""
        entry = {
            "ts": datetime.now().isoformat(),
            "session_id": session_id,
            "outcome": outcome,
            "layers": [
                {
                    "layer": t.layer,
                    "decision": t.decision,
                    "confidence": t.confidence,
                    "source": t.source,
                    "meta": t.meta,
                }
                for t in traces
            ],
        }
        try:
            with open(self._path, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def log_fallback(self, route: str, model: str, reason: str, success: bool):
        """Log a fallback event."""
        entry = {
            "ts": datetime.now().isoformat(),
            "event": "fallback",
            "route": route,
            "model": model,
            "reason": reason,
            "success": success,
        }
        try:
            fpath = self._dir / f"fallbacks_{self._today}.jsonl"
            with open(fpath, "a") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
```

**Step 2: Commit**

```bash
git add agent/brain/logging.py
git commit -m "feat: add Brain trace logging"
```

---

## Task 10: Pipeline Orchestrator

**Objective:** Wire all layers together. The `route_message()` function is the single entry point.

**Files:**
- Create: `agent/brain/pipeline.py`

**Step 1: Write `agent/brain/pipeline.py`**

```python
"""Brain Pipeline — orchestrates all routing layers."""

import time
import logging
from typing import List, Dict, Any, Optional

from agent.brain.types import (
    RouteDecision, LayerTrace, SessionAffinityState, EMPTY_DECISION
)
from agent.brain.config import BrainConfig
from agent.brain.layer0 import layer0_preprocess
from agent.brain.layer0_5 import FingerprintCache
from agent.brain.layer1 import layer1_heuristic
from agent.brain.layer2 import layer2_planner
from agent.brain.affinity import (
    check_affinity, establish_affinity,
    record_affinity_failure, record_affinity_success,
)
from agent.brain.circuit_breaker import CircuitBreaker
from agent.brain.execution import resolve_model, get_route_timeout
from agent.brain.logging import BrainTraceLogger

logger = logging.getLogger(__name__)

# Global fingerprint cache (shared across sessions)
_fingerprint_cache = FingerprintCache(max_entries=1000, ttl=3600)
_trace_logger = BrainTraceLogger()


def _count_turns(history: List[Dict[str, Any]]) -> int:
    """Count user turns in conversation history."""
    return sum(1 for m in history if m.get("role") == "user")


def _concat_history_text(history: List[Dict[str, Any]]) -> str:
    """Extract text content from history messages."""
    parts = []
    for m in history:
        content = m.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
    return " ".join(parts)


def route_message(
    user_input: str,
    history: List[Dict[str, Any]],
    config: BrainConfig,
    affinity_state: Optional[SessionAffinityState] = None,
) -> RouteDecision:
    """
    Multi-layer intelligent routing pipeline.

    Args:
        user_input: The user's message.
        history: Conversation history (OpenAI-format messages).
        config: Brain configuration.
        affinity_state: Current session affinity state (or None).

    Returns:
        RouteDecision with resolved_model/provider filled in.
    """
    traces: List[LayerTrace] = []
    turns = _count_turns(history)
    est_tokens = 0

    if not config.enabled:
        return EMPTY_DECISION

    # ═══════════════════════════════════════
    # Layer 0: Preprocessing
    # ═══════════════════════════════════════
    try:
        l0 = layer0_preprocess(user_input, history, config)
        if l0 and l0.is_terminal:
            traces.append(LayerTrace("l0", l0.route, l0.confidence, l0.source))
            decision = resolve_model(l0, config, CircuitBreaker(config.circuit_breaker))
            _trace_logger.log("", traces)  # no session_id yet
            return decision
        if l0:
            traces.append(LayerTrace("l0", l0.route, l0.confidence, l0.source))
            est_tokens = l0.metadata.get("estimated_tokens", 0)
    except Exception as e:
        logger.warning("Layer 0 failed: %s", e)
        traces.append(LayerTrace("l0", meta={"error": str(e)[:100]}))

    # ═══════════════════════════════════════
    # Layer 0.5: Fingerprint Cache
    # ═══════════════════════════════════════
    try:
        if config.layer0_5.enabled:
            cached = _fingerprint_cache.get(user_input)
            if cached:
                traces.append(LayerTrace("l05", cached.route, cached.confidence, cached.source))
                decision = resolve_model(cached, config, CircuitBreaker(config.circuit_breaker))
                _trace_logger.log("", traces)
                return decision
            traces.append(LayerTrace("l05", meta={"hit": False}))
    except Exception as e:
        logger.warning("Layer 0.5 failed: %s", e)

    # ═══════════════════════════════════════
    # Layer 1: Heuristic
    # ═══════════════════════════════════════
    l1_result = None
    try:
        l1_result = layer1_heuristic(user_input, history, turns, est_tokens)
        if l1_result:
            traces.append(LayerTrace("l1", l1_result.route, l1_result.confidence, l1_result.source))
            # High-confidence simple/coding: skip Layer 2
            skip_threshold = {"simple": 0.95, "coding": 0.92}.get(l1_result.route, 1.0)
            if l1_result.confidence >= skip_threshold:
                decision = resolve_model(l1_result, config, CircuitBreaker(config.circuit_breaker),
                                        estimated_tokens=est_tokens, session_turns=turns)
                _fingerprint_cache.set(user_input, decision)
                _trace_logger.log("", traces)
                return decision
        else:
            traces.append(LayerTrace("l1"))
    except Exception as e:
        logger.warning("Layer 1 failed: %s", e)

    # ═══════════════════════════════════════
    # Session Affinity Check
    # ═══════════════════════════════════════
    try:
        affinity_decision = check_affinity(affinity_state, l1_result, config.affinity)
        if affinity_decision:
            # Check circuit breaker for affinity model
            cb = CircuitBreaker(config.circuit_breaker)
            if not cb.is_open(affinity_decision.resolved_provider or "",
                            affinity_decision.resolved_model or ""):
                traces.append(LayerTrace("affinity", affinity_decision.route,
                                        affinity_decision.confidence, "affinity_reuse"))
                _trace_logger.log("", traces)
                return affinity_decision
    except Exception as e:
        logger.warning("Affinity check failed: %s", e)

    # ═══════════════════════════════════════
    # Layer 2: Lightweight Planner
    # ═══════════════════════════════════════
    try:
        l2_result = layer2_planner(user_input, history, config, l1_result)
        traces.append(LayerTrace("l2", l2_result.route, l2_result.confidence, l2_result.source))
    except Exception as e:
        logger.warning("Layer 2 failed: %s", e)
        l2_result = RouteDecision("complex", 0.1, "l2_crash")

    # ═══════════════════════════════════════
    # Session Affinity Establish
    # ═══════════════════════════════════════
    # Note: affinity_state is mutated in-place by the caller

    # ═══════════════════════════════════════
    # Execution Layer
    # ═══════════════════════════════════════
    try:
        cb = CircuitBreaker(config.circuit_breaker)
        decision = resolve_model(l2_result, config, cb,
                                estimated_tokens=est_tokens,
                                session_turns=turns)
        decision.metadata["timeout"] = get_route_timeout(decision.route, config)
        decision.metadata["fallback_chain"] = config.fallback.chains.get(
            decision.route, [decision.resolved_model]
        )
    except Exception as e:
        logger.error("Execution layer failed: %s", e)
        decision = RouteDecision("complex", 0.1, "exec_crash",
                                resolved_model="deepseek-v4-pro")

    # Cache and trace
    try:
        _fingerprint_cache.set(user_input, decision)
    except Exception:
        pass

    _trace_logger.log("", traces)
    return decision
```

**Step 2: Update `agent/brain/__init__.py`**

```python
"""Brain — Multi-layer intelligent model routing for Hermes Agent."""

from agent.brain.types import RouteDecision, SessionAffinityState, LayerTrace, EMPTY_DECISION
from agent.brain.config import BrainConfig
from agent.brain.pipeline import route_message
from agent.brain.affinity import establish_affinity, record_affinity_failure, record_affinity_success
```

**Step 3: Verify import chain**

```bash
python -c "from agent.brain import route_message, BrainConfig, RouteDecision; print('All imports OK')"
```

**Step 4: Commit**

```bash
git add agent/brain/pipeline.py agent/brain/__init__.py
git commit -m "feat: add Brain pipeline orchestrator"
```

---

## Task 11: Integration into run_agent.py

**Objective:** Insert brain routing into `AIAgent.run_conversation()`. Opt-in via config. Zero impact when disabled.

**Files:**
- Modify: `run_agent.py` (insert ~20 lines)

**Step 1: Add brain config loading to AIAgent.__init__**

Find the section in `run_agent.py` where config is parsed (around line 940-1100) and add:

```python
# Near the end of __init__, after primary runtime is set up:
self._brain_enabled = False
self._brain_config = None
self._brain_affinity = None
try:
    brain_raw = self._config.get("brain", {})
    if brain_raw.get("enabled"):
        from agent.brain.config import BrainConfig
        self._brain_config = BrainConfig.from_dict(brain_raw)
        self._brain_enabled = True
        from agent.brain.types import SessionAffinityState
        self._brain_affinity = SessionAffinityState()
except Exception:
    self._brain_enabled = False
```

**Step 2: Insert routing call in run_conversation()**

After line 9259 (`self._restore_primary_runtime()`), insert:

```python
# Brain routing: override model based on intelligent classification
_original_model = None
_original_provider = None
_original_base_url = None
_original_api_key = None

if self._brain_enabled and self._brain_config:
    try:
        from agent.brain import route_message, establish_affinity

        decision = route_message(
            user_input=user_message,
            history=conversation_history or [],
            config=self._brain_config,
            affinity_state=self._brain_affinity,
        )

        if decision.resolved_model:
            # Save original state for restoration
            _original_model = self.model
            _original_provider = self.provider
            _original_base_url = getattr(self, 'base_url', '')
            _original_api_key = getattr(self, 'api_key', '')

            # Apply routing decision
            self.model = decision.resolved_model
            if decision.resolved_provider:
                self.provider = decision.resolved_provider
            if decision.resolved_base_url:
                self.base_url = decision.resolved_base_url

            # Re-initialize client with new model/provider
            self._init_llm_client()

            # Establish affinity after successful route
            self._brain_affinity = establish_affinity(
                self._brain_affinity, decision, self._brain_config.affinity
            ) or self._brain_affinity

            if not self._brain_config.shadow_mode:
                self._emit_status(
                    f"🧠 Brain routed to {decision.route} "
                    f"({decision.resolved_model}, conf={decision.confidence:.0%})"
                )
    except Exception as e:
        logger.warning("Brain routing failed, using default model: %s", e)
```

**Step 3: Add restoration at end of run_conversation (before return)**

```python
# Restore primary model if brain overrode it
if _original_model is not None:
    self.model = _original_model
    self.provider = _original_provider or self.provider
    if _original_base_url:
        self.base_url = _original_base_url
```

**Step 4: Add default config to hermes_cli/config.py**

In `hermes_cli/config.py`, add to DEFAULT_CONFIG:

```python
"brain": {
    "enabled": False,
},
```

**Step 5: Commit**

```bash
git add run_agent.py hermes_cli/config.py
git commit -m "feat: integrate Brain routing into AIAgent.run_conversation"
```

---

## Task 12: End-to-end smoke test

**Objective:** Verify the full pipeline works with a real model call.

**Step 1: Create test script**

```bash
cat > /tmp/test_brain.py << 'EOF'
"""Smoke test for Brain routing pipeline."""
import sys
sys.path.insert(0, '/home/devin/.hermes/hermes-agent')

from agent.brain.types import RouteDecision, SessionAffinityState
from agent.brain.config import BrainConfig
from agent.brain.pipeline import route_message
from agent.brain.layer0 import token_estimate
from agent.brain.layer0_5 import FingerprintCache
from agent.brain.layer1 import layer1_heuristic, is_greeting, compute_code_score

# Test 1: Token estimation
assert token_estimate("hello world") > 0
assert token_estimate("你好") > 0
print("✓ Token estimation")

# Test 2: Fingerprint cache
cache = FingerprintCache(max_entries=5, ttl=3600)
cache.set("test", RouteDecision("simple", 0.9, "test"))
assert cache.get("test") is not None
assert cache.get("nope") is None
print("✓ Fingerprint cache")

# Test 3: Greeting detection
assert is_greeting("你好") is True
assert is_greeting("hello") is True
assert is_greeting("你好，帮我写代码") is False
print("✓ Greeting detection")

# Test 4: Code scoring
assert compute_code_score("写个函数 import numpy as np def main():") >= 3
assert compute_code_score("帮我查一下 import 怎么用") < 2
print("✓ Code scoring")

# Test 5: Full pipeline (greeting)
config = BrainConfig()
config.enabled = True
result = route_message("你好", [], config)
assert result.route == "simple"
print(f"✓ Full pipeline greeting: {result.route} ({result.source})")

# Test 6: Full pipeline (code)
result = route_message("写个Python函数用pandas读取CSV文件", [], config)
print(f"✓ Full pipeline code: {result.route} ({result.source})")

# Test 7: Full pipeline (complex)
result = route_message(
    "我需要设计一个分布式系统架构，包括负载均衡、数据库分片、缓存策略，请详细分析",
    [], config
)
print(f"✓ Full pipeline complex: {result.route} ({result.source})")

print("\n🎉 All smoke tests passed!")
EOF

cd ~/.hermes/hermes-agent && source venv/bin/activate
python /tmp/test_brain.py
```

**Step 2: Run and verify**

Expected output: all tests pass, greeting classifies as simple, code as coding/whatever L1 says, complex goes to L2.

**Step 3: Commit**

```bash
git add tests/brain/  # if any test files were created
git commit -m "test: add Brain smoke tests"
```

---

## Summary

| Task | File | LOC (est) | Purpose |
|------|------|-----------|---------|
| 0 | `types.py` | 60 | Shared data types |
| 0 | `__init__.py` | 15 | Module exports |
| 1 | `config.py` | 130 | Centralized config dataclasses |
| 2 | `layer0.py` | 85 | Preprocessing (multimodal, token est) |
| 3 | `layer0_5.py` | 80 | Fingerprint cache |
| 4 | `layer1.py` | 140 | Heuristic classifier |
| 5 | `layer2.py` | 160 | Lightweight planner |
| 6 | `affinity.py` | 90 | Session affinity |
| 7 | `circuit_breaker.py` | 130 | Persistent circuit breaker |
| 8 | `execution.py` | 90 | Model resolution + fallback |
| 9 | `logging.py` | 65 | Trace logging |
| 10 | `pipeline.py` | 175 | Orchestrator |
| 11 | `run_agent.py` | +30 | Integration hook |
| **Total** | | **~1250** | 12 files |

**Post-implementation:** Run full test suite — `python -m pytest tests/ -o 'addopts=' -q` — to ensure no regressions from the `run_agent.py` hook.
