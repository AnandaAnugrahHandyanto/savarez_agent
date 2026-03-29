# Windows QoL Phase 5 — Implementation Handoff

> Spawned from a swarm research session on 2026-03-28. Research covered 27 topics across
> clipboard, security, UX, packaging, networking, and tooling. This handoff focuses on
> the top 5 highest-ROI items only. Implement them in order — each is independent.

---

## Context

Branch: `windows-qol-v2` (fork: claudlos/hermes-agent)
Repo: /c/Users/Carlos/hermes-agent
Venv: ~/hermes-venv (editable install, Linux)
Native Windows Python: C:\Users\Carlos\AppData\Local\Programs\Python\Python313\

Phases 1-4 are complete. All crash fixes, security hardening, feature parity, and polish
work is done. This phase adds 5 targeted improvements discovered via research.

CRITICAL — before touching any file, sweep for logout corruption artifacts:
  grep -rn "logout" --include="*.py" hermes_cli/ tools/ | grep -v "#" | grep -v "'logout'" | grep -v '"logout"' | grep -v "_logout"

If hits appear, fix before editing. See hermes-windows-development skill for the fix script.

Also verify the active install:
  source ~/hermes-venv/bin/activate
  python3 -c "import hermes_cli.clipboard; print(hermes_cli.clipboard.__file__)"
  # Should print /c/Users/Carlos/hermes-agent/hermes_cli/clipboard.py

---

## Task 1 — CF_PNG clipboard format priority

**Why:** Chrome, Firefox, Word, and Snipping Tool all place CF_PNG on the clipboard when
copying images. CF_PNG preserves alpha channels losslessly. Our current code checks
CF_DIBV5 > CF_DIB > CF_BITMAP but skips CF_PNG entirely, resulting in degraded quality
or missing transparency on every browser screenshot paste.

**File:** hermes_cli/clipboard.py

**Current logic (has_clipboard_image):**
  Checks: CF_BITMAP (2), CF_DIB (8), CF_DIBV5 (17)

**New logic:**
  1. Register the "PNG" custom clipboard format at module load
  2. Check it first in has_clipboard_image() and save_clipboard_image()
  3. If CF_PNG is available, read the raw bytes directly — no DIB conversion needed

**Step 1: Add the format registration at the top of clipboard.py (after the CF_ constants)**

```python
# Custom registered formats (Windows)
# These must be registered at runtime — the IDs vary per Windows session
def _get_cf_png():
    """Get the clipboard format ID for PNG (registered by Chrome/Firefox/Word)."""
    if sys.platform != "win32":
        return None
    try:
        return ctypes.windll.user32.RegisterClipboardFormatW("PNG")
    except Exception:
        return None

_CF_PNG: int | None = _get_cf_png()  # None on non-Windows
```

Place this after the existing `CF_UNICODETEXT = 13` constant block.

**Step 2: Update has_clipboard_image() to check CF_PNG first**

In the `win32` branch of `has_clipboard_image()`, change the IsClipboardFormatAvailable
block to:

```python
# Check CF_PNG first (Chrome/Firefox/Word store alpha-correct PNG here)
if _CF_PNG and u32.IsClipboardFormatAvailable(_CF_PNG):
    return True
# Fall back to DIB formats
for fmt in (CF_DIBV5, CF_DIB, CF_BITMAP):
    if u32.IsClipboardFormatAvailable(fmt):
        return True
return False
```

**Step 3: Update save_clipboard_image() to extract CF_PNG when available**

In the `win32` branch of `save_clipboard_image()`, before the existing PowerShell
DIB-extraction path, add:

```python
# Try CF_PNG first — direct bytes, no PowerShell needed
if _CF_PNG and u32.IsClipboardFormatAvailable(_CF_PNG):
    try:
        u32.OpenClipboard(0)
        h = k32.GetClipboardData(_CF_PNG)
        if h:
            size = k32.GlobalSize(h)
            ptr = k32.GlobalLock(h)
            if ptr and size:
                data = ctypes.string_at(ptr, size)
                k32.GlobalUnlock(h)
                u32.CloseClipboard()
                dest.write_bytes(data)
                return True
            k32.GlobalUnlock(h)
        u32.CloseClipboard()
    except Exception:
        try:
            u32.CloseClipboard()
        except Exception:
            pass
        # Fall through to PowerShell/DIB path below
```

