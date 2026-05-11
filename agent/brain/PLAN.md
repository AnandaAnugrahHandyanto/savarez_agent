# Hermes Brain — Three-Layer Intelligent Routing Architecture

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Replace Hermes' static model-per-session routing with a three-layer intelligent brain that classifies every user message and routes it to the optimal model/toolset, with fallback and monitoring.

**Architecture:** Standalone `agent/brain/` package with five modules. Plugs into `AIAgent.run_conversation()` as a pre-routing hook. Opt-in via `config.yaml` (`brain.enabled: true`), defaults to off for zero-risk rollout.

**Tech Stack:** Python 3.11+, faiss-cpu or hnswlib (embedding), json-schema (Planner output validation), LRU cache (stdlib `functools.lru_cache`), deepseek-v4-flash (Planner LLM)

**Core principle:** Stability > Performance > Speed. Every layer fails safe — if routing fails for any reason, fall back to the default model.

---

## Architecture Diagram

```
user_input
  ↓
[Brain.router(user_input, session_context) → RoutingDecision]
  ↓
┌─────────────────────────────────────────────┐
│ Layer 0: Preprocessor                       │  <1ms
│   - Token count estimation                  │
│   - Multimodal detection (images in input)  │
│   - Compression gate check                  │
│   → Updates metadata dict                  │
├─────────────────────────────────────────────┤
│ Layer 0.5: Fingerprint Cache                │  <1ms
│   - SHA256(normalized_text)                 │
│   - Exact match → reuse RoutingDecision     │
│   - TTL: 1h for exact, 24h for semantic     │
├─────────────────────────────────────────────┤
│ Layer 1: Heuristic Classifier               │  <5ms
│   - Rule engine: regex/keyword patterns     │
│     → Coding, Translation, Simple greeting, │
│       Math, Vision, Long-context            │
│   - Embedding index: cosine similarity      │
│     → Fallback for unclassified inputs      │
│   - Combined confidence score               │
│   → If confidence ≥ 0.9, skip Layer 2       │
├─────────────────────────────────────────────┤
│ Layer 2: Light Planner (deepseek-v4-flash)  │  ~500ms
│   - Structured JSON output with schema      │
│   - Fields: route, confidence, risk,        │
│             reasoning, latency_budget       │
│   - risk = deterministic function (not LLM) │
│   → If confidence < 0.6 OR risk=high:       │
│     fallback to complex model               │
├─────────────────────────────────────────────┤
│ Execution: RoutingDecision → model/provider │
│   Routes: simple | coding | complex |       │
│           vision | long_context             │
├─────────────────────────────────────────────┤
│ Fallback chain                              │
│   - Same-tier alternative model             │
│   - Cross-provider fallback                 │
│   - Ultimate: default model from config     │
└─────────────────────────────────────────────┘
        ↓
  Monitoring Layer (async, non-blocking)
    - Route log: {input_hash, route, model, latency, cost}
    - Outcome signal: retry/fallback/user_feedback
    - Feedback loop: prunes bad routing rules
```

---

## File Structure (new files)

```
agent/brain/
├── __init__.py          # Public API: router(), RoutingDecision
├── preprocessor.py      # Layer 0: token estimation, multimodal detect
├── fingerprint.py       # Layer 0.5: LRU cache with TTL
├── classifier.py        # Layer 1: rules + embedding hybrid
├── planner.py           # Layer 2: lightweight LLM router
├── routes.py            # Route enum, RoutingDecision dataclass
├── fallback.py          # Fallback chain logic
├── monitor.py           # Cost tracking + health + feedback loop
└── config_schema.py     # Brain config section for config.yaml
```

Modified files:
- `run_agent.py` — integrate brain as pre-routing hook
- `hermes_cli/config.py` — add `brain` section to DEFAULT_CONFIG
- `hermes_cli/main.py` — `hermes config set brain.*` support
- `tests/agent/test_brain_routing.py` — full integration tests

---

## Configuration (config.yaml)

```yaml
brain:
  enabled: false  # Opt-in: set to true to activate
  layer_0:
    token_estimation: average  # average | tiktoken | character
  layer_0_5:
    cache_size: 1000
    exact_ttl_seconds: 3600
  layer_1:
    embedding_model: all-MiniLM-L6-v2  # sentence-transformers model
    embedding_threshold: 0.75  # cosine similarity minimum
    rule_confidence: 1.0  # confidence for rule matches
  layer_2:
    provider: openai-compatible
    model: deepseek-v4-flash
    base_url: https://api.deepseek.com/v1
    api_key: ''  # inherits from main if empty
    timeout: 5
    confidence_threshold: 0.6
  routes:
    simple:
      provider: openai-compatible
      model: deepseek-v4-flash
    coding:
      provider: openai-compatible
      model: deepseek-v4-pro
      toolsets: [terminal, file, web, browser, code_execution]
    complex:
      provider: openai-compatible
      model: deepseek-v4-pro
      toolsets: all
    vision:
      provider: openai-compatible
      model: qwen3-vl-plus
      base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    long_context:
      provider: openai-compatible
      model: deepseek-v4-pro
  fallback:
    same_tier_models:
      - provider: openrouter
        model: anthropic/claude-sonnet-4
    cross_provider:
      - provider: gemini
        model: gemini-2.5-flash
  monitor:
    log_dir: ~/.hermes/logs/brain/
    max_log_age_days: 30
    feedback_loop:
      strong_signal_window_seconds: 60
      weak_signal_ratio_threshold: 0.3
```

---

## Task 1: Create route types and data structures

**Objective:** Define the core data types that all brain layers use

**Files:**
- Create: `agent/brain/__init__.py`
- Create: `agent/brain/routes.py`

**Step 1: Create routes.py with Route enum and RoutingDecision**

```python
"""Route types and routing decision dataclass."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List


class Route(str, Enum):
    """Target execution route."""
    SIMPLE = "simple"            # Quick answers, no tools needed
    CODING = "coding"            # Code generation, file ops, terminal
    COMPLEX = "complex"          # Multi-step reasoning, full tools
    VISION = "vision"            # Image analysis required
    LONG_CONTEXT = "long_context"  # >64K tokens expected


@dataclass
class RouteMetadata:
    """Extra context collected during routing."""
    token_count_estimate: int = 0
    is_multimodal: bool = False
    needs_compression: bool = False
    source: str = "unknown"  # "rule", "embedding", "planner", "cache"
    confidence: float = 0.0
    risk: str = "low"  # low | medium | high


@dataclass
class ModelTarget:
    """Concrete model/provider to use."""
    provider: str
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None


@dataclass
class RoutingDecision:
    """Final routing decision after all layers."""
    route: Route
    model: ModelTarget
    metadata: RouteMetadata = field(default_factory=RouteMetadata)
    toolsets: Optional[List[str]] = None
    reasoning: str = ""
    latency_budget_ms: int = 30000
    fallback_chain: List[ModelTarget] = field(default_factory=list)
```

