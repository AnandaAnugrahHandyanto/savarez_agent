"""kind integration tests for the Kubernetes terminal backend.

Requires a running kind cluster reachable via the default kubeconfig and
RBAC allowing pod create/exec/delete + PVC create in the target namespace.
Excluded from CI (integration marker); developers run locally with:
  HERMES_K8S_KIND_TEST=1 python -m pytest tests/integration/test_kubernetes_terminal.py -v
"""

import os
import uuid

import pytest

# integration marker -> excluded by CI's `addopts = -m 'not integration'`,
# matching tests/integration/test_daytona_terminal.py. Plus an env-gate so it
# no-ops unless a kind cluster is explicitly opted into.
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("HERMES_K8S_KIND_TEST") != "1",
        reason="set HERMES_K8S_KIND_TEST=1 to run against a kind cluster",
    ),
]

NAMESPACE = os.getenv("HERMES_K8S_KIND_NS", "default")
IMAGE = os.getenv("HERMES_K8S_KIND_IMAGE", "ubuntu:22.04")


def _provisioner(api):
    from tools.environments.kubernetes import DirectProvisioner
    return DirectProvisioner(
        namespace=NAMESPACE,
        pod_service_account="default",
        owner_pod_name="",   # no ownerRef in kind test (no agent pod)
        owner_pod_uid="",
        api=api,
    )


@pytest.fixture()
def api():
    from kubernetes import config, client
    config.load_kube_config()
    return client.CoreV1Api()


def test_ephemeral_roundtrip(api):
    from tools.environments.kubernetes import KubernetesEnvironment, Resources
    prov = _provisioner(api)
    task = f"it-{uuid.uuid4().hex[:8]}"
    env = KubernetesEnvironment(
        provisioner=prov, task_id=task, persistent=False, image=IMAGE,
        timeout=120, resources=Resources(memory_mib=512, disk_mib=1024),
        api=api,
    )
    try:
        result = env.execute("echo hello-from-pod")
        assert "hello-from-pod" in result["output"]
        assert result["returncode"] == 0
    finally:
        env.cleanup()


def test_persistent_filesystem_survives_pod_recreation(api):
    from tools.environments.kubernetes import KubernetesEnvironment, Resources
    task = f"it-{uuid.uuid4().hex[:8]}"

    env1 = KubernetesEnvironment(
        provisioner=_provisioner(api), task_id=task, persistent=True,
        image=IMAGE, timeout=120, resources=Resources(memory_mib=512, disk_mib=1024),
        api=api,
    )
    try:
        env1.execute("echo persisted > /workspace/marker.txt")
    finally:
        env1.cleanup()  # deletes pod, keeps PVC

    env2 = KubernetesEnvironment(
        provisioner=_provisioner(api), task_id=task, persistent=True,
        image=IMAGE, timeout=120, resources=Resources(memory_mib=512, disk_mib=1024),
        api=api,
    )
    try:
        result = env2.execute("cat /workspace/marker.txt")
        assert "persisted" in result["output"]
    finally:
        env2.cleanup()
        try:
            api.delete_namespaced_persistent_volume_claim(
                name=f"hermes-ws-{task}", namespace=NAMESPACE
            )
        except Exception:
            pass