You'll need `k32.GlobalSize.restype = ctypes.c_size_t` in the `_configure_win32_api()`
function. Add it alongside the existing GlobalLock declaration.

**Step 4: Write tests**

File: tests/tools/test_clipboard.py
Add a new Level 9 section at the bottom:

```python
class TestCFPngFormat:
    """T9: CF_PNG custom format registration and priority."""

    def test_cf_png_registered_on_windows(self):
        """_CF_PNG should be a non-zero int on Windows, None elsewhere."""
        if sys.platform == "win32":
            assert clipboard._CF_PNG is not None
            assert isinstance(clipboard._CF_PNG, int)
            assert clipboard._CF_PNG > 0
        else:
            assert clipboard._CF_PNG is None

    def test_has_image_checks_cf_png_first(self):
        """CF_PNG availability should short-circuit DIB checks."""
        if sys.platform != "win32":
            pytest.skip("Windows only")
        with patch.object(clipboard, "_CF_PNG", 49161):  # fake registered ID
            with patch.object(clipboard._u32, "IsClipboardFormatAvailable",
                              side_effect=lambda fmt: fmt == 49161) as mock_avail:
                result = clipboard.has_clipboard_image()
        assert result is True
        # CF_PNG was checked — if it returned True we never reached DIB formats
        first_call_fmt = mock_avail.call_args_list[0][0][0]
        assert first_call_fmt == 49161

    def test_save_image_uses_cf_png_bytes_directly(self, tmp_path):
        """When CF_PNG available, save_clipboard_image writes bytes without PowerShell."""
        if sys.platform != "win32":
            pytest.skip("Windows only")
        dest = tmp_path / "out.png"
        fake_png = b"\\x89PNG\\r\\n\\x1a\\n" + b"\\x00" * 20
        with patch.object(clipboard, "_CF_PNG", 49161):
            with patch.object(clipboard._u32, "IsClipboardFormatAvailable",
                              return_value=True):
                with patch.object(clipboard._u32, "OpenClipboard", return_value=1):
                    with patch.object(clipboard._k32, "GetClipboardData",
                                      return_value=0x1000):
                        with patch.object(clipboard._k32, "GlobalSize",
                                          return_value=len(fake_png)):
                            with patch.object(clipboard._k32, "GlobalLock",
                                              return_value=0x2000):
                                with patch("ctypes.string_at",
                                           return_value=fake_png):
                                    result = clipboard.save_clipboard_image(dest)
        assert result is True
        assert dest.read_bytes() == fake_png
```

**Step 5: Verify**

```bash
cd /c/Users/Carlos/hermes-agent
source ~/hermes-venv/bin/activate
python3 -m pytest tests/tools/test_clipboard.py -o "addopts=" -q -k "TestCFPng"
python3 -c "import py_compile; py_compile.compile('hermes_cli/clipboard.py', doraise=True); print('OK')"
```

**Step 6: Commit**

```bash
git add hermes_cli/clipboard.py tests/tools/test_clipboard.py
git commit -m "feat(clipboard): check CF_PNG format first for lossless alpha-correct image paste"
```

---

## Task 2 — $ENV{VAR} substitution in config.yaml

**Why:** MCP server configs embed API keys as plaintext in config.yaml. This is a known
security gap from the Phase 2 audit. Supporting ${MY_API_KEY} variable references lets
users store secrets in environment variables instead of the config file.

**File:** hermes_cli/config.py

**Syntax to support:** ${VAR_NAME} — standard shell-compatible, most widely understood.
Leave unresolved references as-is (don't raise, don't substitute empty string).

**Step 1: Write the substitution helper**

Add this function in config.py after the imports:

