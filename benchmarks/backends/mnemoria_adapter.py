"""Benchmark adapter for the Mnemoria memory system.

Mnemoria is a local-first, markdown-native memory layer shipped as an npm
package that speaks MCP.  It stores notes on disk as markdown files and uses
a three-signal retrieval engine (semantic + keyword + graph / PersonalisedPageRank).

This adapter shells out to the ``mnemoria`` CLI binary so that the real plugin
behaviour is exercised during benchmarks rather than a mock.

Binary resolution order
-----------------------
1. shutil.which('mnemoria')                     -- already on PATH
2. ~/.npm-global/bin/mnemoria                   -- npm global install (default prefix)
3. ~/.local/share/npm/bin/mnemoria              -- alternative npm global prefix
4. /usr/local/bin/mnemoria                      -- system-wide install
5. npx mnemoria (fallback, slow first run)      -- run without permanent install

CLI commands used
-----------------
``mnemoria init <vault>``        Scaffold the vault directory structure.
``mnemoria add <content>``       Capture a note / fact to the vault inbox.
``mnemoria query ranked <q>``    Three-signal ranked retrieval (returns JSON).
``mnemoria health``              Validate vault + confirm binary works.

All subcommands accept ``--vault <path>`` to specify which vault to operate on,
letting each benchmark run use its own isolated temporary directory so runs
never contaminate each other.

If the binary is absent the adapter raises ``RuntimeError`` at construction
time with clear installation instructions, so failures surface early rather
than on the first API call.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, List, Optional

from benchmarks.capabilities import BackendCapabilities
from benchmarks.interface import BenchmarkableStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level exports consumed by the benchmark runner
# ---------------------------------------------------------------------------

BACKEND_NAME = "mnemoria"

BACKEND_CAPABILITIES = BackendCapabilities(
    universal_store_recall=True,
    time_simulation=False,    # Mnemoria vitality decay is real-clock-based
    access_rehearsal=False,   # No dedicated rehearsal CLI command
    consolidation=False,      # Consolidation happens automatically in the vault
    scopes=False,             # Vault spaces (self/notes/ops) differ from benchmark scopes
    typed_facts=False,
    supersession=False,
    reward_learning=False,
    exploration=False,
    turn_sync=False,
    precompress_hook=False,
    session_end_hook=False,
    delegation_hook=False,
)

# ---------------------------------------------------------------------------
# Binary resolution
# ---------------------------------------------------------------------------

_MNEMORIA_FALLBACK_PATHS: tuple[Path, ...] = (
    Path.home() / ".npm-global" / "bin" / "mnemoria",
    Path.home() / ".local" / "share" / "npm" / "bin" / "mnemoria",
    Path("/usr/local/bin/mnemoria"),
    Path("/usr/bin/mnemoria"),
)

# When set to True, fall back to ``npx mnemoria`` when no local binary exists.
# This is disabled by default because ``npx`` triggers a download on first
# use and makes cold-start benchmarks unreliable.
_ALLOW_NPX_FALLBACK: bool = False


def _resolve_mnemoria_binary() -> Optional[str]:
    """Return the absolute path to the mnemoria binary, or None if not found."""
    on_path = shutil.which("mnemoria")
    if on_path:
        return on_path
    for candidate in _MNEMORIA_FALLBACK_PATHS:
        if candidate.is_file() and shutil.os.access(candidate, shutil.os.X_OK):
            return str(candidate)
    if _ALLOW_NPX_FALLBACK:
        npx = shutil.which("npx")
        if npx:
            return None  # handled separately by _run()
    return None


def _is_mnemoria_available() -> bool:
    """Return True if the mnemoria binary can be located on this system."""
    return _resolve_mnemoria_binary() is not None


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class MnemoriaBenchmarkAdapter(BenchmarkableStore):
    """Adapter exposing the Mnemoria CLI through BenchmarkableStore.

    Each adapter instance owns an isolated temporary vault directory.  The
    vault is initialised via ``mnemoria init`` at construction time and torn
    down (``reset()`` or ``__del__``) afterwards.

    Parameters
    ----------
    vault_path:
        Optional path to an existing vault.  When omitted a fresh temporary
        directory is created so multiple benchmark runs remain independent.
    timeout_store:
        Subprocess timeout (seconds) for ``mnemoria add`` calls.  Defaults to
        60 s because the first add in a new vault triggers embedding model
        download.
    timeout_recall:
        Subprocess timeout (seconds) for ``mnemoria query`` calls.
    """

    def __init__(
        self,
        vault_path: Optional[str] = None,
        timeout_store: int = 60,
        timeout_recall: int = 30,
        **kwargs,
    ) -> None:
        binary = _resolve_mnemoria_binary()
        if binary is None:
            raise RuntimeError(
                "Mnemoria binary not found.  Install it with:\n"
                "  npm install -g mnemoria\n"
                "Then verify with: mnemoria health\n"
                "Searched: PATH, ~/.npm-global/bin, ~/.local/share/npm/bin, "
                "/usr/local/bin, /usr/bin."
            )
        self._binary: str = binary
        self._timeout_store: int = timeout_store
        self._timeout_recall: int = timeout_recall

        # Vault lifecycle
        if vault_path:
            self._vault = Path(vault_path)
            self._vault.mkdir(parents=True, exist_ok=True)
            self._owned_tempdir = None
        else:
            self._owned_tempdir = tempfile.TemporaryDirectory(
                prefix="mnemoria-bench-"
            )
            self._vault = Path(self._owned_tempdir.name)

        self._store_count: int = 0
        self._init_vault()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(
        self,
        args: List[str],
        *,
        timeout: int = 30,
        check: bool = True,
        capture: bool = False,
    ) -> subprocess.CompletedProcess:
        """Run mnemoria with ``--vault`` injected and return CompletedProcess."""
        cmd = [self._binary, "--vault", str(self._vault)] + args
        return subprocess.run(
            cmd,
            timeout=timeout,
            check=check,
            capture_output=capture,
            text=True,
        )

    def _init_vault(self) -> None:
        """Initialise the vault by running ``mnemoria init``."""
        try:
            # ``mnemoria init`` is idempotent — safe to call on existing vaults.
            self._run(["init", str(self._vault)], timeout=60, check=True)
            logger.debug("Mnemoria vault initialised at %s", self._vault)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"mnemoria init failed (exit {exc.returncode}).  "
                "Make sure the mnemoria binary is functional and try "
                "'mnemoria health'."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "mnemoria init timed out.  The binary may be hanging on first "
                "use while downloading the embedding model.  "
                "Try running 'mnemoria health' manually first."
            ) from exc

    def _parse_ranked_output(self, stdout: str, top_k: int) -> List[str]:
        """Parse ``mnemoria query ranked`` stdout into a list of content strings.

        The command returns a JSON array of result objects.  Each object has at
        least a ``content`` key (the note body) and optionally ``title`` and
        ``score``.  We return the content strings ranked by the order Mnemoria
        already provides.

        Falls back to line-splitting when the output is not valid JSON (e.g.
        older CLI versions that emit plain text).
        """
        text = stdout.strip()
        if not text:
            return []
        # Try JSON array first
        if text.startswith("["):
            try:
                items = json.loads(text)
                results: List[str] = []
                for item in items[:top_k]:
                    if isinstance(item, dict):
                        # Prefer explicit content field; fall back to title
                        content = item.get("content") or item.get("title") or ""
                        if content:
                            results.append(str(content).strip())
                    elif isinstance(item, str):
                        results.append(item.strip())
                return results
            except json.JSONDecodeError:
                pass
        # Try JSON object with a results array
        if text.startswith("{"):
            try:
                obj = json.loads(text)
                items = obj.get("results") or obj.get("items") or []
                results = []
                for item in items[:top_k]:
                    if isinstance(item, dict):
                        content = item.get("content") or item.get("title") or ""
                        if content:
                            results.append(str(content).strip())
                return results
            except json.JSONDecodeError:
                pass
        # Plain-text fallback: one result per non-empty line
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return lines[:top_k]

    # ------------------------------------------------------------------
    # BenchmarkableStore interface
    # ------------------------------------------------------------------

    def store(
        self,
        content: str,
        category: str = "factual",
        scope: str = "global",
        importance: float = 0.5,
    ) -> None:
        """Capture *content* into the Mnemoria vault via ``mnemoria add``.

        Parameters
        ----------
        content:
            The text to remember.
        category:
            Semantic category tag.  Passed as-is for interface compatibility;
            Mnemoria routes notes internally based on content analysis.
        scope:
            Scope tag (``"global"``, ``"session"``, …).  Ignored because
            Mnemoria organises storage across its own vault spaces (self /
            notes / ops) rather than arbitrary scope strings.
        importance:
            Salience weight in [0, 1].  Ignored; Mnemoria computes vitality
            from access patterns and structural links.
        """
        del category, scope, importance  # unused by this backend
        try:
            self._run(
                ["add", content],
                timeout=self._timeout_store,
                check=True,
            )
            self._store_count += 1
        except subprocess.CalledProcessError as exc:
            logger.warning(
                "mnemoria add failed (exit %d): %s", exc.returncode, exc.stderr
            )
        except subprocess.TimeoutExpired:
            logger.warning("mnemoria add timed out for content: %.80s…", content)

    def recall(
        self,
        query: str,
        top_k: int = 10,
        scope: Optional[str] = None,
    ) -> List[str]:
        """Retrieve memories matching *query* using three-signal ranked search.

        Uses ``mnemoria query ranked`` which fuses semantic embeddings, BM25
        keyword scoring, and Personalised PageRank into a single ranked list.

        Parameters
        ----------
        query:
            Natural-language search string.
        top_k:
            Maximum number of results to return.
        scope:
            Optional scope filter.  Ignored because Mnemoria does not expose
            benchmark-level scoping via its CLI.
        """
        del scope  # unused by this backend
        try:
            result = self._run(
                ["query", "ranked", query, "--limit", str(top_k)],
                timeout=self._timeout_recall,
                check=False,
                capture=True,
            )
            return self._parse_ranked_output(result.stdout, top_k)
        except subprocess.TimeoutExpired:
            logger.warning("mnemoria query timed out for query: %.80s…", query)
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning("mnemoria query failed: %s", exc)
            return []

    def simulate_time(self, days: float) -> None:
        """No-op — Mnemoria vitality decay is tied to the real-world clock.

        Parameters
        ----------
        days:
            Number of days to advance (ignored).
        """
        del days
        return None

    def simulate_access(self, content_substring: str) -> None:
        """No-op — Mnemoria has no dedicated rehearsal CLI command.

        Vitality boosts happen automatically when notes are retrieved via
        ``mnemoria query ranked`` (activation spreading), not via an explicit
        rehearsal API.

        Parameters
        ----------
        content_substring:
            Substring identifying the memory to rehearse (ignored).
        """
        del content_substring
        return None

    def consolidate(self) -> None:
        """No-op — Mnemoria consolidates notes automatically in the background.

        The ACT-R vitality model and Hebbian link weights are maintained
        incrementally on every access rather than through an explicit
        consolidation cycle.
        """
        return None

    def get_stats(self) -> dict[str, Any]:
        """Return basic adapter statistics.

        Returns
        -------
        dict
            Contains ``backend`` name, ``vault`` path, and ``store_count``
            (number of successful ``store()`` calls since last ``reset()``).
            A ``health`` key is included when ``mnemoria health`` succeeds.
        """
        stats: dict[str, Any] = {
            "backend": BACKEND_NAME,
            "vault": str(self._vault),
            "store_count": self._store_count,
        }
        try:
            result = self._run(
                ["health"],
                timeout=15,
                check=False,
                capture=True,
            )
            stats["health"] = result.stdout.strip() or "ok"
        except Exception:  # noqa: BLE001
            stats["health"] = "unavailable"
        return stats

    def reset(self) -> None:
        """Clear all stored memories by re-initialising the vault.

        All markdown notes and the embedding database inside the vault
        directory are removed and a fresh vault is scaffolded in their place.
        The ``store_count`` counter is reset to zero.
        """
        # Wipe vault contents
        errors: list[str] = []
        for child in list(self._vault.iterdir()):
            try:
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{child}: {exc}")
        if errors:
            logger.warning(
                "mnemoria reset: could not remove some vault entries:\n%s",
                "\n".join(errors),
            )
        self._store_count = 0
        self._init_vault()

    def __del__(self) -> None:
        tempdir = getattr(self, "_owned_tempdir", None)
        if tempdir is not None:
            try:
                tempdir.cleanup()
            except Exception:  # noqa: BLE001
                pass


# Module-level alias consumed by the benchmark runner's dynamic loader.
BACKEND_CLASS = MnemoriaBenchmarkAdapter
