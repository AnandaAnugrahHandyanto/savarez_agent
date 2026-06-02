"""Unit tests for the Kubernetes session-pod execution backend."""

import sys
import types as _types
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

from tools.environments.kubernetes import PodRef, WorkspaceProvisioner, DirectProvisioner, Resources, KubernetesEnvironment


@pytest.fixture(autouse=True)
def _stub_kubernetes(monkeypatch):
    """Stub the kubernetes client so the backend imports without the cluster."""
    if "kubernetes" in sys.modules:
        return
    k = _types.ModuleType("kubernetes")
    k.client = _types.ModuleType("kubernetes.client")
    k.config = _types.ModuleType("kubernetes.config")
    k.stream = _types.ModuleType("kubernetes.stream")
    exc_mod = _types.ModuleType("kubernetes.client.exceptions")

    class ApiException(Exception):
        def __init__(self, status=0, reason=""):
            self.status = status
            self.reason = reason
            super().__init__(f"{status}: {reason}")

    exc_mod.ApiException = ApiException
    k.client.exceptions = exc_mod
    k.client.CoreV1Api = MagicMock
    k.config.load_incluster_config = lambda: None
    k.stream.stream = MagicMock()
    monkeypatch.setitem(sys.modules, "kubernetes", k)
    monkeypatch.setitem(sys.modules, "kubernetes.client", k.client)
    monkeypatch.setitem(sys.modules, "kubernetes.client.exceptions", exc_mod)
    monkeypatch.setitem(sys.modules, "kubernetes.config", k.config)
    monkeypatch.setitem(sys.modules, "kubernetes.stream", k.stream)


def test_podref_holds_coordinates():
    ref = PodRef(namespace="hermes", pod_name="hermes-ws-abc", container="workspace")
    assert ref.namespace == "hermes"
    assert ref.pod_name == "hermes-ws-abc"
    assert ref.container == "workspace"


def test_provisioner_is_abstract():
    import pytest
    with pytest.raises(TypeError):
        WorkspaceProvisioner()  # ABC — cannot instantiate


def _provisioner():
    # owner_uid/name come from the agent's own pod (downward API); namespace
    # from the SA mount. Inject directly to avoid touching the cluster.
    return DirectProvisioner(
        namespace="hermes",
        pod_service_account="hermes-session-noperms",
        owner_pod_name="hermes-agent-0",
        owner_pod_uid="11111111-1111-1111-1111-111111111111",
        image_pull_secrets=["regcred"],
        api=None,  # manifest builders don't touch the API
    )


def test_ephemeral_pod_uses_emptydir_and_no_ownerref_on_pvc():
    p = _provisioner()
    pod = p._pod_manifest("abc", persistent=False, image="img:1", resources=Resources())
    vols = pod["spec"]["volumes"]
    assert vols[0]["emptyDir"] == {}
    assert vols[0]["name"] == "workspace"
    mount = pod["spec"]["containers"][0]["volumeMounts"][0]
    assert mount["mountPath"] == "/workspace"
    owner = pod["metadata"]["ownerReferences"][0]
    assert owner["uid"] == "11111111-1111-1111-1111-111111111111"


def test_persistent_pod_references_pvc_by_task_id():
    p = _provisioner()
    pod = p._pod_manifest("mytask", persistent=True, image="img:1", resources=Resources())
    vol = pod["spec"]["volumes"][0]
    assert vol["persistentVolumeClaim"]["claimName"] == "hermes-ws-mytask"


def test_pvc_manifest_has_no_ownerref():
    p = _provisioner()
    pvc = p._pvc_manifest("mytask", resources=Resources(disk_mib=10240))
    assert pvc["metadata"]["name"] == "hermes-ws-mytask"
    assert "ownerReferences" not in pvc["metadata"]
    assert pvc["spec"]["resources"]["requests"]["storage"] == "10240Mi"


def test_pod_manifest_omits_ownerref_when_owner_unknown():
    # When owner pod name/uid are absent (host-driven / not in-cluster), the
    # manifest must NOT carry an ownerReference — K8s rejects an empty one
    # with 422 (regression caught by L2 against a real cluster).
    p = DirectProvisioner(
        namespace="hermes",
        pod_service_account="hermes-session-noperms",
        owner_pod_name="",
        owner_pod_uid="",
        api=None,
    )
    pod = p._pod_manifest("abc", persistent=False, image="img:1", resources=Resources())
    assert "ownerReferences" not in pod["metadata"]