```python
import re as _re

def _expand_env_vars(value: object) -> object:
    """Recursively expand ${VAR} references in config strings.

    Leaves ${MISSING_VAR} as-is if the variable is not set.
    Only processes str values; dicts and lists are walked recursively.
    """
    if isinstance(value, str):
        return _re.sub(
            r"\$\{([^}]+)\}",
            lambda m: os.environ.get(m.group(1), m.group(0)),
            value,
        )
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value
```

**Step 2: Apply it in the config loader**

Find the function that loads and returns the parsed YAML config (likely `load_config()` or
`get_config()`). After `yaml.safe_load()`, wrap the result:

```python
config = yaml.safe_load(f) or {}
config = _expand_env_vars(config)
return config
```

If config loading is done in multiple places, grep for `yaml.safe_load` and apply to each
call site that loads the main config (not test fixtures).

```bash
grep -n "yaml.safe_load" hermes_cli/config.py
```

**Step 3: Write tests**

File: tests/tools/test_config_env_expansion.py (new file)

```python
"""Tests for ${ENV_VAR} expansion in config loading."""
import os
import pytest
from unittest.mock import patch
from hermes_cli.config import _expand_env_vars


class TestExpandEnvVars:
    def test_plain_string_unchanged(self):
        assert _expand_env_vars("hello") == "hello"

    def test_resolves_set_var(self):
        with patch.dict(os.environ, {"MY_KEY": "secret123"}):
            assert _expand_env_vars("${MY_KEY}") == "secret123"

    def test_leaves_missing_var_as_is(self):
        result = _expand_env_vars("${HERMES_NONEXISTENT_12345}")
        assert result == "${HERMES_NONEXISTENT_12345}"

    def test_partial_string(self):
        with patch.dict(os.environ, {"HOST": "localhost"}):
            assert _expand_env_vars("http://${HOST}:8080") == "http://localhost:8080"

    def test_dict_recursion(self):
        with patch.dict(os.environ, {"TOKEN": "abc"}):
            result = _expand_env_vars({"api_key": "${TOKEN}", "other": "plain"})
            assert result == {"api_key": "abc", "other": "plain"}

    def test_list_recursion(self):
        with patch.dict(os.environ, {"VAL": "x"}):
            assert _expand_env_vars(["${VAL}", "static"]) == ["x", "static"]

    def test_nested_dict(self):
        with patch.dict(os.environ, {"SECRET": "pw"}):
            cfg = {"mcp": {"servers": {"myserver": {"env": {"PASS": "${SECRET}"}}}}}
            result = _expand_env_vars(cfg)
            assert result["mcp"]["servers"]["myserver"]["env"]["PASS"] == "pw"

    def test_non_string_values_pass_through(self):
        assert _expand_env_vars(42) == 42
        assert _expand_env_vars(True) is True
        assert _expand_env_vars(None) is None
```

**Step 4: Verify**

```bash
python3 -m pytest tests/tools/test_config_env_expansion.py -v -o "addopts="
python3 -c "import py_compile; py_compile.compile('hermes_cli/config.py', doraise=True); print('OK')"
```

**Step 5: Update WINDOWS.md**

In the Security section of WINDOWS.md, add a note:

```markdown
### Secrets in config.yaml

Use `${ENV_VAR}` syntax to reference environment variables instead of embedding secrets:

```yaml
mcpServers:
  myserver:
    env:
      API_KEY: ${MY_SERVICE_API_KEY}
```

Set the variable in your shell profile or Windows environment variables.
Unresolved references are left as-is (no silent empty substitution).
```

**Step 6: Commit**

```bash
git add hermes_cli/config.py tests/tools/test_config_env_expansion.py WINDOWS.md
git commit -m "feat(config): support \${ENV_VAR} substitution in config.yaml for secrets"
```

---

## Task 3 — keyring integration for API key storage

**Why:** API keys are stored in plaintext in auth.json / .env files. chmod(0o600) is a
no-op on Windows. Phase 2 added icacls hardening but the file is still readable by anyone
who bypasses ACLs. The keyring library uses Windows Credential Manager (DPAPI-encrypted,
tied to the user account) transparently.