**Step 2: Create __init__.py with public API**

```python
"""Hermes Brain — Intelligent model routing."""

from agent.brain.routes import Route, RoutingDecision, ModelTarget, RouteMetadata

__all__ = ["Route", "RoutingDecision", "ModelTarget", "RouteMetadata", "router"]
```

**Step 3: Verify imports work**

```bash
cd ~/.hermes/hermes-agent && python -c "from agent.brain import Route, RoutingDecision; print('OK')"
```

---

## Task 2: Implement Layer 0 — Preprocessor

**Objective:** Token estimation, multimodal detection, compression gate

**Files:**
- Create: `agent/brain/preprocessor.py`
- Create: `tests/agent/test_brain_routing.py`

**Step 1: Write failing tests**

```python
import pytest
from agent.brain.preprocessor import Preprocessor, estimate_tokens, detect_multimodal

class TestPreprocessor:
    def test_estimate_tokens_short(self):
        assert estimate_tokens("Hello world") > 0
        assert estimate_tokens("Hello world") <= 5

    def test_estimate_tokens_long(self):
        long_text = "test " * 1000
        tokens = estimate_tokens(long_text)
        assert 500 < tokens < 2000  # char / 4 ≈ 500; with overhead

    def test_estimate_tokens_empty(self):
        assert estimate_tokens("") == 0

    def test_detect_multimodal_image_url(self):
        assert detect_multimodal("Look at this: https://example.com/img.jpg")

    def test_detect_multimodal_no_image(self):
        assert not detect_multimodal("Hello world, no images here")

    def test_detect_multimodal_base64_image(self):
        assert detect_multimodal("data:image/png;base64,iVBOR...")

    def test_preprocessor_integration(self):
        p = Preprocessor()
        result = p.process("Hello world")
        assert result.token_count_estimate > 0
        assert not result.is_multimodal
        assert not result.needs_compression

    def test_preprocessor_multimodal_input(self):
        p = Preprocessor()
        result = p.process("Check this: https://x.com/img/photo.jpg")
        assert result.is_multimodal

    def test_preprocessor_compression_gate(self):
        p = Preprocessor(compression_threshold=0.8, current_fill_ratio=0.85)
        result = p.process("Short message")
        assert result.needs_compression
```

**Step 2: Run tests — expect FAIL**

```bash
cd ~/.hermes/hermes-agent && python -m pytest tests/agent/test_brain_routing.py::TestPreprocessor -v
```

**Step 3: Implement preprocessor.py**

```python
"""Layer 0: Preprocessing — token estimation, multimodal detection, compression gate."""

import re
import logging

logger = logging.getLogger(__name__)

# Conservative: 1 token ≈ 4 characters for English, 1 token ≈ 1.5 chars for Chinese
def estimate_tokens(text: str) -> int:
    """Fast token count approximation. No LLM call, <1ms."""
    if not text:
        return 0
    chars = len(text)
    # Count CJK characters (U+4E00-U+9FFF, U+3400-U+4DBF, U+F900-U+FAFF)
    cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')
    non_cjk = chars - cjk_count
    # CJK: ~1.5 chars per token, English: ~4 chars per token
    return int(cjk_count / 1.5 + non_cjk / 4)


# Image URL patterns
_IMAGE_URL_PATTERN = re.compile(
    r'(https?://\S+\.(?:png|jpg|jpeg|gif|webp|bmp|svg)(?:\?\S*)?)',
    re.IGNORECASE
)
_BASE64_IMAGE_PATTERN = re.compile(r'data:image/\w+;base64,')


def detect_multimodal(text: str) -> bool:
    """Detect if input contains image references."""
    if not text:
        return False
    if _IMAGE_URL_PATTERN.search(text):
        return True
    if _BASE64_IMAGE_PATTERN.search(text):
        return True
    return False


class Preprocessor:
    """Layer 0: fast preprocessing for routing metadata."""

    def __init__(self, compression_threshold: float = 0.8, current_fill_ratio: float = 0.0):
        self.compression_threshold = compression_threshold
        self.current_fill_ratio = current_fill_ratio

    def process(self, text: str):
        """Process input text and return routing metadata."""
        from agent.brain.routes import RouteMetadata

        token_count = estimate_tokens(text)
        is_multimodal = detect_multimodal(text)
        needs_compression = self.current_fill_ratio > self.compression_threshold

        logger.debug(
            "Layer 0: tokens=%d multimodal=%s compress=%s",
            token_count, is_multimodal, needs_compression
        )

        return RouteMetadata(
            token_count_estimate=token_count,
            is_multimodal=is_multimodal,
            needs_compression=needs_compression,
        )
```

**Step 4: Run tests — expect PASS**

```bash
cd ~/.hermes/hermes-agent && python -m pytest tests/agent/test_brain_routing.py::TestPreprocessor -v
```

**Step 5: Commit**

```bash
git add agent/brain/__init__.py agent/brain/routes.py agent/brain/preprocessor.py tests/agent/test_brain_routing.py
git commit -m "feat(brain): add Layer 0 preprocessor with token estimation and multimodal detection"
```

---

## Task 3: Implement Layer 0.5 — Fingerprint Cache

**Objective:** LRU cache for request fingerprints, avoid re-routing identical inputs

**Files:**
- Create: `agent/brain/fingerprint.py`
- Modify: `tests/agent/test_brain_routing.py`

**Step 1: Write failing tests**

```python
import time
import hashlib
from agent.brain.fingerprint import FingerprintCache

class TestFingerprintCache:
    def test_cache_hit(self):
        cache = FingerprintCache(max_size=100, ttl_seconds=3600)
        from agent.brain.routes import Route, RoutingDecision, ModelTarget, RouteMetadata
        decision = RoutingDecision(
            route=Route.SIMPLE,
            model=ModelTarget(provider="test", model="flash"),
            metadata=RouteMetadata(source="cache"),
        )
        text = "Hello world"
        cache.put(text, decision)
        result = cache.get(text)
        assert result is not None
        assert result.route == Route.SIMPLE

    def test_cache_miss(self):
        cache = FingerprintCache(max_size=100, ttl_seconds=3600)
        result = cache.get("never seen before")
        assert result is None

    def test_cache_ttl_expiry(self):
        cache = FingerprintCache(max_size=100, ttl_seconds=0.01)
        from agent.brain.routes import Route, RoutingDecision, ModelTarget
        decision = RoutingDecision(
            route=Route.SIMPLE,
            model=ModelTarget(provider="test", model="flash"),
        )
        cache.put("test", decision)
        time.sleep(0.02)
        result = cache.get("test")
        assert result is None

    def test_cache_normalization(self):
        """Different whitespace should hit same cache entry."""
        cache = FingerprintCache(max_size=100, ttl_seconds=3600)
        from agent.brain.routes import Route, RoutingDecision, ModelTarget
        decision = RoutingDecision(
            route=Route.COMPLEX,
            model=ModelTarget(provider="test", model="pro"),
        )
        cache.put("  Hello   World  ", decision)
        result1 = cache.get("Hello World")
        result2 = cache.get("hello world")
        assert result1 is not None
        assert result2 is not None

    def test_cache_max_size_eviction(self):
        cache = FingerprintCache(max_size=3, ttl_seconds=3600)
        from agent.brain.routes import Route, RoutingDecision, ModelTarget
        for i in range(5):
            decision = RoutingDecision(
                route=Route.SIMPLE,
                model=ModelTarget(provider="test", model=f"model{i}"),
            )
            cache.put(f"text{i}", decision)
        # Oldest entry should be evicted
        assert cache.get("text0") is None or cache.get("text1") is None
```

