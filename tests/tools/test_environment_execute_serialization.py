"""Regression tests for stateful terminal environment execution."""

import threading
import time

from tools.environments.base import BaseEnvironment


class _SerializedProbeEnvironment(BaseEnvironment):
    def __init__(self):
        self.active = 0
        self.max_active = 0
        self._probe_lock = threading.Lock()
        super().__init__(cwd="/tmp", timeout=5)

    def init_session(self):
        self._snapshot_ready = False

    def _run_bash(self, cmd_string, *, login=False, timeout=120, stdin_data=None):
        with self._probe_lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(0.05)
        with self._probe_lock:
            self.active -= 1
        return object()

    def _wait_for_process(self, proc, timeout=120):
        return {"output": "", "returncode": 0}

    def cleanup(self):
        return None


def test_environment_execute_is_serialized_per_environment():
    env = _SerializedProbeEnvironment()

    threads = [
        threading.Thread(target=env.execute, args=(f"echo {i}",))
        for i in range(6)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert env.max_active == 1