**File:** hermes_cli/config.py (same file as Task 2, do Task 2 first)

**Dependency:** keyring is already a common Python package. Add to pyproject.toml
optional deps rather than a hard dependency — keyring requires a credential store daemon
on some Linux setups, making it a bad hard dep.

**Step 1: Add optional import at the top of config.py**

```python
try:
    import keyring as _keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    _keyring = None  # type: ignore[assignment]
    _KEYRING_AVAILABLE = False
```

**Step 2: Write keyring-backed get/set helpers**

Add these alongside the existing `save_env_value_secure()` and `get_env_value()`:

```python
_KEYRING_SERVICE = "hermes-agent"


def save_secret_keyring(key: str, value: str) -> bool:
    """Store a secret in the OS keychain. Returns True on success.

    Falls back to the existing secure-file storage if keyring is unavailable
    or if we're in a headless environment (Windows service / CI).
    """
    if not _KEYRING_AVAILABLE:
        return False
    try:
        _keyring.set_password(_KEYRING_SERVICE, key, value)
        return True
    except Exception:
        # Headless environment — DPAPI/SecretService unavailable
        return False


def get_secret_keyring(key: str) -> str | None:
    """Retrieve a secret from the OS keychain. Returns None if not found."""
    if not _KEYRING_AVAILABLE:
        return None
    try:
        return _keyring.get_password(_KEYRING_SERVICE, key)
    except Exception:
        return None


def delete_secret_keyring(key: str) -> bool:
    """Delete a secret from the OS keychain. Returns True on success."""
    if not _KEYRING_AVAILABLE:
        return False
    try:
        _keyring.delete_password(_KEYRING_SERVICE, key)
        return True
    except Exception:
        return False
```

**Step 3: Update save_env_value_secure() to try keyring first**

Find the existing `save_env_value_secure()` function. At the top of its body, add:

```python
# Try OS keychain first (DPAPI on Windows, SecretService on Linux, Keychain on macOS)
if save_secret_keyring(key, value):
    return  # stored in keychain, done
# Fall through to file-based secure storage
```

**Step 4: Update get_env_value() to check keyring first**

At the top of the existing lookup logic, add:

```python
# Check OS keychain first
v = get_secret_keyring(key)
if v is not None:
    return v
# Fall through to file-based storage
```

**Step 5: Write tests**

File: tests/tools/test_keyring_storage.py (new file)

```python
"""Tests for keyring-backed secret storage."""
import pytest
from unittest.mock import patch, MagicMock
import hermes_cli.config as config


class TestKeyringHelpers:
    def test_save_returns_false_when_keyring_unavailable(self):
        with patch.object(config, "_KEYRING_AVAILABLE", False):
            assert config.save_secret_keyring("k", "v") is False

    def test_save_returns_true_on_success(self):
        mock_kr = MagicMock()
        with patch.object(config, "_KEYRING_AVAILABLE", True):
            with patch.object(config, "_keyring", mock_kr):
                result = config.save_secret_keyring("mykey", "myval")
        assert result is True
        mock_kr.set_password.assert_called_once_with("hermes-agent", "mykey", "myval")

    def test_save_returns_false_on_exception(self):
        mock_kr = MagicMock()
        mock_kr.set_password.side_effect = Exception("no daemon")
        with patch.object(config, "_KEYRING_AVAILABLE", True):
            with patch.object(config, "_keyring", mock_kr):
                result = config.save_secret_keyring("k", "v")
        assert result is False

    def test_get_returns_none_when_unavailable(self):
        with patch.object(config, "_KEYRING_AVAILABLE", False):
            assert config.get_secret_keyring("k") is None

    def test_get_returns_value_on_success(self):
        mock_kr = MagicMock()
        mock_kr.get_password.return_value = "secretval"
        with patch.object(config, "_KEYRING_AVAILABLE", True):
            with patch.object(config, "_keyring", mock_kr):
                result = config.get_secret_keyring("mykey")
        assert result == "secretval"

    def test_get_returns_none_on_exception(self):
        mock_kr = MagicMock()
        mock_kr.get_password.side_effect = Exception("locked")
        with patch.object(config, "_KEYRING_AVAILABLE", True):
            with patch.object(config, "_keyring", mock_kr):
                assert config.get_secret_keyring("k") is None

    def test_delete_returns_true_on_success(self):
        mock_kr = MagicMock()
        with patch.object(config, "_KEYRING_AVAILABLE", True):
            with patch.object(config, "_keyring", mock_kr):
                assert config.delete_secret_keyring("k") is True

    def test_save_env_value_secure_uses_keyring_first(self):
        with patch.object(config, "save_secret_keyring", return_value=True) as mock_save:
            with patch.object(config, "_write_env_file") as mock_file:
                config.save_env_value_secure("ANTHROPIC_API_KEY", "sk-test")
        mock_save.assert_called_once()
        mock_file.assert_not_called()  # keyring succeeded, no file write

    def test_get_env_value_falls_back_to_file(self):
        with patch.object(config, "get_secret_keyring", return_value=None):
            with patch.object(config, "_read_env_file", return_value="from_file"):
                result = config.get_env_value("SOME_KEY")
        assert result == "from_file"
```