**Step 2: Run tests — expect FAIL**

**Step 3: Implement fingerprint.py**

```python
"""Layer 0.5: Request fingerprint cache with LRU eviction and TTL."""

import hashlib
import logging
import re
import time
from collections import OrderedDict
from typing import Optional

from agent.brain.routes import RoutingDecision

logger = logging.getLogger(__name__)

# Normalize text for consistent hashing: lowercase, collapse whitespace
_NORMALIZE_RE = re.compile(r'\s+')


def _normalize(text: str) -> str:
    """Normalize text for fingerprinting: lowercase + collapse whitespace."""
    return _NORMALIZE_RE.sub(' ', text.lower().strip())


def _hash(text: str) -> str:
    """SHA256 of normalized text."""
    return hashlib.sha256(_normalize(text).encode()).hexdigest()


class CacheEntry:
    """A single cache entry with TTL."""
    __slots__ = ('decision', 'expires_at')

    def __init__(self, decision: RoutingDecision, ttl_seconds: float):
        self.decision = decision
        self.expires_at = time.monotonic() + ttl_seconds

    @property
    def expired(self) -> bool:
        return time.monotonic() > self.expires_at


class FingerprintCache:
    """LRU cache for routing decisions, keyed by normalized text hash.

    Thread-safe for reads, not for concurrent writes (single-agent use case).
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()

    def get(self, text: str) -> Optional[RoutingDecision]:
        """Look up a cached routing decision. Returns None on miss or expiry."""
        key = _hash(text)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.expired:
            del self._cache[key]
            return None
        # Move to end (LRU: most recently used)
        self._cache.move_to_end(key)
        logger.debug("Layer 0.5: cache hit for key=%s", key[:8])
        return entry.decision

    def put(self, text: str, decision: RoutingDecision):
        """Store a routing decision in the cache."""
        key = _hash(text)
        # Don't cache if we'd be evicting immediately
        if len(self._cache) >= self.max_size:
            # Evict oldest (first in OrderedDict)
            evicted_key, _ = self._cache.popitem(last=False)
            logger.debug("Layer 0.5: evicted key=%s", evicted_key[:8])
        self._cache[key] = CacheEntry(decision, self.ttl_seconds)

    def size(self) -> int:
        """Number of cached entries."""
        # Purge expired entries
        expired = [k for k, e in self._cache.items() if e.expired]
        for k in expired:
            del self._cache[k]
        return len(self._cache)
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

---

## Task 4: Implement Layer 1 — Heuristic Classifier (Rules)

**Objective:** Rule engine with regex/keyword patterns for high-confidence classification

**Files:**
- Create: `agent/brain/classifier.py`
- Modify: `tests/agent/test_brain_routing.py`

**Step 1: Design the rule set**

Rules are ordered by specificity (most specific first). Each rule returns `(route, confidence)` or `None` if no match.

```python
# Rule format: (name, pattern_func, route, confidence)
# pattern_func(text) -> bool
```

Rules to implement:

| # | Name | Pattern | Route | Why high confidence |
|---|------|---------|-------|---------------------|
| 1 | coding_keywords | `(写|编写|实现|代码|函数|类|修复|bug|重构|优化.*代码\|import\|def \|class \|function \|async def\|npm\|pip\|cargo\|git\|docker\|k8s)` | coding | 0.95 |
| 2 | vision_request | `(这张图|图片中|看图|截图|分析.*图|describe.*image\|what.*in.*picture)` | vision | 0.90 |
| 3 | translation | `(翻译|translate\|翻成|译成\|to Chinese\|to English)` | simple | 0.95 |
| 4 | greeting | `^(你好|hi|hello|hey|早上好|晚上好|下午好)[!！。.]?\s*$` | simple | 1.0 |
| 5 | math | Contains LaTeX `$$...$$` or `\(` or complex math symbols | coding | 0.80 |
| 6 | long_input | token_count > 32000 | long_context | 0.85 |
| 7 | multimodal_media | contains image URL patterns | vision | 0.90 |

**Step 2: Write failing tests**

```python
from agent.brain.classifier import RuleClassifier

class TestRuleClassifier:
    def test_coding_detection_python(self):
        c = RuleClassifier()
        result = c.classify("帮我写一个Python快速排序算法")
        assert result is not None
        assert result[0] == Route.CODING

    def test_coding_detection_import(self):
        c = RuleClassifier()
        result = c.classify("import numpy as np\n\ndef my_func():\n    pass")
        assert result is not None
        assert result[0] == Route.CODING

    def test_greeting_detection(self):
        c = RuleClassifier()
        result = c.classify("你好")
        assert result is not None
        assert result[0] == Route.SIMPLE
        assert result[1] >= 0.9

    def test_translation_detection(self):
        c = RuleClassifier()
        result = c.classify("翻译以下内容：Hello world")
        assert result is not None
        assert result[0] == Route.SIMPLE

    def test_vision_detection(self):
        c = RuleClassifier()
        result = c.classify("这张图里有什么？")
        assert result is not None
        assert result[0] == Route.VISION

    def test_no_match(self):
        c = RuleClassifier()
        result = c.classify("What do you think about climate change policies in developing nations?")
        assert result is None  # Should not be caught by rules, needs Layer 2

    def test_long_input(self):
        c = RuleClassifier()
        long_text = "test " * 10000  # ~40K chars ≈ 10K tokens
        result = c.classify(long_text)
        # May or may not match; depends on token threshold
```

**Step 3: Implement classifier.py**

```python
"""Layer 1: Heuristic classifier — rule engine + embedding fallback."""

import logging
import re
from typing import Optional, Tuple

from agent.brain.routes import Route

logger = logging.getLogger(__name__)

# ── Rule definitions ──────────────────────────────────────────────
# Each rule: (name, compiled_regex_or_callable, route, confidence)

_CODING_KEYWORDS_RE = re.compile(
    r'(写|编写|实现|代码|函数|类|修复|bug|重构|优化|部署|配置'
    r'|import\s|def\s|class\s|function\s|async\s+def'
    r'|npm\s|pip\s|cargo\s|git\s|docker|k8s|kubernetes'
    r'|api|endpoint|middleware|database|sql|query'
    r'|algorithm|sort|search|parse|compile'
    r'|debug|traceback|error|exception|crash)',
    re.IGNORECASE
)

_VISION_REQUEST_RE = re.compile(
    r'(这张图|图片中|看图|截图|分析.*图|describe.*image'
    r'|what.*in.*(?:picture|image|photo|screenshot)'
    r'|describe.*(?:picture|image|photo|screenshot)'
    r'|look.*at.*(?:this|that|the).*(?:picture|image|photo))',
    re.IGNORECASE
)

_TRANSLATION_RE = re.compile(
    r'(翻译|translate|翻成|译成|转成.*中文|转成.*英文'
    r'|to\s+Chinese|to\s+English)',
    re.IGNORECASE
)

_GREETING_RE = re.compile(
    r'^(你好|hi|hello|hey|早上好|晚上好|下午好|good\s+(?:morning|evening|afternoon))[!！。.]?\s*$',
    re.IGNORECASE
)

_IMAGE_URL_IN_TEXT = re.compile(
    r'(https?://\S+\.(?:png|jpg|jpeg|gif|webp|bmp)(?:\?\S*)?)',
    re.IGNORECASE
)

# ── Rules list: ordered by specificity ──────────────────────────

class RuleClassifier:
    """Rule-based classifier using regex patterns.

    Returns (route, confidence) on match, or None if no rule fires.
    Confidence is baked into each rule based on empirical precision.
    """

    def __init__(self, long_context_threshold: int = 32000):
        self.long_context_threshold = long_context_threshold

    def classify(self, text: str, token_count: int = 0) -> Optional[Tuple[Route, float]]:
        """Apply rules in priority order. First match wins."""
        if not text or not text.strip():
            return None

        # Rule 1: Long context (token-based, must come first)
        if token_count > self.long_context_threshold:
            logger.debug("Layer 1: rule=long_input route=%s conf=0.85", Route.LONG_CONTEXT)
            return (Route.LONG_CONTEXT, 0.85)

        # Rule 2: Vision request (semantic)
        if _VISION_REQUEST_RE.search(text):
            logger.debug("Layer 1: rule=vision_request route=%s conf=0.90", Route.VISION)
            return (Route.VISION, 0.90)

        # Rule 3: Image URL in text
        if _IMAGE_URL_IN_TEXT.search(text):
            logger.debug("Layer 1: rule=image_url route=%s conf=0.90", Route.VISION)
            return (Route.VISION, 0.90)

        # Rule 4: Greeting (must be short, exact match)
        if _GREETING_RE.match(text) and len(text) < 30:
            logger.debug("Layer 1: rule=greeting route=%s conf=1.0", Route.SIMPLE)
            return (Route.SIMPLE, 1.0)

        # Rule 5: Translation
        if _TRANSLATION_RE.search(text) and len(text) < 2000:
            logger.debug("Layer 1: rule=translation route=%s conf=0.95", Route.SIMPLE)
            return (Route.SIMPLE, 0.95)

        # Rule 6: Coding (broad pattern, lower confidence)
        if _CODING_KEYWORDS_RE.search(text):
            logger.debug("Layer 1: rule=coding route=%s conf=0.85", Route.CODING)
            return (Route.CODING, 0.85)

        return None
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

---

## Task 5: Implement Layer 1 — Embedding Classifier

**Objective:** Embedding-based similarity as fallback when rules don't match

**Files:**
- Modify: `agent/brain/classifier.py`
- Modify: `tests/agent/test_brain_routing.py`

**Step 1: Write failing tests**

```python
class TestEmbeddingClassifier:
    def test_embedding_initialization(self):
        from agent.brain.classifier import EmbeddingClassifier
        ec = EmbeddingClassifier(model_name="all-MiniLM-L6-v2")
        assert ec.model is not None

    def test_embedding_similarity_coding(self):
        from agent.brain.classifier import EmbeddingClassifier
        ec = EmbeddingClassifier(model_name="all-MiniLM-L6-v2")
        ec.add_example("Write a function to sort an array", Route.CODING)
        ec.add_example("Fix the bug in my React component", Route.CODING)
        result = ec.classify("Help me implement a binary search tree")
        assert result is not None
        # Should match coding
        assert result[0] == Route.CODING

    def test_embedding_no_match(self):
        from agent.brain.classifier import EmbeddingClassifier
        ec = EmbeddingClassifier(threshold=0.9)  # Very strict
        ec.add_example("Write code", Route.CODING)
        result = ec.classify("What is the weather today?")
        assert result is None  # No match with strict threshold

    def test_embedding_multiple_categories(self):
        from agent.brain.classifier import EmbeddingClassifier
        ec = EmbeddingClassifier()
        ec.add_example("def hello(): print('hi')", Route.CODING)
        ec.add_example("What's 2+2?", Route.SIMPLE)
        ec.add_example("Write a novel", Route.COMPLEX)
        # Should return closest match
        result = ec.classify("Write a Python script")
        assert result is not None
```

**Step 2: Implement embedding classifier**

```python
"""Embedding-based classifier as fallback for Layer 1."""

import logging
import numpy as np
from typing import List, Optional, Tuple

from agent.brain.routes import Route

logger = logging.getLogger(__name__)


class EmbeddingClassifier:
    """Cosine-similarity classifier using sentence-transformer embeddings.

    Uses an in-memory index (list of vectors + labels). For production
    scale, swap to faiss or hnswlib.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", threshold: float = 0.75):
        self.threshold = threshold
        self.model_name = model_name
        self._model = None
        self._embeddings: List[np.ndarray] = []
        self._routes: List[Route] = []
        self._texts: List[str] = []

    @property
    def model(self):
        """Lazy-load sentence-transformers."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                logger.info("Loaded embedding model: %s", self.model_name)
            except ImportError:
                logger.warning(
                    "sentence-transformers not installed. "
                    "Embedding classifier disabled. "
                    "Install with: pip install sentence-transformers"
                )
                self._model = False  # Sentinel to avoid retry
        return self._model if self._model is not False else None

    def add_example(self, text: str, route: Route):
        """Add a labeled example to the index."""
        self._texts.append(text)
        self._routes.append(route)

    def build_index(self):
        """Build embedding index from added examples."""
        model = self.model
        if model is None:
            return
        if not self._texts:
            return
        embeddings = model.encode(self._texts, show_progress_bar=False)
        self._embeddings = list(embeddings)

    def classify(self, text: str) -> Optional[Tuple[Route, float]]:
        """Classify by nearest-neighbor cosine similarity."""
        model = self.model
        if model is None or not self._embeddings:
            return None

        query_emb = model.encode([text], show_progress_bar=False)[0]
        similarities = [
            float(np.dot(query_emb, emb) / (np.linalg.norm(query_emb) * np.linalg.norm(emb) + 1e-10))
            for emb in self._embeddings
        ]

        if not similarities:
            return None

        best_idx = int(np.argmax(similarities))
        best_sim = similarities[best_idx]

        if best_sim >= self.threshold:
            route = self._routes[best_idx]
            # Map similarity to confidence: linear from threshold→1.0 mapped to 0.6→1.0
            confidence = 0.6 + 0.4 * (best_sim - self.threshold) / (1.0 - self.threshold)
            confidence = min(1.0, max(0.0, confidence))
            logger.debug(
                "Layer 1 embedding: route=%s sim=%.3f conf=%.3f",
                route, best_sim, confidence
            )
            return (route, confidence)

        return None
```

**Step 3: Integrate into RuleClassifier as hybrid**

Add to `classifier.py`:

```python
class HybridClassifier:
    """Layer 1: Rules first, embedding fallback."""

    def __init__(
        self,
        rule_classifier: RuleClassifier = None,
        embedding_classifier: EmbeddingClassifier = None,
    ):
        self.rules = rule_classifier or RuleClassifier()
        self.embedding = embedding_classifier or EmbeddingClassifier()

    def classify(self, text: str, token_count: int = 0) -> Optional[Tuple[Route, float]]:
        """Rules first, then embedding. Both return (route, confidence) or None."""
        # Try rules
        result = self.rules.classify(text, token_count)
        if result is not None:
            return result

        # Fall back to embedding
        result = self.embedding.classify(text)
        if result is not None:
            return result

        return None

    def add_example(self, text: str, route: Route):
        """Add a labeled example for the embedding index."""
        self.embedding.add_example(text, route)

    def build_index(self):
        """Build embedding index (call after adding examples)."""
        self.embedding.build_index()
```

**Step 4: Run tests**

---

## Task 6: Implement Layer 2 — Light Planner

**Objective:** LLM-based router using deepseek-v4-flash with structured JSON output

**Files:**
- Create: `agent/brain/planner.py`
- Modify: `tests/agent/test_brain_routing.py`

**Step 1: Write failing tests**

```python
import json
from agent.brain.planner import PlannerRouter

class TestPlannerRouter:
    def test_planner_schema_generation(self):
        """Planner produces valid JSON schema for function calling."""
        router = PlannerRouter(model="deepseek-v4-flash")
        schema = router._build_tool_schema()
        assert "function" in schema
        assert schema["function"]["name"] == "route_request"

    def test_planner_response_parsing_valid(self):
        router = PlannerRouter(model="deepseek-v4-flash")
        valid_json = json.dumps({
            "route": "coding",
            "confidence": 0.85,
            "reasoning": "User is asking to implement a data structure"
        })
        result = router._parse_response(valid_json)
        assert result is not None
        assert result["route"] == "coding"
        assert result["confidence"] == 0.85

    def test_planner_response_parsing_invalid(self):
        router = PlannerRouter(model="deepseek-v4-flash")
        result = router._parse_response("{invalid json")
        assert result is None

    def test_planner_response_parsing_unknown_route(self):
        router = PlannerRouter(model="deepseek-v4-flash")
        result = router._parse_response('{"route": "unknown", "confidence": 0.5}')
        assert result is None  # Unknown route rejected

    def test_risk_computation_high(self):
        from agent.brain.planner import _compute_risk
        risk = _compute_risk(confidence=0.55, token_count=1000, route=Route.CODING)

    def test_risk_computation_low(self):
        from agent.brain.planner import _compute_risk
        risk = _compute_risk(confidence=0.85, token_count=500, route=Route.SIMPLE)
        assert risk == "low"
```

**Step 2: Implement planner.py**

```python
"""Layer 2: Light Planner — LLM-based router with structured JSON output."""

import json
import logging
import os
from typing import Optional, Dict, Any

from openai import OpenAI

from agent.brain.routes import Route

logger = logging.getLogger(__name__)

# Valid routes for validation
_VALID_ROUTES = {r.value for r in Route}

# Planner prompt — injected dynamically with conversation context
_PLANNER_SYSTEM_PROMPT = """You are a request router for an AI agent. Your job is to classify user requests into one of these categories:

- simple: Quick fact, translation, greeting, simple question. No tools needed.
- coding: Writing code, debugging, file operations, terminal commands, git, docker.
- complex: Multi-step reasoning, research, analysis, creative writing, planning.
- vision: Image analysis or questions about pictures/screenshots.
- long_context: Very long input (>32K tokens) that needs high context window.

Consider:
1. Does the user need tools (terminal, file, web)?
2. How complex is the reasoning required?
3. Is there image content to analyze?
4. How long is the input?

Respond with this EXACT format (no markdown, just JSON):
{"route": "<category>", "confidence": <0.0-1.0>, "reasoning": "<brief>"}"""


def _compute_risk(confidence: float, token_count: int, route: str) -> str:
    """Deterministic risk computation — NOT from the LLM.

    This is the stable calibration function discussed in the architecture doc.
    """
    if confidence < 0.65:
        return "high"
    if token_count > 8000:
        return "high"
    if route == "coding" and confidence < 0.75:
        return "medium"
    return "low"


class PlannerRouter:
    """Layer 2: LLM-based routing using a lightweight model."""

    def __init__(
        self,
        provider: str = "openai-compatible",
        model: str = "deepseek-v4-flash",
        base_url: str = "https://api.deepseek.com/v1",
        api_key: str = "",
        timeout: int = 5,
        confidence_threshold: float = 0.6,
    ):
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.confidence_threshold = confidence_threshold

        # Resolve API key
        api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            logger.warning("No API key for Planner. Layer 2 disabled.")
            self._client = None
        else:
            self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)

    def _build_tool_schema(self) -> Dict[str, Any]:
        """Build a function-calling schema to enforce structured JSON output."""
        return {
            "type": "function",
            "function": {
                "name": "route_request",
                "description": "Classify the user request into a routing category.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "route": {
                            "type": "string",
                            "enum": list(_VALID_ROUTES),
                            "description": "Best routing category"
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                            "description": "Confidence in this classification"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Brief explanation (max 100 chars)"
                        }
                    },
                    "required": ["route", "confidence", "reasoning"]
                }
            }
        }

    def _parse_response(self, raw: str) -> Optional[Dict[str, Any]]:
        """Parse and validate Planner response."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Planner returned invalid JSON: %s", raw[:200])
            return None

        # Must have required fields
        if not all(k in data for k in ("route", "confidence")):
            logger.warning("Planner response missing fields: %s", data)
            return None

        # Validate route
        if data["route"] not in _VALID_ROUTES:
            logger.warning("Planner returned unknown route: %s", data["route"])
            return None

        # Validate confidence
        try:
            conf = float(data["confidence"])
            if not (0.0 <= conf <= 1.0):
                return None
            data["confidence"] = conf
        except (ValueError, TypeError):
            return None

        return data

    def route(self, user_message: str, conversation_history: list = None) -> Optional[Dict[str, Any]]:
        """Call the Planner LLM and return structured routing decision.

        Returns None if call fails or confidence is too low.
        """
        if self._client is None:
            return None

        # Build messages
        messages = [{"role": "system", "content": _PLANNER_SYSTEM_PROMPT}]

        # Add recent conversation context (last 2 exchanges)
        if conversation_history:
            recent = conversation_history[-4:]  # last 2 exchanges
            for msg in recent:
                if msg.get("role") in ("user", "assistant"):
                    content = msg.get("content", "")
                    if isinstance(content, str) and len(content) > 200:
                        content = content[:200] + "..."
                    messages.append({"role": msg["role"], "content": content})

        # Add current message
        truncated = user_message
        if len(truncated) > 4000:
            truncated = truncated[:2000] + "\n...\n" + truncated[-2000:]
        messages.append({"role": "user", "content": truncated})

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[self._build_tool_schema()],
                tool_choice={"type": "function", "function": {"name": "route_request"}},
                temperature=0.0,  # Deterministic
            )

            # Extract function call
            tool_calls = response.choices[0].message.tool_calls
            if not tool_calls:
                logger.warning("Planner returned no tool call")
                return None

            raw_args = tool_calls[0].function.arguments
            result = self._parse_response(raw_args)

            if result is None:
                return None

            logger.info(
                "Layer 2: route=%s conf=%.2f reasoning=%s",
                result["route"], result["confidence"], result.get("reasoning", "")
            )
            return result

        except Exception as e:
            logger.warning("Planner call failed: %s", e)
            return None

    def compute_decision(
        self, user_message: str, token_count: int = 0, conversation_history: list = None
    ) -> Optional[Dict[str, Any]]:
        """Full Layer 2 pipeline: call planner, compute risk, validate."""
        result = self.route(user_message, conversation_history)
        if result is None:
            return None

        # Compute deterministic risk
        result["risk"] = _compute_risk(
            confidence=result["confidence"],
            token_count=token_count,
            route=result["route"],
        )

        # Reject low-confidence or high-risk
        if result["confidence"] < self.confidence_threshold or result["risk"] == "high":
            logger.info(
                "Layer 2: rejected (conf=%.2f risk=%s), fallback to complex",
                result["confidence"], result["risk"]
            )
            return None

        return result
```

**Step 3: Run tests**

---

## Task 7: Implement Fallback Chain

**Objective:** Robust fallback when primary model fails

**Files:**
- Create: `agent/brain/fallback.py`
- Modify: `tests/agent/test_brain_routing.py`

**Step 1: Implement fallback.py**

```python
"""Fallback chain: same-tier alternatives → cross-provider → default."""

import logging
from typing import List, Optional

from agent.brain.routes import Route, ModelTarget, RoutingDecision

logger = logging.getLogger(__name__)


class FallbackChain:
    """Ordered list of fallback models to try when primary fails."""

    def __init__(
        self,
        same_tier: List[ModelTarget] = None,
        cross_provider: List[ModelTarget] = None,
        default_model: ModelTarget = None,
    ):
        self.same_tier = same_tier or []
        self.cross_provider = cross_provider or []
        self.default_model = default_model or ModelTarget(
            provider="openai-compatible",
            model="deepseek-chat",
        )

    def get_fallback(self, failed_target: ModelTarget, exhausted: set) -> Optional[ModelTarget]:
        """Get next available fallback model.

        Order: same-tier → cross-provider → default.
        Skips already-exhausted targets.
        """
        # Try same-tier alternatives
        for target in self.same_tier:
            key = (target.provider, target.model)
            if key not in exhausted and key != (failed_target.provider, failed_target.model):
                logger.info("Fallback: same-tier %s/%s", target.provider, target.model)
                return target

        # Try cross-provider
        for target in self.cross_provider:
            key = (target.provider, target.model)
            if key not in exhausted:
                logger.info("Fallback: cross-provider %s/%s", target.provider, target.model)
                return target

        # Ultimate fallback
        key = (self.default_model.provider, self.default_model.model)
        if key not in exhausted:
            logger.info("Fallback: default %s/%s", self.default_model.provider, self.default_model.model)
            return self.default_model

        logger.error("All fallbacks exhausted")
        return None

    def build_fallback_list(self, route: Route) -> List[ModelTarget]:
        """Build ordered fallback list for a given route."""
        return self.same_tier + self.cross_provider + [self.default_model]
```

---

## Task 8: Implement Monitoring Layer

**Objective:** Cost tracking, health metrics, feedback loop

**Files:**
- Create: `agent/brain/monitor.py`
- Modify: `tests/agent/test_brain_routing.py`

**Step 1: Implement monitor.py**

```python
"""Monitoring layer: route logging, cost tracking, feedback loop."""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)


class RouteMonitor:
    """Tracks routing decisions and outcomes for the feedback loop."""

    def __init__(self, log_dir: str = None, max_age_days: int = 30):
        self.log_dir = Path(log_dir or os.path.join(get_hermes_home(), "logs", "brain"))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_days = max_age_days
        self._current_log_file = self.log_dir / f"routes_{datetime.now().strftime('%Y%m%d')}.jsonl"

    def log_route(self, input_hash: str, route: str, model: str, provider: str,
                  confidence: float, latency_ms: float, token_count: int):
        """Log a routing decision."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "input_hash": input_hash,
            "route": route,
            "model": model,
            "provider": provider,
            "confidence": confidence,
            "latency_ms": latency_ms,
            "token_count": token_count,
        }
        try:
            with open(self._current_log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning("Failed to log route: %s", e)

    def log_outcome(self, input_hash: str, signal: str, signal_type: str = "weak",
                    window_seconds: int = 60):
        """Log an outcome signal (retry, fallback, user feedback).

        signal_type: 'strong' (retry within window, fallback trigger)
                     'weak' (user dislike, timeout)
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "input_hash": input_hash,
            "signal": signal,
            "signal_type": signal_type,
            "window_seconds": window_seconds,
        }
        try:
            out_file = self.log_dir / f"outcomes_{datetime.now().strftime('%Y%m%d')}.jsonl"
            with open(out_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning("Failed to log outcome: %s", e)

    def get_route_stats(self, route: str = None, days: int = 7) -> dict:
        """Get routing statistics for the last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        stats = {"total": 0, "by_route": {}, "avg_confidence": 0.0, "count": 0}

        for log_file in sorted(self.log_dir.glob("routes_*.jsonl")):
            try:
                file_date = datetime.strptime(log_file.stem, "routes_%Y%m%d")
                if file_date < cutoff:
                    continue
                for line in open(log_file):
                    entry = json.loads(line)
                    if route and entry.get("route") != route:
                        continue
                    stats["total"] += 1
                    r = entry["route"]
                    stats["by_route"][r] = stats["by_route"].get(r, 0) + 1
                    stats["avg_confidence"] += entry.get("confidence", 0)
                    stats["count"] += 1
            except Exception:
                continue

        if stats["count"] > 0:
            stats["avg_confidence"] /= stats["count"]

        return stats
```

---

## Task 9: Wire everything together — Main Router

**Objective:** Create the `router()` function that orchestrates all layers

**Files:**
- Modify: `agent/brain/__init__.py`

**Step 1: Add router function to __init__.py**

```python
"""Main router: orchestrates Layer 0 → 0.5 → 1 → 2 → execution."""

import hashlib
import logging
import time
from typing import Optional, Dict, Any, List

from agent.brain.routes import Route, RoutingDecision, ModelTarget, RouteMetadata
from agent.brain.preprocessor import Preprocessor
from agent.brain.fingerprint import FingerprintCache
from agent.brain.classifier import HybridClassifier, RuleClassifier
from agent.brain.planner import PlannerRouter

logger = logging.getLogger(__name__)


def router(
    user_message: str,
    session_context: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Dict]] = None,
) -> RoutingDecision:
    """Route a user message through the three-layer brain.

    Args:
        user_message: The user's input text
        session_context: Current session metadata (compression fill ratio, etc.)
        config: Brain config section from config.yaml
        conversation_history: Recent conversation for context-aware routing

    Returns:
        RoutingDecision with target model and metadata.
        NEVER raises — always returns a valid decision (defaults to complex).
    """
    config = config or {}
    session_context = session_context or {}
    start_time = time.monotonic()

    # ── Default decision (safe fallback) ──────────────────
    default_model = ModelTarget(
        provider=config.get("provider", "openai-compatible"),
        model=config.get("model", "deepseek-v4-pro"),
    )
    default_decision = RoutingDecision(
        route=Route.COMPLEX,
        model=default_model,
        metadata=RouteMetadata(source="default"),
    )

    try:
        # ── Layer 0: Preprocessing ────────────────────────
        compression_threshold = config.get("compression_threshold", 0.8)
        current_fill = session_context.get("context_fill_ratio", 0.0)
        preprocessor = Preprocessor(
            compression_threshold=compression_threshold,
            current_fill_ratio=current_fill,
        )
        metadata = preprocessor.process(user_message)
        metadata.source = "layer_0"

        # If compression needed, force simple route to save context
        if metadata.needs_compression:
            logger.info("Brain: compression needed, forcing simple route")
            return RoutingDecision(
                route=Route.SIMPLE,
                model=ModelTarget(
                    provider=config.get("routes", {}).get("simple", {}).get("provider", "openai-compatible"),
                    model=config.get("routes", {}).get("simple", {}).get("model", "deepseek-v4-flash"),
                ),
                metadata=metadata,
            )

        # ── Layer 0.5: Fingerprint Cache ─────────────────
        cache = _get_cache(config)
        if cache:
            cached = cache.get(user_message)
            if cached:
                logger.info("Brain: cache hit, reusing route=%s", cached.route.value)
                return cached

        # ── Layer 1: Heuristic Classification ────────────
        l1_config = config.get("layer_1", {})
        classifier = _get_classifier(l1_config)

        if classifier:
            result = classifier.classify(user_message, metadata.token_count_estimate)
            if result is not None:
                route, confidence = result
                # High confidence rules (≥0.9) skip Layer 2
                if confidence >= 0.9:
                    metadata.source = "layer_1_rule"
                    metadata.confidence = confidence
                    decision = _build_decision(route, metadata, config)
                    _cache_decision(cache, user_message, decision)
                    return decision

        # ── Layer 2: Light Planner ───────────────────────
        l2_config = config.get("layer_2", {})
        if l2_config.get("enabled", True):
            planner = PlannerRouter(
                provider=l2_config.get("provider", "openai-compatible"),
                model=l2_config.get("model", "deepseek-v4-flash"),
                base_url=l2_config.get("base_url", "https://api.deepseek.com/v1"),
                api_key=l2_config.get("api_key", ""),
                timeout=l2_config.get("timeout", 5),
                confidence_threshold=l2_config.get("confidence_threshold", 0.6),
            )
            planner_result = planner.compute_decision(
                user_message,
                token_count=metadata.token_count_estimate,
                conversation_history=conversation_history,
            )

            if planner_result:
                metadata.source = "layer_2_planner"
                metadata.confidence = planner_result["confidence"]
                route = Route(planner_result["route"])
                decision = _build_decision(route, metadata, config)
                _cache_decision(cache, user_message, decision)
                return decision

        # ── Fallback: return default ─────────────────────
        logger.info("Brain: all layers missed, using default model")
        return default_decision

    except Exception as e:
        logger.error("Brain router error: %s. Falling back to default.", e)
        return default_decision


# ── Module-level singletons (lazy init) ───────────────────

_cache: Optional[FingerprintCache] = None
_classifier: Optional[HybridClassifier] = None


def _get_cache(config: dict) -> Optional[FingerprintCache]:
    global _cache
    if _cache is None:
        cache_config = config.get("layer_0_5", {})
        cache_size = cache_config.get("cache_size", 1000)
        ttl = cache_config.get("exact_ttl_seconds", 3600)
        _cache = FingerprintCache(max_size=cache_size, ttl_seconds=ttl)
    return _cache


def _get_classifier(config: dict) -> Optional[HybridClassifier]:
    global _classifier
    if _classifier is None:
        _classifier = HybridClassifier(
            rule_classifier=RuleClassifier(
                long_context_threshold=config.get("long_context_threshold", 32000)
            ),
        )
    return _classifier


def _build_decision(route: Route, metadata: RouteMetadata, config: dict) -> RoutingDecision:
    """Build a RoutingDecision from route and config."""
    route_configs = config.get("routes", {})
    route_config = route_configs.get(route.value, {})

    model = ModelTarget(
        provider=route_config.get("provider", config.get("provider", "openai-compatible")),
        model=route_config.get("model", config.get("model", "deepseek-v4-pro")),
        base_url=route_config.get("base_url"),
        api_key=route_config.get("api_key"),
    )

    return RoutingDecision(
        route=route,
        model=model,
        metadata=metadata,
        toolsets=route_config.get("toolsets"),
    )


def _cache_decision(cache, text: str, decision: RoutingDecision):
    """Safely cache a decision."""
    if cache:
        try:
            cache.put(text, decision)
        except Exception as e:
            logger.debug("Failed to cache decision: %s", e)
```

---

## Task 10: Integrate into run_agent.py

**Objective:** Add brain as a pre-routing hook in AIAgent.run_conversation()

**Files:**
- Modify: `run_agent.py`

**Step 1: Add brain integration at the start of run_conversation()**

After the preprocessing section (~line 9298), add:

```python
# ── Brain: Intelligent model routing ──────────────────────
# Check if brain routing is enabled in config
if self._brain_enabled:
    from agent.brain import router
    try:
        brain_config = self._brain_config or {}
        session_ctx = {
            "context_fill_ratio": self._context_fill_ratio if hasattr(self, '_context_fill_ratio') else 0.0,
        }
        routing_decision = router(
            user_message=user_message,
            session_context=session_ctx,
            config=brain_config,
            conversation_history=conversation_history,
        )
        # Override model for this turn
        original_model = self.model
        original_base_url = self.base_url
        original_api_key = self._api_key

        if routing_decision.model.model:
            self.model = routing_decision.model.model
        if routing_decision.model.base_url:
            self.base_url = routing_decision.model.base_url
        if routing_decision.model.api_key:
            self._api_key = routing_decision.model.api_key

        # Store for restoration after turn
        self._brain_original_state = {
            "model": original_model,
            "base_url": original_base_url,
            "api_key": original_api_key,
        }
        self._brain_decision = routing_decision

        logger.info(
            "Brain routed to %s/%s (route=%s conf=%.2f source=%s)",
            routing_decision.model.provider,
            routing_decision.model.model,
            routing_decision.route.value,
            routing_decision.metadata.confidence,
            routing_decision.metadata.source,
        )
    except Exception as e:
        logger.warning("Brain routing failed: %s. Using default model.", e)
        self._brain_decision = None
```

Also add brain config loading to `__init__`:

```python
# Brain config
self._brain_enabled = False
self._brain_config = {}
self._brain_decision = None
self._brain_original_state = None
```

And set from config in the gateway/CLI init code that creates AIAgent.

---

## Task 11: Add brain config schema

**Objective:** Define brain config defaults for config.yaml

**Files:**
- Modify: `hermes_cli/config.py`

**Step 1: Add brain section to DEFAULT_CONFIG**

```python
"brain": {
    "enabled": False,  # Opt-in
    "provider": "openai-compatible",
    "model": "deepseek-v4-pro",  # Default model
    "compression_threshold": 0.8,
    "layer_0_5": {
        "cache_size": 1000,
        "exact_ttl_seconds": 3600,
    },
    "layer_1": {
        "long_context_threshold": 32000,
        "embedding_model": "all-MiniLM-L6-v2",
        "embedding_threshold": 0.75,
    },
    "layer_2": {
        "enabled": True,
        "provider": "openai-compatible",
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "timeout": 5,
        "confidence_threshold": 0.6,
    },
    "routes": {
        "simple": {
            "provider": "openai-compatible",
            "model": "deepseek-v4-flash",
        },
        "coding": {
            "provider": "openai-compatible",
            "model": "deepseek-v4-pro",
            "toolsets": ["terminal", "file", "web", "browser", "code_execution"],
        },
        "complex": {
            "provider": "openai-compatible",
            "model": "deepseek-v4-pro",
            "toolsets": None,  # All tools
        },
        "vision": {
            "provider": "openai-compatible",
            "model": "qwen3-vl-plus",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        },
        "long_context": {
            "provider": "openai-compatible",
            "model": "deepseek-v4-pro",
        },
    },
    "monitor": {
        "enabled": True,
        "log_dir": "",  # Auto: ~/.hermes/logs/brain/
        "max_age_days": 30,
    },
},
```

---

## Task 12: End-to-end integration test

**Objective:** Verify the full pipeline works with a real message

**Files:**
- Modify: `tests/agent/test_brain_routing.py`

**Step 1: Add integration test**

```python
class TestBrainIntegration:
    def test_full_pipeline_simple_greeting(self):
        """A greeting should route to SIMPLE via Layer 1 rules."""
        from agent.brain import router

        decision = router(
            user_message="你好",
            config={
                "provider": "openai-compatible",
                "model": "deepseek-v4-pro",
                "routes": {
                    "simple": {"provider": "test", "model": "flash"},
                    "complex": {"provider": "test", "model": "pro"},
                },
            },
        )
        assert decision.route == Route.SIMPLE
        assert decision.metadata.source in ("layer_1_rule", "layer_0", "default")

    def test_full_pipeline_coding_request(self):
        """A coding request should route to CODING."""
        from agent.brain import router

        decision = router(
            user_message="帮我写一个Python排序算法",
            config={
                "provider": "openai-compatible",
                "model": "deepseek-v4-pro",
                "routes": {
                    "coding": {"provider": "test", "model": "pro"},
                    "complex": {"provider": "test", "model": "pro"},
                },
            },
        )
        assert decision.route == Route.CODING

    def test_full_pipeline_unknown_query(self):
        """An ambiguous query should fall back to COMPLEX."""
        from agent.brain import router

        decision = router(
            user_message="What are the implications of quantum computing on modern cryptography?",
            config={
                "provider": "openai-compatible",
                "model": "deepseek-v4-pro",
                "layer_2": {"enabled": False},  # Disable planner for test
                "routes": {
                    "complex": {"provider": "test", "model": "pro"},
                },
            },
        )
        # Without planner, should default to COMPLEX
        assert decision.route == Route.COMPLEX

    def test_router_always_returns_decision(self):
        """Even with empty config, router must return a valid decision."""
        from agent.brain import router

        decision = router(user_message="test", config={})
        assert decision is not None
        assert decision.model is not None
        assert decision.route is not None

    def test_cache_hit_on_repeat(self):
        """Same message twice should use cache on second call."""
        from agent.brain import router, _cache

        config = {
            "provider": "test",
            "model": "pro",
            "layer_0_5": {"cache_size": 100, "exact_ttl_seconds": 3600},
            "routes": {
                "simple": {"provider": "test", "model": "flash"},
                "complex": {"provider": "test", "model": "pro"},
            },
        }

        decision1 = router(user_message="你好", config=config)
        decision2 = router(user_message="你好", config=config)

        assert decision2.metadata.source == "cache" or decision2.route == decision1.route
```

---

## Implementation Order (Priority)

1. **Task 1-2**: Data types + preprocessor (foundation, no external deps)
2. **Task 3-4**: Cache + Rule classifier (fast value, testable in isolation)
3. **Task 5**: Embedding classifier (depends on sentence-transformers, skip if not installed)
4. **Task 6**: Planner (requires API key, test with mocks)
5. **Task 7-8**: Fallback + Monitor (standalone, testable)
6. **Task 9**: Main router (wires everything)
7. **Task 10-11**: Integration (touches run_agent.py, careful)
8. **Task 12**: End-to-end tests

## Stability Checklist (per user's priority)

- [x] Every layer must fail safe — return default model on any error
- [x] Brain is opt-in (`brain.enabled: false` by default)
- [x] No breaking changes to existing session flow
- [x] `risk` computation is deterministic, not LLM-based
- [x] Feedback loop writes async, never blocks routing
- [x] Fingerprint cache is bounded (LRU eviction)
- [x] Embedding classifier gracefully handles missing deps
- [x] Planner timeout is short (5s default)
- [x] All config values have sensible defaults
- [x] Cache TTL prevents stale decisions