def test_ephemeral_pod_has_active_deadline_persistent_does_not():
    # Ephemeral pods get a hard lifetime ceiling (leak backstop); persistent
    # pods must NOT (their workspace is meant to be long-lived).
    p = DirectProvisioner(
        namespace="hermes",
        pod_service_account="hermes-session-noperms",
        owner_pod_name="ag",
        owner_pod_uid="u",
        active_deadline_seconds=999,
        api=None,
    )
    ephemeral = p._pod_manifest("abc", persistent=False, image="i:1", resources=Resources())
    persistent = p._pod_manifest("abc", persistent=True, image="i:1", resources=Resources())
    assert ephemeral["spec"]["activeDeadlineSeconds"] == 999
    assert "activeDeadlineSeconds" not in persistent["spec"]


def test_pod_security_context_satisfies_vap():
    """The pod shape must satisfy the operator's secure-pod VAP."""
    p = _provisioner()
    pod = p._pod_manifest("abc", persistent=False, image="img:1", resources=Resources())
    spec = pod["spec"]
    assert spec["automountServiceAccountToken"] is False
    assert spec["serviceAccountName"] == "hermes-session-noperms"
    assert spec["hostNetwork"] is False
    assert spec["hostPID"] is False
    assert spec["hostIPC"] is False
    sc = spec["containers"][0]["securityContext"]
    assert sc["runAsNonRoot"] is True
    assert sc["allowPrivilegeEscalation"] is False
    assert sc["capabilities"]["drop"] == ["ALL"]
    # Pod-level context: concrete non-root uid + fsGroup so a runAsNonRoot
    # pod actually schedules on a root-default image and can write /workspace.
    pod_sc = spec["securityContext"]
    assert pod_sc["runAsUser"] == 1000
    assert pod_sc["fsGroup"] == 1000


def _running_pod():
    cond = SimpleNamespace(type="Ready", status="True")
    return SimpleNamespace(
        status=SimpleNamespace(phase="Running", conditions=[cond])
    )


def _provisioner_with_api(api):
    return DirectProvisioner(
        namespace="hermes",
        pod_service_account="hermes-session-noperms",
        owner_pod_name="hermes-agent-0",
        owner_pod_uid="uid-1",
        api=api,
    )


def test_ensure_ephemeral_creates_pod_only():
    api = MagicMock()
    api.read_namespaced_pod.return_value = _running_pod()
    p = _provisioner_with_api(api)

    ref = p.ensure("abc", persistent=False, image="img:1", resources=Resources())

    api.create_namespaced_pod.assert_called_once()
    api.create_namespaced_persistent_volume_claim.assert_not_called()
    assert ref.pod_name == "hermes-ws-abc"
    assert ref.container == "workspace"


def test_ensure_persistent_creates_pvc_then_pod():
    api = MagicMock()
    api.read_namespaced_pod.return_value = _running_pod()
    from kubernetes.client.exceptions import ApiException
    api.read_namespaced_persistent_volume_claim.side_effect = ApiException(status=404)
    p = _provisioner_with_api(api)

    p.ensure("mytask", persistent=True, image="img:1", resources=Resources())

    api.create_namespaced_persistent_volume_claim.assert_called_once()
    api.create_namespaced_pod.assert_called_once()


def test_ensure_persistent_skips_existing_pvc():
    api = MagicMock()
    api.read_namespaced_pod.return_value = _running_pod()
    api.read_namespaced_persistent_volume_claim.return_value = SimpleNamespace()
    p = _provisioner_with_api(api)

    p.ensure("mytask", persistent=True, image="img:1", resources=Resources())

    api.create_namespaced_persistent_volume_claim.assert_not_called()


def test_destroy_ephemeral_deletes_pod():
    api = MagicMock()
    p = _provisioner_with_api(api)
    p.destroy(PodRef("hermes", "hermes-ws-abc", "workspace"), persistent=False)
    api.delete_namespaced_pod.assert_called_once_with(
        name="hermes-ws-abc", namespace="hermes"
    )


def test_destroy_persistent_deletes_pod_keeps_pvc():
    api = MagicMock()
    p = _provisioner_with_api(api)
    p.destroy(PodRef("hermes", "hermes-ws-mytask", "workspace"), persistent=True)
    api.delete_namespaced_pod.assert_called_once()
    api.delete_namespaced_persistent_volume_claim.assert_not_called()


# ---------------------------------------------------------------------------
# KubernetesEnvironment tests
# ---------------------------------------------------------------------------