Note: The mock target names (_write_env_file, _read_env_file) need to match whatever
the actual private functions are called in config.py. Adjust accordingly after reading
the file.

**Step 6: Add keyring to optional deps in pyproject.toml**

```toml
[project.optional-dependencies]
keyring = ["keyring>=24.0"]
```

And note in WINDOWS.md:
  pip install "hermes-agent[keyring]"   # enables OS keychain storage

**Step 7: Verify**

```bash
pip install keyring -q
python3 -m pytest tests/tools/test_keyring_storage.py -v -o "addopts="
python3 -c "import py_compile; py_compile.compile('hermes_cli/config.py', doraise=True); print('OK')"
```

**Step 8: Commit**

```bash
git add hermes_cli/config.py tests/tools/test_keyring_storage.py pyproject.toml WINDOWS.md
git commit -m "feat(config): keyring integration for OS-native secret storage (DPAPI on Windows)"
```

---

## Task 4 — doctor.py Windows health checks

**Why:** hermes doctor currently skips systemd linger checks on Windows (correct) but
adds no Windows-specific checks. First-run issues on Windows (wrong Python, missing WSL,
Defender scanning the venv, AF_UNIX not available) are silent and confusing.

**File:** hermes_cli/doctor.py

**Step 1: Read the existing file to understand the check pattern**

```bash
grep -n "def.*check\|class.*Check\|def check\|def run" hermes_cli/doctor.py | head -30
```

Understand how checks are structured (likely a list of Check objects or functions
returning a namedtuple/dataclass with name, status, message, fix_cmd).

**Step 2: Write a Windows-specific check battery**

Add this function to doctor.py (or its appropriate check module):

