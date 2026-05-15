"""Integration test for FastVM tar bulk upload.

Requires FASTVM_API_KEY to be set. Run with:
    uv run --locked --extra dev --extra fastvm pytest \
        tests/integration/test_fastvm_bulk_upload.py -q -o addopts=''
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import uuid

import pytest

pytestmark = pytest.mark.integration

FASTVM_API_KEY = os.getenv("FASTVM_API_KEY")

if not FASTVM_API_KEY:
    pytest.skip("FASTVM_API_KEY not set", allow_module_level=True)


class RecordingFastvmClient:
    def __init__(self):
        from fastvm import FastvmClient

        self._inner = FastvmClient(api_key=FASTVM_API_KEY)
        self.vms = self._inner.vms
        self.snapshots = self._inner.snapshots
        self.upload_calls: list[dict[str, object]] = []

    def upload(self, vm_id: str, local_path: str, remote_path: str, **kwargs):
        path = Path(local_path)
        self.upload_calls.append(
            {
                "vm_id": vm_id,
                "local_path": local_path,
                "remote_path": remote_path,
                "size": path.stat().st_size,
            }
        )
        return self._inner.upload(vm_id, local_path, remote_path, **kwargs)

    def download(self, vm_id: str, remote_path: str, local_path: str, **kwargs):
        return self._inner.download(vm_id, remote_path, local_path, **kwargs)


def _extract_id(value) -> str | None:
    if isinstance(value, dict):
        return value.get("id")
    return getattr(value, "id", None)


def _cleanup_test_vms(client: RecordingFastvmClient, task_id: str) -> None:
    try:
        response = client.vms.list(
            status="running",
            extra_query={
                "metadata.hermes_backend": "fastvm",
                "metadata.hermes_task_id": task_id,
            },
        )
    except Exception:
        return

    for vm in response or []:
        vm_id = _extract_id(vm)
        if not vm_id:
            continue
        try:
            client.vms.delete(vm_id)
        except Exception:
            pass


def test_fastvm_initial_sync_uses_one_real_tar_upload(monkeypatch, tmp_path):
    from tools.environments.fastvm import FastVMEnvironment

    local_files = {
        "alpha.txt": b"alpha\n",
        "nested/beta.txt": b"beta\n",
        "nested/deeper/gamma.json": b'{"gamma": true}\n',
    }
    mounts = []
    for rel_path, content in local_files.items():
        host_path = tmp_path / "host" / rel_path
        host_path.parent.mkdir(parents=True, exist_ok=True)
        host_path.write_bytes(content)
        mounts.append(
            {
                "host_path": str(host_path),
                "container_path": f"/root/.hermes/fastvm-bulk-upload/{rel_path}",
            }
        )

    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))
    monkeypatch.setattr("tools.credential_files.get_credential_file_mounts", lambda: mounts)
    monkeypatch.setattr("tools.credential_files.iter_skills_files", lambda **kwargs: [])
    monkeypatch.setattr("tools.credential_files.iter_cache_files", lambda **kwargs: [])

    task_id = f"fastvm-bulk-upload-{uuid.uuid4().hex[:12]}"
    client = RecordingFastvmClient()
    env = None
    try:
        env = FastVMEnvironment(
            machine_type="c1m2",
            disk_gib=10,
            persistent_filesystem=False,
            live_resume=False,
            task_id=task_id,
            launch_timeout=300,
            snapshot_timeout=300,
            _client=client,
        )

        assert len(client.upload_calls) == 1
        upload = client.upload_calls[0]
        remote_tar = str(upload["remote_path"])
        assert remote_tar.startswith("/tmp/.hermes_upload.")
        assert remote_tar.endswith(".tar.gz")

        remote_base = (
            "/.hermes"
            if env._remote_home == "/"
            else f"{env._remote_home.rstrip('/')}/.hermes"
        )
        expected_hashes = {
            f"{remote_base}/fastvm-bulk-upload/{rel_path}": hashlib.sha256(
                content
            ).hexdigest()
            for rel_path, content in local_files.items()
        }
        verify = env.execute(
            "python3 - <<'PY'\n"
            "import hashlib, pathlib, sys\n"
            f"expected = {json.dumps(expected_hashes, sort_keys=True)!r}\n"
            "import json\n"
            "expected = json.loads(expected)\n"
            "for path, digest in expected.items():\n"
            "    data = pathlib.Path(path).read_bytes()\n"
            "    actual = hashlib.sha256(data).hexdigest()\n"
            "    if actual != digest:\n"
            "        print(f'{path}: {actual} != {digest}', file=sys.stderr)\n"
            "        raise SystemExit(1)\n"
            "print('uploaded files verified')\n"
            "PY",
            timeout=60,
        )
        assert verify["returncode"] == 0, verify["output"]
        assert "uploaded files verified" in verify["output"]

        cleanup_check = env.execute(
            f"test ! -e {shlex.quote(remote_tar)} && echo remote-tar-cleaned",
            timeout=30,
        )
        assert cleanup_check["returncode"] == 0, cleanup_check["output"]
        assert "remote-tar-cleaned" in cleanup_check["output"]
        assert len(client.upload_calls) == 1
    finally:
        if env is not None:
            env.cleanup()
        _cleanup_test_vms(client, task_id)
