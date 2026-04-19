# Test-Driven Development Guide for Hermes-Agent

This document outlines the testing standards and TDD practices for the hermes-agent project.

## Philosophy

We follow Test-Driven Development (TDD) principles:

1. **Write tests first**: Before implementing a feature or fixing a bug, write a failing test
2. **Red-Green-Refactor**: Write failing test → Make it pass → Refactor
3. **Test as documentation**: Tests should clearly explain what the code does and why
4. **Fast feedback**: Tests should run quickly to provide immediate feedback

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── agent/                   # Tests for agent/ module
├── cli/                     # Tests for hermes_cli/ module
├── cron/                    # Tests for cron/ module
├── gateway/                 # Tests for gateway/ module
├── tools/                   # Tests for tools/ module
├── integration/             # Integration tests (external services)
├── e2e/                     # End-to-end tests (full flows)
└── fakes/                   # Mock implementations
```

## Test Categories

### Unit Tests (`tests/*/`)

- Test individual functions and classes in isolation
- Mock all external dependencies (APIs, databases, filesystem)
- Should run in milliseconds
- Located alongside the module they test

**Naming convention:** `test_<module>_<function>_<scenario>.py` or `test_<specific_feature>.py`

**Example:**
```python
def test_detect_dangerous_command_rm_rf_flags_as_dangerous():
    is_dangerous, key, desc = detect_dangerous_command("rm -rf /home/user")
    assert is_dangerous is True
    assert "delete" in desc.lower()
```

### Integration Tests (`tests/integration/`)

- Test interaction between components
- May use real external services or sophisticated mocks
- Slower than unit tests
- Marked with `@pytest.mark.integration`

**Example:**
```python
@pytest.mark.integration
def test_web_search_returns_results():
    result = web_search(query="Python testing best practices")
    assert len(result["results"]) > 0
```

### End-to-End Tests (`tests/e2e/`)

- Test complete user workflows
- Exercise full system with mocked external services
- Use platform-specific fixtures in `conftest.py`

**Example:**
```python
@pytest.mark.asyncio
async def test_help_command_replies(adapter, runner):
    send_mock = await send_and_capture(adapter, "/help", Platform.TELEGRAM)
    assert send_mock.called
    args = send_mock.call_args[0][0]
    assert "/help" in args or "commands" in args.lower()
```

## Writing Tests

### Test Classes

Use classes to group related tests:

```python
class TestApprovalModeParsing:
    """Tests for approval mode configuration parsing."""
    
    def test_unquoted_yaml_off_boolean_false_maps_to_off(self):
        ...
    
    def test_string_off_still_maps_to_off(self):
        ...
```

### Fixtures

Use fixtures from `conftest.py` for common setup:

```python
# Use the autouse fixture that isolates HERMES_HOME
def test_writes_to_hermes_home(tmp_path):
    # HERMES_HOME is already set to a temp directory
    config_path = Path(os.environ["HERMES_HOME"]) / "config.yaml"
    # Test safely writes here instead of ~/.hermes/
```

### Mocking External Dependencies

Always mock external services in unit tests:

```python
from unittest.mock import patch, MagicMock

def test_web_search_with_mocked_client():
    with patch("tools.web_tools._search_exa") as mock_search:
        mock_search.return_value = {"results": [{"title": "Test"}]}
        result = web_search(query="test")
        assert result["success"] is True
```

### Async Tests

Mark async tests properly:

```python
import pytest

@pytest.mark.asyncio
async def test_async_adapter_send():
    adapter = MockAdapter()
    result = await adapter.send("Hello")
    assert result.success is True
```

## Running Tests

### Quick Unit Tests

```bash
# Run all unit tests (excludes integration and e2e)
make test

# Or with pytest directly
python -m pytest tests/ -q --ignore=tests/integration --ignore=tests/e2e -n auto
```

### Integration Tests

```bash
# Run integration tests (requires API keys)
make test-integration

# Or
python -m pytest tests/integration/ -v
```

### E2E Tests

```bash
# Run e2e tests
make test-e2e

# Or
python -m pytest tests/e2e/ -v
```

### Coverage

```bash
# Run tests with coverage report
make coverage

# View HTML report
open htmlcov/index.html
```

### Specific Tests

```bash
# Run tests for a specific module
python -m pytest tests/tools/test_approval.py -v

# Run a specific test class
python -m pytest tests/tools/test_approval.py::TestDetectDangerousRm -v

# Run a specific test method
python -m pytest tests/tools/test_approval.py::TestDetectDangerousRm::test_rm_rf_detected -v
```

## Coverage Requirements

- **Minimum coverage**: 80% for new code
- **Critical paths**: 90% for tools/approval.py, tools/registry.py
- **Excluded from coverage**: 
  - Debug/test utilities
  - Platform-specific code not testable in CI
  - Auto-generated code

## TDD Workflow

1. **Identify the behavior**: Understand what needs to change
2. **Write a failing test**: Create a test that demonstrates the missing/incorrect behavior
3. **Run the test**: Confirm it fails (Red)
4. **Implement the fix**: Write minimal code to make the test pass
5. **Run the test**: Confirm it passes (Green)
6. **Refactor**: Clean up the code while keeping tests green
7. **Commit**: Commit with a message explaining the change

## Best Practices

### DO

- ✅ Write tests that are independent and isolated
- ✅ Use descriptive test names that explain the scenario
- ✅ Use fixtures for common setup
- ✅ Mock external dependencies
- ✅ Test edge cases and error conditions
- ✅ Keep tests fast (unit tests < 100ms)
- ✅ Use parameterized tests for multiple similar cases

### DON'T

- ❌ Write tests that depend on execution order
- ❌ Access real external services in unit tests
- ❌ Write tests that write to `~/.hermes/` (use `tmp_path` fixture)
- ❌ Leave tests skipped without a reason
- ❌ Test implementation details instead of behavior
- ❌ Write tests that are too large or test too many things

## Test Utilities

### Timeouts

Tests automatically timeout after 30 seconds (Unix only):

```python
# In conftest.py
@pytest.fixture(autouse=True)
def _enforce_test_timeout():
    """Kill any individual test that takes longer than 30 seconds."""
```

### Hermes Home Isolation

All tests automatically get an isolated `HERMES_HOME`:

```python
# In conftest.py
@pytest.fixture(autouse=True)
def _isolate_hermes_home(tmp_path, monkeypatch):
    """Redirect HERMES_HOME to a temp dir so tests never write to ~/.hermes/."""
```

### Event Loop Management

Sync tests that use `asyncio.get_event_loop()` are handled automatically:

```python
@pytest.fixture(autouse=True)
def _ensure_current_event_loop(request):
    """Provide a default event loop for sync tests."""
```

## Common Patterns

### Testing Dangerous Command Detection

```python
class TestRmRecursiveFlagVariants:
    """Ensure all recursive delete flag styles are caught."""

    def test_rm_r(self):
        dangerous, key, desc = detect_dangerous_command("rm -r mydir")
        assert dangerous is True
        assert key is not None
        assert "recursive" in desc.lower() or "delete" in desc.lower()
```

### Testing with AST Analysis

```python
def test_gateway_runner_binds_session_key_to_context_before_agent_run(self):
    run_py = Path(__file__).resolve().parents[2] / "gateway" / "run.py"
    module = ast.parse(run_py.read_text(encoding="utf-8"))
    
    run_sync = None
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == "run_sync":
            run_sync = node
            break
    
    assert run_sync is not None
    
    called_names = set()
    for node in ast.walk(run_sync):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)
    
    assert "set_current_session_key" in called_names
```

### Parametrized Tests

```python
@pytest.mark.parametrize("cmd,expected_dangerous", [
    ("rm -rf /", True),
    ("rm -r mydir", True),
    ("rm readme.txt", False),
    ("ls -la", False),
])
def test_dangerous_command_detection(cmd, expected_dangerous):
    is_dangerous, _, _ = detect_dangerous_command(cmd)
    assert is_dangerous is expected_dangerous
```

## Debugging Tests

### Verbose Output

```bash
python -m pytest tests/tools/test_approval.py -v --tb=long
```

### PDB Debugging

```bash
python -m pytest tests/tools/test_approval.py -v --pdb
```

### Print Statements

```python
def test_something():
    result = some_function()
    print(f"Result: {result}")  # Will show with -s flag
    assert result is True
```

Run with:
```bash
python -m pytest test_file.py -v -s
```

## Continuous Integration

Tests run automatically on GitHub Actions:

1. **Unit tests**: Run on every PR and push to main
2. **E2E tests**: Run on every PR and push to main
3. **Coverage report**: Generated and uploaded as artifact

See `.github/workflows/tests.yml` for configuration.

## Contributing

When contributing code:

1. Ensure all existing tests pass: `make test`
2. Add tests for new functionality
3. Maintain or improve code coverage
4. Follow the TDD workflow for bug fixes
5. Update this document if you add new testing patterns

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [Python testing best practices](https://realpython.com/python-testing/)