```python
def _windows_checks() -> list:
    """Windows-specific health checks. Only called on sys.platform == 'win32'."""
    import shutil, subprocess, platform
    results = []

    def ok(name, msg): return _make_check_result(name, "ok", msg)
    def warn(name, msg, fix=None): return _make_check_result(name, "warn", msg, fix)
    def fail(name, msg, fix=None): return _make_check_result(name, "fail", msg, fix)

    # 1. Python version
    v = sys.version_info
    if v >= (3, 10):
        results.append(ok("Python version", f"{v.major}.{v.minor}.{v.micro}"))
    else:
        results.append(fail(
            "Python version",
            f"{v.major}.{v.minor} is below minimum 3.10",
            "Download Python 3.12+ from python.org"
        ))

    # 2. Windows build (AF_UNIX requires build 17063+)
    try:
        build = int(platform.version().split(".")[-1])
        if build >= 17063:
            results.append(ok("Windows build", f"Build {build} (AF_UNIX supported)"))
        else:
            results.append(warn(
                "Windows build",
                f"Build {build} — AF_UNIX sockets unavailable (need 17063+)",
                "Update Windows via Settings > Windows Update"
            ))
    except Exception:
        results.append(warn("Windows build", "Could not determine build number"))

    # 3. WSL availability
    wsl = shutil.which("wsl.exe") or r"C:\Windows\System32\wsl.exe"
    try:
        r = subprocess.run([wsl, "--status"], capture_output=True, timeout=5)
        if r.returncode == 0:
            results.append(ok("WSL", "WSL available"))
        else:
            results.append(warn("WSL", "wsl.exe found but --status failed",
                                "wsl --install"))
    except FileNotFoundError:
        results.append(warn("WSL", "WSL not installed (optional, needed for some tools)",
                            "wsl --install"))
    except Exception as e:
        results.append(warn("WSL", f"WSL check failed: {e}"))

    # 4. Windows Terminal
    wt_path = os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe"
    )
    if os.path.exists(wt_path):
        results.append(ok("Windows Terminal", "Installed"))
    else:
        results.append(warn(
            "Windows Terminal",
            "Not found — some display features work best in Windows Terminal",
            "winget install Microsoft.WindowsTerminal"
        ))

    # 5. Windows Defender scanning venv
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows Defender\Real-Time Protection"
        )
        val, _ = winreg.QueryValueEx(key, "DisableRealtimeMonitoring")
        winreg.CloseKey(key)
        if val:
            results.append(ok("Windows Defender", "Real-time scanning disabled"))
        else:
            venv = os.environ.get("VIRTUAL_ENV", "")
            results.append(warn(
                "Windows Defender",
                "Real-time scanning active — may slow file I/O significantly",
                (f'Add-MpPreference -ExclusionPath "{venv}"'
                 if venv else
                 "Add-MpPreference -ExclusionProcess python.exe")
            ))
    except Exception:
        pass  # can't read defender status, skip silently

    # 6. keyring availability
    try:
        import keyring  # noqa: F401
        results.append(ok("keyring", "Available — API keys stored in Windows Credential Manager"))
    except ImportError:
        results.append(warn(
            "keyring",
            "Not installed — API keys stored in plaintext files",
            'pip install "hermes-agent[keyring]"'
        ))

    return results
```

**Step 3: Wire into the main doctor check runner**

Find where doctor.py assembles the list of checks to run. Add:

```python
if sys.platform == "win32":
    checks.extend(_windows_checks())
```

And guard the existing systemd/linger check so it only runs on non-Windows:

```python
if sys.platform != "win32":
    # existing systemd check here
```

**Step 4: Write tests**

File: tests/tools/test_doctor_windows.py (new file)

```python
"""Tests for Windows-specific doctor checks."""
import sys
import pytest
from unittest.mock import patch, MagicMock
import hermes_cli.doctor as doctor


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
class TestWindowsDoctorChecks:

    def test_python_version_ok(self):
        results = doctor._windows_checks()
        names = {r.name for r in results}
        assert "Python version" in names

    def test_python_version_fail_below_310(self):
        with patch.object(sys, "version_info", (3, 9, 0)):
            results = doctor._windows_checks()
        version_result = next(r for r in results if r.name == "Python version")
        assert version_result.status == "fail"

    def test_wsl_check_present(self):
        results = doctor._windows_checks()
        names = {r.name for r in results}
        assert "WSL" in names

    def test_keyring_ok_when_installed(self):
        with patch.dict("sys.modules", {"keyring": MagicMock()}):
            results = doctor._windows_checks()
        keyring_result = next(r for r in results if r.name == "keyring")
        assert keyring_result.status == "ok"

    def test_keyring_warn_when_missing(self):
        with patch.dict("sys.modules", {"keyring": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                results = doctor._windows_checks()
        # keyring check should produce a warn result
        keyring_results = [r for r in results if r.name == "keyring"]
        if keyring_results:
            assert keyring_results[0].status == "warn"


class TestDoctorSkipsSystemdOnWindows:
    def test_systemd_check_skipped_on_windows(self):
        with patch.object(sys, "platform", "win32"):
            # Running doctor checks should not raise or include systemd checks
            try:
                checks = doctor._get_all_checks()
                names = [c.name for c in checks]
                assert "systemd linger" not in names
            except AttributeError:
                pytest.skip("doctor._get_all_checks not available — adjust to match actual API")
```