class _FakeWSClient:
    """Mimics kubernetes.stream WSClient for one exec call."""

    def __init__(self, stdout="", returncode=0):
        self._stdout = stdout
        self._returncode = returncode
        self._open = True

    def is_open(self):
        was = self._open
        self._open = False  # one update cycle then close
        return was

    def update(self, timeout=None):
        pass

    def peek_stdout(self):
        return bool(self._stdout)

    def read_stdout(self):
        s, self._stdout = self._stdout, ""
        return s

    def peek_stderr(self):
        return False

    def read_stderr(self):
        return ""

    def close(self):
        self._open = False

    @property
    def returncode(self):
        return self._returncode


def _make_k8s_env(monkeypatch, exec_outputs):
    """exec_outputs: list of (stdout, returncode) consumed per exec call."""
    monkeypatch.setattr("tools.environments.base.is_interrupted", lambda: False)

    provisioner = MagicMock()
    provisioner.ensure.return_value = PodRef("hermes", "hermes-ws-abc", "workspace")

    calls = {"i": 0}

    def fake_stream(*args, **kwargs):
        out, rc = exec_outputs[calls["i"]]
        calls["i"] += 1
        return _FakeWSClient(stdout=out, returncode=rc)

    monkeypatch.setattr("kubernetes.stream.stream", fake_stream)

    return KubernetesEnvironment(
        provisioner=provisioner,
        task_id="abc",
        persistent=False,
        image="img:1",
        cwd="/workspace",
        timeout=30,
    )


def test_basic_command(monkeypatch):
    # exec calls: (1) init_session bootstrap, (2) actual command
    env = _make_k8s_env(monkeypatch, [("", 0), ("hello\n", 0)])
    result = env.execute("echo hello")
    assert "hello" in result["output"]
    assert result["returncode"] == 0


def test_nonzero_exit_code(monkeypatch):
    env = _make_k8s_env(monkeypatch, [("", 0), ("nope\n", 127)])
    result = env.execute("bad_cmd")
    assert result["returncode"] == 127


def test_cleanup_calls_provisioner_destroy(monkeypatch):
    env = _make_k8s_env(monkeypatch, [("", 0)])
    env.cleanup()
    env._provisioner.destroy.assert_called_once()
    args, kwargs = env._provisioner.destroy.call_args
    assert args[1] is False  # persistent flag


def test_ephemeral_cancel_deletes_pod(monkeypatch):
    """cancel_fn (interrupt path) deletes the pod for ephemeral sessions."""
    env = _make_k8s_env(monkeypatch, [("", 0)])
    handle = env._run_bash("sleep 1")
    handle.kill()
    # kill() routes to cancel_fn -> provisioner.destroy for ephemeral
    env._provisioner.destroy.assert_called()


def test_factory_builds_kubernetes_env(monkeypatch):
    """_create_environment routes env_type='kubernetes' to KubernetesEnvironment."""
    import tools.terminal_tool as tt

    captured = {}

    class _FakeEnv:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        "tools.environments.kubernetes.DirectProvisioner",
        lambda **kw: MagicMock(name="provisioner"),
    )
    monkeypatch.setattr(
        "tools.environments.kubernetes.KubernetesEnvironment", _FakeEnv
    )
    monkeypatch.setenv("HERMES_POD_NAMESPACE", "hermes")
    monkeypatch.setenv("HERMES_POD_NAME", "hermes-agent-0")
    monkeypatch.setenv("HERMES_POD_UID", "uid-1")

    env = tt._create_environment(
        env_type="kubernetes",
        image="img:1",
        cwd="/workspace",
        timeout=30,
        container_config={"container_persistent": False},
        task_id="abc",
    )
    assert isinstance(env, _FakeEnv)
    assert captured["task_id"] == "abc"
    assert captured["persistent"] is False


def _build_k8s_env(monkeypatch, container_config):
    import tools.terminal_tool as tt
    captured = {}

    class _FakeEnv:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        "tools.environments.kubernetes.DirectProvisioner",
        lambda **kw: MagicMock(name="provisioner"),
    )
    monkeypatch.setattr("tools.environments.kubernetes.KubernetesEnvironment", _FakeEnv)
    monkeypatch.setenv("HERMES_POD_NAMESPACE", "hermes")
    tt._create_environment(
        env_type="kubernetes", image="img:1", cwd="/workspace", timeout=30,
        container_config=container_config, task_id="abc",
    )
    return captured


def test_factory_k8s_defaults_ephemeral_even_when_container_persistent_true(monkeypatch):
    # k8s must IGNORE the shared container_persistent default and default to
    # ephemeral; only TERMINAL_KUBERNETES_PERSISTENT (kubernetes_persistent)
    # turns it on.
    captured = _build_k8s_env(monkeypatch, {"container_persistent": True})
    assert captured["persistent"] is False


