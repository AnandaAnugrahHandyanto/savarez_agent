"""Run execute_code child subprocess inside Docker for gateway sandbox sessions."""

import logging
import subprocess
import uuid

logger = logging.getLogger(__name__)


def run_script_in_docker(script_path, tmpdir, sock_path, image, child_env, timeout):
    """Run a Python script inside a Docker container.

    Returns (stdout_bytes, stderr_bytes, returncode).

    Known limitation: this function uses blocking communicate() and cannot be
    interrupted by the _interrupt_event used by the local subprocess path.
    If the user sends a cancellation message mid-run, the Docker container will
    run to completion (or timeout). Tracked in: gh issue (follow-up).
    """
    container_name = f"hermes-sandbox-{uuid.uuid4().hex[:8]}"
    cmd = [
        "docker", "run", "--rm",
        "--name", container_name,
        "-v", f"{tmpdir}:{tmpdir}",
        "-v", "/tmp:/tmp",
        "-e", f"HERMES_RPC_SOCKET={sock_path}",
        "--network=host",
    ]

    # Pass child_env vars as -e flags
    for key, val in child_env.items():
        if not key or "=" in key or val is None:
            continue
        cmd.extend(["-e", f"{key}={val}"])

    cmd.extend([image, "python3", script_path])

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning(
                "Docker sandbox timed out after %s seconds, killing container %s",
                timeout,
                container_name,
            )
            # Kill the container by name first (removes the process inside Docker),
            # then kill the Docker CLI client process.
            subprocess.run(
                ["docker", "kill", container_name],
                timeout=5,
                capture_output=True,
            )
            proc.kill()
            stdout_bytes, stderr_bytes = proc.communicate(timeout=5)
            return (stdout_bytes or b"", stderr_bytes or b"", -1)

        return (stdout_bytes, stderr_bytes, proc.returncode)

    except FileNotFoundError:
        logger.error("Docker executable not found. Is Docker installed?")
        return (b"", b"Docker executable not found.\n", 127)
    except Exception as e:
        logger.error("Docker sandbox error: %s", e)
        return (b"", str(e).encode("utf-8", errors="replace"), 1)