Note: Adjust `_make_check_result` and the result object field names to match the actual
pattern used in doctor.py. Read the file first.

**Step 5: Verify**

```bash
python3 -m pytest tests/tools/test_doctor_windows.py -v -o "addopts="
python3 -c "import py_compile; py_compile.compile('hermes_cli/doctor.py', doraise=True); print('OK')"
# Run doctor manually to see output
hermes doctor
```

**Step 6: Commit**

```bash
git add hermes_cli/doctor.py tests/tools/test_doctor_windows.py
git commit -m "feat(doctor): add Windows-specific health checks (build, WSL, Defender, keyring)"
```

---

## Task 5 — Dark/light theme detection

**Why:** Trivial 10-line addition. Hermes can auto-select a color scheme matching the
Windows/macOS/Linux system theme rather than always using the default. Useful for
prompt_toolkit color scheme selection in cli.py.

**File:** hermes_cli/display.py (or a new hermes_cli/theme.py if display.py is large)

**Step 1: Write the detection function**

```python
def get_system_theme() -> str:
    """Detect the OS theme preference. Returns 'dark', 'light', or 'unknown'.

    - Windows: reads HKCU registry AppsUseLightTheme (requires Windows 10 1607+)
    - macOS: runs 'defaults read -g AppleInterfaceStyle'
    - Linux: checks GTK_THEME env var or gsettings (best-effort)
    - Falls back to 'dark' on any error (dark is the safer default for terminals)
    """
    try:
        if sys.platform == "win32":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "light" if val else "dark"

        if sys.platform == "darwin":
            import subprocess
            r = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2
            )
            return "dark" if "Dark" in r.stdout else "light"

        # Linux — check GTK_THEME or gsettings
        gtk = os.environ.get("GTK_THEME", "")
        if "dark" in gtk.lower():
            return "dark"
        if "light" in gtk.lower():
            return "light"

    except Exception:
        pass

    return "dark"  # safe default for terminals
```

**Step 2: Expose it from display.py / __init__ as needed**

If cli.py sets up the prompt_toolkit color scheme at startup, add a call like:

```python
from hermes_cli.display import get_system_theme
_SYSTEM_THEME = get_system_theme()
```

And use `_SYSTEM_THEME` to choose between color palettes when initializing the
`InMemoryHistory` / `PromptSession` in cli.py. Don't force a full re-theme — just
offer dark/light as a toggle for the existing color scheme selection if one exists.

If no color scheme selection exists yet, just export the function — a future PR can
wire it in. The value here is having the detection in place.

**Step 3: Write tests**

File: tests/tools/test_theme_detection.py (new file)

```python
"""Tests for system theme detection."""
import sys
import pytest
from unittest.mock import patch, MagicMock
from hermes_cli.display import get_system_theme   # adjust import if in different module


class TestGetSystemTheme:

    def test_returns_dark_or_light_or_unknown(self):
        result = get_system_theme()
        assert result in ("dark", "light", "unknown", "dark")  # 'dark' fallback

    def test_windows_dark_mode(self):
        mock_key = MagicMock()
        with patch.object(sys, "platform", "win32"):
            with patch("winreg.OpenKey", return_value=mock_key):
                with patch("winreg.QueryValueEx", return_value=(0, 4)):  # 0 = dark
                    with patch("winreg.CloseKey"):
                        result = get_system_theme()
        assert result == "dark"

    def test_windows_light_mode(self):
        mock_key = MagicMock()
        with patch.object(sys, "platform", "win32"):
            with patch("winreg.OpenKey", return_value=mock_key):
                with patch("winreg.QueryValueEx", return_value=(1, 4)):  # 1 = light
                    with patch("winreg.CloseKey"):
                        result = get_system_theme()
        assert result == "light"

    def test_windows_registry_error_returns_dark(self):
        with patch.object(sys, "platform", "win32"):
            with patch("winreg.OpenKey", side_effect=FileNotFoundError):
                result = get_system_theme()
        assert result == "dark"

    def test_macos_dark(self):
        mock_result = MagicMock()
        mock_result.stdout = "Dark\n"
        with patch.object(sys, "platform", "darwin"):
            with patch("subprocess.run", return_value=mock_result):
                result = get_system_theme()
        assert result == "dark"

    def test_macos_light(self):
        mock_result = MagicMock()
        mock_result.stdout = "\n"  # no output = light mode on macOS
        with patch.object(sys, "platform", "darwin"):
            with patch("subprocess.run", return_value=mock_result):
                result = get_system_theme()
        assert result == "light"

    def test_linux_gtk_dark(self):
        with patch.object(sys, "platform", "linux"):
            with patch.dict("os.environ", {"GTK_THEME": "Adwaita:dark"}):
                result = get_system_theme()
        assert result == "dark"

    def test_fallback_is_dark(self):
        with patch.object(sys, "platform", "linux"):
            with patch.dict("os.environ", {}, clear=True):
                result = get_system_theme()
        assert result == "dark"
```

