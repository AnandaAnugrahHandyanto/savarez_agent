import ast
from pathlib import Path


GATEWAY_CLI = Path(__file__).resolve().parents[2] / "hermes_cli" / "gateway.py"


def _function_calls(function_name: str):
    tree = ast.parse(GATEWAY_CLI.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return [child for child in ast.walk(node) if isinstance(child, ast.Call)]
    raise AssertionError(f"Function not found: {function_name}")


def test_dingtalk_qr_setup_does_not_silently_enable_allow_all():
    calls = _function_calls("_setup_dingtalk")

    silent_allow_all_writes = []
    for call in calls:
        if not isinstance(call.func, ast.Name) or call.func.id != "save_env_value":
            continue
        if len(call.args) < 2:
            continue
        key, value = call.args[:2]
        if (
            isinstance(key, ast.Constant)
            and key.value == "DINGTALK_ALLOW_ALL_USERS"
            and isinstance(value, ast.Constant)
            and value.value == "true"
        ):
            silent_allow_all_writes.append(call.lineno)

    assert silent_allow_all_writes == []


def test_dingtalk_setup_includes_access_control_prompting():
    source = GATEWAY_CLI.read_text(encoding="utf-8")

    assert '"name": "DINGTALK_ALLOWED_USERS"' in source
    assert '"is_allowlist": True' in source
    assert "_configure_dingtalk_access()" in source