def test_factory_k8s_persistent_opt_in(monkeypatch):
    captured = _build_k8s_env(monkeypatch, {"kubernetes_persistent": True})
    assert captured["persistent"] is True


def test_check_requirements_kubernetes_missing_client(monkeypatch):
    import tools.terminal_tool as tt
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "kubernetes"})
    import importlib.util as _ilu
    real_find_spec = _ilu.find_spec

    def fake_find_spec(name, *a, **k):
        if name == "kubernetes":
            return None
        return real_find_spec(name, *a, **k)

    monkeypatch.setattr(tt.importlib.util, "find_spec", fake_find_spec)
    assert tt.check_terminal_requirements() is False


def test_check_requirements_kubernetes_present(monkeypatch):
    import tools.terminal_tool as tt
    monkeypatch.setattr(tt, "_get_env_config", lambda: {"env_type": "kubernetes"})
    monkeypatch.setattr(
        tt.importlib.util, "find_spec", lambda name, *a, **k: object()
    )
    assert tt.check_terminal_requirements() is True


# ---------------------------------------------------------------------------
# Regression: live terminal_tool() path correctly sets image + container_config
# ---------------------------------------------------------------------------


def test_live_terminal_tool_kubernetes_image_and_container_config(monkeypatch):
    """
    Exercises the live terminal_tool() entry path (not _create_environment directly).

    Before the fix, terminal_tool() had no 'kubernetes' branch in image-selection
    (defaulting to image="") and no 'kubernetes' branch in container_config-building
    (so kubernetes_* keys were never passed).  This test verifies both are now correct.

    Approach: live terminal_tool() path with monkeypatched _create_environment so no
    real cluster is needed.  We use force=True to bypass security guards, a UUID-style
    unique task_id to avoid the _active_environments cache, and pre-clean that key.
    """
    import uuid
    import tools.terminal_tool as tt

    # Unique task_id so the _active_environments cache cannot return a stale env.
    unique_task_id = f"k8s-regression-{uuid.uuid4().hex}"

    # Ensure the global registry is clear for this task_id (belt-and-suspenders).
    with tt._env_lock:
        tt._active_environments.pop(unique_task_id, None)

    # Capture _create_environment kwargs.
    captured = {}

    def _fake_create_environment(**kwargs):
        captured.update(kwargs)
        mock_env = MagicMock()
        mock_env.execute.return_value = {"output": "", "returncode": 0}
        return mock_env

    monkeypatch.setattr(tt, "_create_environment", _fake_create_environment)

    # Also stub _check_all_guards so force=True path runs cleanly regardless of tirith.
    monkeypatch.setattr(tt, "_check_all_guards", lambda cmd, env_type: {"approved": True})

    # Stub _start_cleanup_thread to avoid spawning background threads.
    monkeypatch.setattr(tt, "_start_cleanup_thread", lambda: None)

    # Set kubernetes env vars.
    monkeypatch.setenv("TERMINAL_ENV", "kubernetes")
    monkeypatch.setenv("TERMINAL_KUBERNETES_POD_SA", "custom-sa")
    monkeypatch.setenv("HERMES_POD_NAMESPACE", "hermes")
    monkeypatch.setenv("HERMES_POD_NAME", "hermes-agent-0")
    monkeypatch.setenv("HERMES_POD_UID", "uid-test")

    # Register a task override so _resolve_container_task_id keeps our unique ID.
    tt._task_env_overrides[unique_task_id] = {}
    try:
        tt.terminal_tool(command="echo hi", task_id=unique_task_id, force=True)
    finally:
        # Clean up global state.
        with tt._env_lock:
            tt._active_environments.pop(unique_task_id, None)
        tt._task_env_overrides.pop(unique_task_id, None)

    assert captured, "_create_environment was never called — env creation path not reached"
    assert captured["image"] == "ubuntu:22.04", (
        f"Expected image 'ubuntu:22.04', got {captured['image']!r}. "
        "The kubernetes image-selection branch is missing or broken."
    )
    cc = captured.get("container_config")
    assert cc is not None, (
        "container_config was None — the kubernetes branch was not added to the "
        "container_config building block."
    )
    assert cc["kubernetes_pod_service_account"] == "custom-sa", (
        f"Expected 'custom-sa', got {cc['kubernetes_pod_service_account']!r}. "
        "kubernetes_pod_service_account is not propagated from config into container_config."
    )