**Step 4: Verify**

```bash
python3 -m pytest tests/tools/test_theme_detection.py -v -o "addopts="
```

**Step 5: Commit**

```bash
git add hermes_cli/display.py tests/tools/test_theme_detection.py
git commit -m "feat(display): add get_system_theme() for dark/light OS theme detection"
```

---

## Final verification after all tasks

```bash
cd /c/Users/Carlos/hermes-agent
source ~/hermes-venv/bin/activate

# Compile-check all touched files
python3 -c "
import py_compile
files = [
    'hermes_cli/clipboard.py',
    'hermes_cli/config.py',
    'hermes_cli/doctor.py',
    'hermes_cli/display.py',
]
for f in files:
    py_compile.compile(f, doraise=True)
    print(f'OK: {f}')
"

# Run all new tests
python3 -m pytest tests/tools/test_clipboard.py tests/tools/test_config_env_expansion.py tests/tools/test_keyring_storage.py tests/tools/test_doctor_windows.py tests/tools/test_theme_detection.py -o "addopts=" -v

# Sweep for logout corruption across touched files
grep -n "logout" hermes_cli/clipboard.py hermes_cli/config.py hermes_cli/doctor.py hermes_cli/display.py | grep -v "#" | grep -v "'logout'" | grep -v '"logout"'

# Check git status — only intended files should be modified
git status
git diff --stat HEAD
```

If any logout corruption appears in git diff, fix it before the final push.
See hermes-windows-development skill for the fix_logout.py script.

Final commit message for the phase:
  git tag windows-qol-phase5 -m "Windows QoL Phase 5: CF_PNG clipboard, env var config, keyring, doctor checks, theme detection"

---

## What was NOT included (future work)

- prompt_toolkit bracketed paste regression workaround (needs upstream version check)
- WSL2 host networking helper (utility value unclear without a concrete use case)
- pystray tray icon (blocked on daemon mode feature which doesn't exist yet)
- Windows toast notifications (nice-to-have, no urgent trigger)
- Windows Terminal profile fragment registration (installer work, not core agent)
- Auto-update mechanism (not relevant for editable git install)
- winget/PyInstaller packaging (separate project)
- Pre-commit platform import guard (dev tooling, separate PR)
- Jump List integration (requires pywin32 hard dep, questionable ROI)
- ConPTY integration (blocked on shell tool redesign)

---

## Research notes (for reference)

CF_PNG: RegisterClipboardFormat("PNG") → check before CF_DIBV5. Chrome/Firefox/Word all use it.
keyring: WinVaultKeyring backend auto-selected on Windows. Headless pitfall: DPAPI needs loaded user profile, returns None in services. Always fallback to file storage.
darkdetect PyPI wraps AppsUseLightTheme registry read cleanly if winreg import feels heavy.
doctor pattern: Flutter Doctor is canonical reference. Check objects with name/status/message/fix_cmd.
$ENV substitution: string.Template(safe_substitute) is zero-dep alternative to re.sub approach.
