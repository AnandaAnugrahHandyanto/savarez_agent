"""Shared file safety rules used by both tools and ACP shims."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import Optional


def _hermes_home_path() -> Path:
    """Resolve the active HERMES_HOME (profile-aware) without circular imports."""
    try:
        from hermes_constants import get_hermes_home  # local import to avoid cycles
        return get_hermes_home()
    except Exception:
        return Path(os.path.expanduser("~/.hermes"))


def build_write_denied_paths(home: str) -> set[str]:
    """Return exact sensitive paths that must never be written."""
    hermes_home = _hermes_home_path()
    return {
        os.path.realpath(p)
        for p in [
            os.path.join(home, ".ssh", "authorized_keys"),
            os.path.join(home, ".ssh", "id_rsa"),
            os.path.join(home, ".ssh", "id_ed25519"),
            os.path.join(home, ".ssh", "config"),
            str(hermes_home / ".env"),
            os.path.join(home, ".bashrc"),
            os.path.join(home, ".zshrc"),
            os.path.join(home, ".profile"),
            os.path.join(home, ".bash_profile"),
            os.path.join(home, ".zprofile"),
            os.path.join(home, ".netrc"),
            os.path.join(home, ".pgpass"),
            os.path.join(home, ".npmrc"),
            os.path.join(home, ".pypirc"),
            "/etc/sudoers",
            "/etc/passwd",
            "/etc/shadow",
        ]
    }


def build_write_denied_prefixes(home: str) -> list[str]:
    """Return sensitive directory prefixes that must never be written."""
    return [
        os.path.realpath(p) + os.sep
        for p in [
            os.path.join(home, ".ssh"),
            os.path.join(home, ".aws"),
            os.path.join(home, ".gnupg"),
            os.path.join(home, ".kube"),
            "/etc/sudoers.d",
            "/etc/systemd",
            os.path.join(home, ".docker"),
            os.path.join(home, ".azure"),
            os.path.join(home, ".config", "gh"),
        ]
    ]


def get_safe_write_root() -> Optional[str]:
    """Return the resolved HERMES_WRITE_SAFE_ROOT path, or None if unset."""
    root = os.getenv("HERMES_WRITE_SAFE_ROOT", "")
    if not root:
        return None
    try:
        return os.path.realpath(os.path.expanduser(root))
    except Exception:
        return None


def is_write_denied(path: str) -> bool:
    """Return True if path is blocked by the write denylist or safe root."""
    home = os.path.realpath(os.path.expanduser("~"))
    resolved = os.path.realpath(os.path.expanduser(str(path)))

    if resolved in build_write_denied_paths(home):
        return True
    for prefix in build_write_denied_prefixes(home):
        if resolved.startswith(prefix):
            return True

    safe_root = get_safe_write_root()
    if safe_root and not (resolved == safe_root or resolved.startswith(safe_root + os.sep)):
        return True

    return False


_SAFE_ENV_EXAMPLE_SUFFIXES = (
    ".example",
    ".sample",
    ".template",
    ".tmpl",
    ".dist",
    ".default",
    ".defaults",
    ".mock",
)

_SENSITIVE_HOME_FILES = (
    ".xurl",
    ".netrc",
    ".pgpass",
    ".npmrc",
    ".pypirc",
)

_SENSITIVE_HOME_DIRS = (
    ".ssh",
    ".aws",
    ".gnupg",
    ".kube",
    ".docker",
    ".azure",
    os.path.join(".config", "gh"),
    os.path.join(".config", "gcloud"),
)

_TERMINAL_SECRET_READ_VERBS = frozenset({
    "awk",
    "base64",
    "bat",
    "cat",
    "cp",
    "curl",
    "dd",
    "grep",
    "head",
    "hexdump",
    "jq",
    "less",
    "more",
    "node",
    "openssl",
    "perl",
    "php",
    "python",
    "python3",
    "rg",
    "rsync",
    "ruby",
    "scp",
    "sed",
    "strings",
    "tail",
    "tac",
    "wget",
    "xxd",
    "yq",
})

_ENV_DUMP_RE = re.compile(r"(?:^|[;&|]\s*)(?:(?:/usr/bin|/bin)/)?(?:env|printenv)(?:\s+(?:-[A-Za-z0-9-]+))*\s*(?:$|[;&|])")

_SEARCH_SCAN_SKIP_DIRS = frozenset({
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "dist",
    "build",
})
_SENSITIVE_SEARCH_DIR_NAMES = frozenset({".ssh", ".aws", ".gnupg", ".kube", ".docker", ".azure"})
_SHELL_EVAL_VERBS = frozenset({"bash", "dash", "fish", "ksh", "sh", "zsh"})
_COMMAND_WRAPPER_VERBS = frozenset({"command", "env", "nice", "timeout"})
_VERSIONED_READ_VERB_RE = re.compile(r"^(?:python(?:\d+(?:\.\d+)*)?|pypy\d*|nodejs)$")


def _resolve_path(path: str | os.PathLike[str]) -> Path:
    """Resolve a path for safety checks without requiring it to exist."""
    return Path(path).expanduser().resolve()


def _home_path() -> Path:
    return _resolve_path(os.path.expanduser("~"))


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_secret_env_filename(name: str) -> bool:
    """Return True for real env files, while allowing examples/templates."""
    lower = name.lower()
    if lower.endswith(_SAFE_ENV_EXAMPLE_SUFFIXES):
        return False
    return lower == ".env" or lower.startswith(".env.")


def _directory_contains_sensitive_read_target(root: Path, max_entries: int = 20_000) -> bool:
    """Return True when a directory tree contains obvious secret filenames.

    This only inspects path names, never file contents. It is intentionally
    bounded so ordinary searches do not become expensive on huge trees; known
    credential roots are handled by exact descendant checks before this scan.
    """
    if not root.is_dir():
        return False

    seen = 0
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            if any(name in _SENSITIVE_SEARCH_DIR_NAMES for name in dirnames):
                return True

            path = Path(dirpath)
            if path.name == ".config" and any(name in {"gh", "gcloud"} for name in dirnames):
                return True

            dirnames[:] = [name for name in dirnames if name not in _SEARCH_SCAN_SKIP_DIRS]
            if any(_is_secret_env_filename(name) for name in filenames):
                return True

            seen += len(dirnames) + len(filenames)
            if seen > max_entries:
                return True
    except OSError:
        return True

    return False


def _sensitive_exact_read_paths(home: Path, hermes_home: Path) -> set[Path]:
    return {
        hermes_home / ".env",
        hermes_home / "auth.json",
        hermes_home / "config.yaml",
        *(home / name for name in _SENSITIVE_HOME_FILES),
    }


def _sensitive_dir_read_paths(home: Path, hermes_home: Path) -> list[Path]:
    return [
        hermes_home / "secrets",
        *(home / rel for rel in _SENSITIVE_HOME_DIRS),
    ]


def _sensitive_read_block_error(path: str) -> Optional[str]:
    """Return an error when a read targets local credential material."""
    resolved = _resolve_path(path)
    home = _home_path()
    hermes_home = _hermes_home_path().resolve()

    if resolved in _sensitive_exact_read_paths(home, hermes_home):
        return (
            f"Access denied: {path} is a sensitive credential/configuration "
            "file and cannot be read directly. Use a purpose-built helper that "
            "prints only redacted, task-specific metadata."
        )

    for sensitive_dir in _sensitive_dir_read_paths(home, hermes_home):
        if _is_relative_to(resolved, sensitive_dir):
            return (
                f"Access denied: {path} is inside a sensitive credential "
                "directory and cannot be read directly. Use a redacted, "
                "purpose-built helper instead."
            )

    if _is_secret_env_filename(resolved.name):
        return (
            f"Access denied: {path} looks like a sensitive credential .env "
            "file and cannot be read directly. Example/template env files are "
            "allowed; real env files require a redacted helper."
        )

    return None


def get_search_block_error(path: str) -> Optional[str]:
    """Return an error when a recursive/content search targets credential roots."""
    direct_error = get_read_block_error(path)
    if direct_error:
        return direct_error

    resolved = _resolve_path(path)
    home = _home_path()
    hermes_home = _hermes_home_path().resolve()
    sensitive_descendants = [
        *_sensitive_exact_read_paths(home, hermes_home),
        *_sensitive_dir_read_paths(home, hermes_home),
    ]
    for sensitive_path in sensitive_descendants:
        if _is_relative_to(sensitive_path, resolved):
            return (
                f"Access denied: {path} contains sensitive credential stores "
                "and cannot be searched recursively. Search a narrower "
                "non-sensitive subdirectory or use a redacted helper."
            )

    if _directory_contains_sensitive_read_target(resolved):
        return (
            f"Access denied: {path} contains sensitive credential-like files "
            "and cannot be searched recursively. Search a narrower "
            "non-sensitive subdirectory or use a redacted helper."
        )

    return None


def get_read_block_error(path: str) -> Optional[str]:
    """Return an error message when a read targets unsafe local files."""
    sensitive_error = _sensitive_read_block_error(path)
    if sensitive_error:
        return sensitive_error

    resolved = _resolve_path(path)
    hermes_home = _hermes_home_path().resolve()
    blocked_dirs = [
        hermes_home / "skills" / ".hub" / "index-cache",
        hermes_home / "skills" / ".hub",
    ]
    for blocked in blocked_dirs:
        if _is_relative_to(resolved, blocked):
            return (
                f"Access denied: {path} is an internal Hermes cache file "
                "and cannot be read directly to prevent prompt injection. "
                "Use the skills_list or skill_view tools instead."
            )
    return None


def _command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return re.split(r"\s+", command)


def _normalize_shell_path_token(token: str) -> str:
    """Expand shell-ish home variables in a token without consulting secrets."""
    home = str(_home_path())
    hermes_home = str(_hermes_home_path().resolve())
    normalized = (
        token.replace("${HERMES_HOME}", hermes_home)
        .replace("$HERMES_HOME", hermes_home)
        .replace("${HOME}", home)
        .replace("$HOME", home)
    )
    if normalized.startswith("~"):
        normalized = normalized.replace("~", home, 1)
    compact = normalized.strip("'\"` ,;()[]{}<>")
    if compact.startswith("@"):
        compact = compact[1:]
    return compact


def _resolve_shell_path_token(token: str, cwd: str | os.PathLike[str] | None = None) -> Path | None:
    """Resolve a possible shell path token relative to cwd, if it looks usable."""
    compact = _normalize_shell_path_token(token)
    if not compact or compact.startswith("-"):
        return None
    # Skip common assignment tokens (`FOO=bar command`) and option payloads.
    if "=" in compact and not compact.startswith(("/", ".", "~")):
        return None
    try:
        candidate = Path(compact).expanduser()
        if not candidate.is_absolute():
            base = _resolve_path(cwd) if cwd else Path.cwd().resolve()
            candidate = base / candidate
        return candidate.resolve()
    except (OSError, RuntimeError, ValueError):
        return None


def _token_mentions_sensitive_path(token: str, cwd: str | os.PathLike[str] | None = None) -> bool:
    """Best-effort detection of credential path references in shell tokens."""
    if not token:
        return False

    home = str(_home_path())
    hermes_home = str(_hermes_home_path().resolve())
    compact = _normalize_shell_path_token(token)

    if "=" in compact:
        value = compact.split("=", 1)[1]
        if value and _token_mentions_sensitive_path(value, cwd=cwd):
            return True

    sensitive_fragments = [
        f"{hermes_home}/.env",
        f"{hermes_home}/auth.json",
        f"{hermes_home}/config.yaml",
        f"{hermes_home}/secrets/",
        f"{home}/.xurl",
        f"{home}/.netrc",
        f"{home}/.pgpass",
        f"{home}/.npmrc",
        f"{home}/.pypirc",
        f"{home}/.ssh/",
        f"{home}/.aws/",
        f"{home}/.gnupg/",
        f"{home}/.kube/",
        f"{home}/.docker/",
        f"{home}/.azure/",
        f"{home}/.config/gh/",
        f"{home}/.config/gcloud/",
    ]
    if any(fragment in compact for fragment in sensitive_fragments):
        return True

    resolved = _resolve_shell_path_token(compact, cwd=cwd)
    if resolved is not None and get_search_block_error(str(resolved)):
        return True

    # Bare project env-file reads such as `cat .env` or code strings like
    # `open('.env.local')` are common prompt-injection targets.
    for match in re.finditer(r"(?<![\w.-])\.env(?:\.[A-Za-z0-9_-]+)*(?![\w.-])", compact):
        if _is_secret_env_filename(match.group(0)):
            return True

    return False


def _command_uses_secret_read_verb(tokens: list[str]) -> bool:
    for token in tokens:
        base = os.path.basename(token)
        if base in _TERMINAL_SECRET_READ_VERBS or _VERSIONED_READ_VERB_RE.match(base):
            return True
    return False


def _split_shell_segments(command: str) -> list[str]:
    """Split simple shell command chains while preserving quoted separators."""
    segments: list[str] = []
    current: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(command):
        ch = command[i]
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
            elif ch == "\\" and i + 1 < len(command):
                i += 1
                current.append(command[i])
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            current.append(ch)
            i += 1
            continue
        if command.startswith("&&", i) or command.startswith("||", i):
            segment = "".join(current).strip()
            if segment:
                segments.append(segment)
            current = []
            i += 2
            continue
        if ch == ";" or ch in "\n\r":
            segment = "".join(current).strip()
            if segment:
                segments.append(segment)
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    segment = "".join(current).strip()
    if segment:
        segments.append(segment)
    return segments or [command]


def _update_cwd_from_cd(tokens: list[str], cwd: Path) -> Path:
    if not tokens or tokens[0] != "cd":
        return cwd
    # `cd` with no operand returns home; ignore flags/complex expansions.
    target = tokens[1] if len(tokens) > 1 else str(_home_path())
    resolved = _resolve_shell_path_token(target, cwd=cwd)
    return resolved if resolved is not None else cwd


def _iter_embedded_shell_commands(command: str) -> list[str]:
    """Extract command substitution payloads for recursive scanning."""
    embedded: list[str] = []
    i = 0
    while i < len(command):
        if command.startswith("$(", i):
            start = i + 2
            depth = 1
            quote: str | None = None
            j = start
            while j < len(command):
                ch = command[j]
                if quote:
                    if ch == quote:
                        quote = None
                    elif ch == "\\" and j + 1 < len(command):
                        j += 1
                    j += 1
                    continue
                if ch in ("'", '"'):
                    quote = ch
                elif command.startswith("$(", j):
                    depth += 1
                    j += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        embedded.append(command[start:j])
                        i = j
                        break
                j += 1
        elif command[i] == "`":
            j = i + 1
            while j < len(command):
                if command[j] == "`":
                    embedded.append(command[i + 1:j])
                    i = j
                    break
                if command[j] == "\\" and j + 1 < len(command):
                    j += 1
                j += 1
        i += 1
    return embedded


def _extract_shell_c_payload(tokens: list[str]) -> str | None:
    if not tokens or os.path.basename(tokens[0]) not in _SHELL_EVAL_VERBS:
        return None
    for idx, token in enumerate(tokens[1:], start=1):
        if token == "--":
            break
        if token == "-c" or (token.startswith("-") and "c" in token and not token.startswith("--")):
            if idx + 1 < len(tokens):
                return tokens[idx + 1]
            return None
    return None


def _unwrap_command_wrappers(tokens: list[str]) -> list[str] | None:
    """Return the real command after common benign launcher wrappers."""
    if not tokens:
        return None
    base = os.path.basename(tokens[0])
    if base not in _COMMAND_WRAPPER_VERBS:
        return None

    if base == "command":
        idx = 1
        while idx < len(tokens) and tokens[idx].startswith("-"):
            idx += 1
        return tokens[idx:] or None

    if base == "env":
        idx = 1
        while idx < len(tokens):
            token = tokens[idx]
            if token == "--":
                idx += 1
                break
            if token == "-S" and idx + 1 < len(tokens):
                return _command_tokens(tokens[idx + 1]) + tokens[idx + 2:]
            if token.startswith("-"):
                idx += 1
                continue
            if "=" in token and not token.startswith(("/", ".", "~")):
                idx += 1
                continue
            break
        return tokens[idx:] or None

    if base == "nice":
        idx = 1
        while idx < len(tokens):
            token = tokens[idx]
            if token == "-n" and idx + 1 < len(tokens):
                idx += 2
                continue
            if token.startswith("-"):
                idx += 1
                continue
            break
        return tokens[idx:] or None

    if base == "timeout":
        idx = 1
        while idx < len(tokens) and tokens[idx].startswith("-"):
            # Options may have a following value. This is conservative; if we
            # skip too little, the recursive scan just sees a harmless token.
            idx += 1
        if idx < len(tokens):
            idx += 1  # duration
        return tokens[idx:] or None

    return None


def _command_recursively_searches_cwd(tokens: list[str]) -> bool:
    if not tokens:
        return False
    base = os.path.basename(tokens[0])
    if base == "grep":
        return any(
            token in {"-R", "-r", "--recursive", "--dereference-recursive"}
            or (token.startswith("-") and not token.startswith("--") and any(ch in token for ch in "Rr"))
            for token in tokens[1:]
        )
    if base == "rg":
        return any(
            token in {"--hidden", "--unrestricted", "-u", "-uu", "-uuu"}
            for token in tokens[1:]
        )
    return False


def get_terminal_read_block_error(
    command: str,
    cwd: str | os.PathLike[str] | None = None,
    _depth: int = 0,
) -> Optional[str]:
    """Return an error when a shell command appears to read local secrets.

    This is a guardrail for obvious prompt-injection/exfiltration attempts. It
    is intentionally conservative and complements, rather than replaces,
    running untrusted web/X automations with restricted toolsets.
    """
    if not isinstance(command, str):
        return None

    stripped = command.strip()
    if not stripped:
        return None

    if _ENV_DUMP_RE.search(stripped):
        return (
            "Access denied: this command would dump process environment "
            "variables, which may include sensitive credentials. Request only "
            "specific non-secret variables or use a redacted helper."
        )

    current_cwd = _resolve_path(cwd) if cwd else Path.cwd().resolve()

    if _depth < 4:
        for embedded in _iter_embedded_shell_commands(stripped):
            embedded_error = get_terminal_read_block_error(embedded, cwd=current_cwd, _depth=_depth + 1)
            if embedded_error:
                return embedded_error

    whole_tokens = _command_tokens(stripped)
    if _command_uses_secret_read_verb(whole_tokens) and any(
        _token_mentions_sensitive_path(token, cwd=current_cwd) for token in whole_tokens
    ):
        return (
            "Access denied: this command appears to read or exfiltrate a "
            "sensitive credential file. Use a redacted, purpose-built helper "
            "instead of reading credential stores directly."
        )

    for segment in _split_shell_segments(stripped):
        tokens = _command_tokens(segment)
        if not tokens:
            continue
        unwrapped = _unwrap_command_wrappers(tokens)
        if unwrapped is not None and _depth < 4:
            wrapper_error = get_terminal_read_block_error(shlex.join(unwrapped), cwd=current_cwd, _depth=_depth + 1)
            if wrapper_error:
                return wrapper_error
            tokens = unwrapped
        shell_payload = _extract_shell_c_payload(tokens)
        if shell_payload is not None and _depth < 4:
            shell_error = get_terminal_read_block_error(shell_payload, cwd=current_cwd, _depth=_depth + 1)
            if shell_error:
                return shell_error
        if tokens[0] == "cd":
            current_cwd = _update_cwd_from_cd(tokens, current_cwd)
            continue
        if _command_recursively_searches_cwd(tokens) and get_search_block_error(str(current_cwd)):
            return (
                "Access denied: this recursive search command would scan a "
                "directory containing sensitive credential files. Search a "
                "narrower non-sensitive path or use a redacted helper."
            )
        if not _command_uses_secret_read_verb(tokens):
            continue
        if any(_token_mentions_sensitive_path(token, cwd=current_cwd) for token in tokens):
            return (
                "Access denied: this command appears to read or exfiltrate a "
                "sensitive credential file. Use a redacted, purpose-built helper "
                "instead of reading credential stores directly."
            )

    return None
