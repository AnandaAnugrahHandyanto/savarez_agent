"""Hermes execution environment backends.

Each backend provides the same interface (BaseEnvironment ABC) for running
shell commands in a specific execution context: local, Docker, Singularity,
SSH, Modal, or Daytona.

The terminal_tool.py factory (_create_environment) selects the backend
based on the TERMINAL_ENV configuration.
"""

from tools.environments.base import BaseEnvironment

# Backward-compatible export expected by some tool tests and older code paths.
# CI logs mention `tools.environments.environments` missing.
#
# We keep imports inside try/except because some backends (e.g. modal/daytona)
# can require optional SDKs at import-time.
environments = {}
try:
    from tools.environments.local import LocalEnvironment  # type: ignore

    environments["local"] = LocalEnvironment
except Exception:
    pass

try:
    from tools.environments.ssh import SSHEnvironment  # type: ignore

    environments["ssh"] = SSHEnvironment
except Exception:
    pass

try:
    from tools.environments.docker import DockerEnvironment  # type: ignore

    environments["docker"] = DockerEnvironment
except Exception:
    pass

try:
    from tools.environments.singularity import SingularityEnvironment  # type: ignore

    environments["singularity"] = SingularityEnvironment
except Exception:
    pass

try:
    from tools.environments.modal import ModalEnvironment  # type: ignore

    environments["modal"] = ModalEnvironment
except Exception:
    pass

try:
    from tools.environments.daytona import DaytonaEnvironment  # type: ignore

    environments["daytona"] = DaytonaEnvironment
except Exception:
    pass

__all__ = ["BaseEnvironment", "environments"]
