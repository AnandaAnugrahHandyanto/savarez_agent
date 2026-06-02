"""Kubernetes session-pod execution environment.

Runs each command by exec-ing into a per-session pod in the same cluster.
Provisioning is behind WorkspaceProvisioner so the Phase-1 DirectProvisioner
(raw K8s API) can be swapped for an operator-CR provisioner later without
touching the exec loop. See
hermes-operator/docs/research/2026-05-23-kubernetes-exec-backend-design.md.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from tools.environments.base import BaseEnvironment, _ThreadedProcessHandle

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PodRef:
    """Coordinates for exec-ing into a session pod."""

    namespace: str
    pod_name: str
    container: str


@dataclass(frozen=True)
class Resources:
    """Resource request for a session pod (millicores / MiB / MiB)."""

    cpu: int = 1
    memory_mib: int = 5120
    disk_mib: int = 51200


class WorkspaceProvisioner(ABC):
    """Creates and destroys the session pod (and its PVC, when persistent)."""

    @abstractmethod
    def ensure(
        self, task_id: str, persistent: bool, image: str, resources: Resources
    ) -> PodRef:
        """Create (or resume) the session pod; return a PodRef once Ready."""
        ...

    @abstractmethod
    def destroy(self, pod_ref: PodRef, persistent: bool) -> None:
        """Delete the session pod. Keep the PVC iff persistent."""
        ...


class DirectProvisioner(WorkspaceProvisioner):
    """Creates session pods/PVCs directly via the in-cluster K8s API.

    The pod shape is deliberately constrained to satisfy the operator's
    secure-pod ValidatingAdmissionPolicy: no host namespaces, a no-perms SA
    with the token unmounted, runAsNonRoot, drop-ALL caps, no privilege
    escalation. The session pod carries an ownerReference to the agent's own
    pod so it is garbage-collected if the agent crashes.
    """

    _READY_TIMEOUT = 120  # seconds to wait for pod Ready

    def __init__(
        self,
        namespace: str,
        pod_service_account: str,
        owner_pod_name: str,
        owner_pod_uid: str,
        image_pull_secrets: list[str] | None = None,
        run_as_user: int = 1000,
        active_deadline_seconds: int = 14400,
        api=None,
    ):
        self.namespace = namespace
        self.pod_service_account = pod_service_account
        self.owner_pod_name = owner_pod_name
        self.owner_pod_uid = owner_pod_uid
        self.image_pull_secrets = image_pull_secrets or []
        self.run_as_user = run_as_user
        # Hard ceiling on an EPHEMERAL pod's total lifetime — a backstop that
        # bounds any leak (e.g. an orphaned pod in a no-ownerRef topology).
        # Must exceed the longest legitimate session; not applied to persistent
        # pods (their workspace is meant to outlive a single session).
        self.active_deadline_seconds = active_deadline_seconds
        self._api = api  # kubernetes.client.CoreV1Api (None in manifest tests)

    @staticmethod
    def _pod_name(task_id: str) -> str:
        return f"hermes-ws-{task_id}"

    @staticmethod
    def _pvc_name(task_id: str) -> str:
        return f"hermes-ws-{task_id}"

    def _owner_reference(self) -> dict | None:
        # Only emit an ownerRef when we actually know the agent pod's identity
        # (in-cluster, via the downward API). K8s rejects an ownerRef with an
        # empty name/uid, so when owner info is absent (e.g. host-driven dev /
        # kubeconfig use) we omit it — there's no agent pod to GC against.
        if not (self.owner_pod_name and self.owner_pod_uid):
            return None
        return {
            "apiVersion": "v1",
            "kind": "Pod",
            "name": self.owner_pod_name,
            "uid": self.owner_pod_uid,
            "controller": False,
            "blockOwnerDeletion": False,
        }

    def _pvc_manifest(self, task_id: str, resources: "Resources") -> dict:
        # No ownerRef: a persistent PVC must outlive the agent pod.
        return {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {
                "name": self._pvc_name(task_id),
                "namespace": self.namespace,
                "labels": {"app.kubernetes.io/managed-by": "hermes-agent"},
            },
            "spec": {
                "accessModes": ["ReadWriteOnce"],
                "resources": {
                    "requests": {"storage": f"{resources.disk_mib}Mi"}
                },
            },
        }

    def _pod_manifest(
        self, task_id: str, persistent: bool, image: str, resources: "Resources"
    ) -> dict:
        if persistent:
            workspace_volume = {
                "name": "workspace",
                "persistentVolumeClaim": {"claimName": self._pvc_name(task_id)},
            }
        else:
            workspace_volume = {"name": "workspace", "emptyDir": {}}

        metadata = {
            "name": self._pod_name(task_id),
            "namespace": self.namespace,
            "labels": {"app.kubernetes.io/managed-by": "hermes-agent"},
        }
        owner = self._owner_reference()
        if owner is not None:
            # GC the session pod when the agent pod dies.
            metadata["ownerReferences"] = [owner]

        spec = {
            "restartPolicy": "Never",
            "automountServiceAccountToken": False,
            "serviceAccountName": self.pod_service_account,
            "hostNetwork": False,
            "hostPID": False,
            "hostIPC": False,
            # Pod-level securityContext: runAsNonRoot needs a concrete
            # runAsUser or kubelet rejects images whose default user is
            # root (e.g. ubuntu) with "container has runAsNonRoot and
            # image will run as root". fsGroup makes the /workspace volume
            # group-writable so the non-root uid can actually write to it
            # (emptyDir/PVC mount as root:root 0755 otherwise).
            "securityContext": {
                "runAsNonRoot": True,
                "runAsUser": self.run_as_user,
                "fsGroup": self.run_as_user,
            },
            "imagePullSecrets": [
                {"name": n} for n in self.image_pull_secrets
            ],
            "containers": [
                {
                    "name": "workspace",
                    "image": image,
                    # Keep the pod alive so we can exec repeatedly.
                    "command": ["sleep", "infinity"],
                    "workingDir": "/workspace",
                    "volumeMounts": [
                        {"name": "workspace", "mountPath": "/workspace"}
                    ],
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": self.run_as_user,
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                    },
                    "resources": {
                        "requests": {
                            "cpu": str(resources.cpu),
                            "memory": f"{resources.memory_mib}Mi",
                        }
                    },
                }
            ],
            "volumes": [workspace_volume],
        }
        if not persistent:
            # Hard lifetime ceiling for ephemeral pods (leak backstop). Not set
            # for persistent pods — their workspace is meant to be long-lived.
            spec["activeDeadlineSeconds"] = self.active_deadline_seconds

        return {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": metadata,
            "spec": spec,
        }

    def ensure(
        self, task_id: str, persistent: bool, image: str, resources: Resources
    ) -> PodRef:
        from kubernetes.client.exceptions import ApiException

        if persistent:
            try:
                self._api.read_namespaced_persistent_volume_claim(
                    name=self._pvc_name(task_id), namespace=self.namespace
                )
            except ApiException as exc:
                if exc.status != 404:
                    raise
                self._api.create_namespaced_persistent_volume_claim(
                    namespace=self.namespace,
                    body=self._pvc_manifest(task_id, resources),
                )

        try:
            self._api.create_namespaced_pod(
                namespace=self.namespace,
                body=self._pod_manifest(task_id, persistent, image, resources),
            )
        except ApiException as exc:
            # 409 = pod already exists (persistent resume after a soft stop
            # that didn't fully delete, or a racing session). Reuse it.
            if exc.status != 409:
                raise

        self._wait_ready(self._pod_name(task_id))
        return PodRef(self.namespace, self._pod_name(task_id), "workspace")

    def _wait_ready(self, pod_name: str) -> None:
        import time

        deadline = time.monotonic() + self._READY_TIMEOUT
        while time.monotonic() < deadline:
            pod = self._api.read_namespaced_pod(
                name=pod_name, namespace=self.namespace
            )
            conditions = getattr(pod.status, "conditions", None) or []
            ready = any(
                c.type == "Ready" and c.status == "True" for c in conditions
            )
            if pod.status.phase == "Running" and ready:
                return
            if pod.status.phase in ("Failed", "Succeeded"):
                raise RuntimeError(
                    f"session pod {pod_name} entered phase {pod.status.phase}"
                )
            time.sleep(0.5)
        raise TimeoutError(
            f"session pod {pod_name} not Ready after {self._READY_TIMEOUT}s"
        )

    def destroy(self, pod_ref: PodRef, persistent: bool) -> None:
        from kubernetes.client.exceptions import ApiException

        try:
            self._api.delete_namespaced_pod(
                name=pod_ref.pod_name, namespace=pod_ref.namespace
            )
        except ApiException as exc:
            if exc.status != 404:
                logger.warning("k8s: failed to delete pod %s: %s",
                               pod_ref.pod_name, exc)
        # Persistent: keep the PVC so the next session resumes the filesystem.


class KubernetesEnvironment(BaseEnvironment):
    """Exec-into-session-pod backend. Lifecycle delegated to a provisioner."""

    _stdin_mode = "heredoc"  # no real stdin pipe over the exec channel
    _snapshot_timeout = 60  # pod cold-start can be slow

    def __init__(
        self,
        provisioner: WorkspaceProvisioner,
        task_id: str,
        persistent: bool,
        image: str,
        cwd: str = "/workspace",
        timeout: int = 60,
        resources: "Resources | None" = None,
        api=None,
    ):
        super().__init__(cwd=cwd, timeout=timeout)
        self._provisioner = provisioner
        self._persistent = persistent
        self._exec_api = api  # configured CoreV1Api; falls back to a fresh one
        self._pod_ref = provisioner.ensure(
            task_id=task_id,
            persistent=persistent,
            image=image,
            resources=resources or Resources(),
        )
        self.init_session()

    def _run_bash(
        self, cmd_string: str, *, login: bool = False, timeout: int = 120,
        stdin_data: str | None = None,
    ):
        from kubernetes.stream import stream as k8s_stream
        from kubernetes.client import CoreV1Api

        ref = self._pod_ref
        shell = "bash -l -c" if login else "bash -c"
        command = [*shell.split(), cmd_string]

        def exec_fn() -> tuple[str, int]:
            api = self._exec_api or CoreV1Api()
            resp = k8s_stream(
                api.connect_get_namespaced_pod_exec,
                ref.pod_name,
                ref.namespace,
                container=ref.container,
                command=command,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _preload_content=False,
            )
            chunks: list[str] = []
            while resp.is_open():
                resp.update(timeout=1)
                if resp.peek_stdout():
                    chunks.append(resp.read_stdout())
                if resp.peek_stderr():
                    chunks.append(resp.read_stderr())
            # Drain any tail buffered by the final update() before closing.
            if resp.peek_stdout():
                chunks.append(resp.read_stdout())
            if resp.peek_stderr():
                chunks.append(resp.read_stderr())
            resp.close()
            rc = resp.returncode
            return "".join(chunks), (rc if rc is not None else 0)

        def cancel() -> None:
            # Ephemeral: tearing the pod down is the cleanest interrupt.
            # Persistent: leave the pod; closing the stream stops the exec'd
            # process when the WSClient is GC'd.
            if not self._persistent:
                try:
                    self._provisioner.destroy(self._pod_ref, persistent=False)
                except Exception:
                    pass

        return _ThreadedProcessHandle(exec_fn, cancel_fn=cancel)

    def cleanup(self):
        ref = getattr(self, "_pod_ref", None)
        if ref is None:
            return
        try:
            self._provisioner.destroy(ref, self._persistent)
        except Exception as exc:
            logger.warning("k8s: cleanup failed: %s", exc)
        self._pod_ref = None
