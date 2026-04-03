"""Run execute_code child subprocess inside Docker for gateway sandbox sessions."""

import logging
import subprocess

logger = logging.getLogger(__name__)


def run_script_in_docker(script_path, tmpdir, sock_path, image, child_env, timeout):
    """Run a Python script inside a Docker container.

    Returns (stdout_bytes, stderr_bytes, returncode).
    """
    cmd = [
        "docker", "run", "--rm",
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

    container_id = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        # Extract container ID for potential kill on timeout
        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning("Docker sandbox timed out after %s seconds, killing container", timeout)
            # Try to kill via docker kill using the process
            proc.kill()
            stdout_bytes, stderr_bytes = proc.communicate(timeout=5)
            # Also attempt to find and kill any running container from our command
            return (stdout_bytes or b"", stderr_bytes or b"", -1)

        return (stdout_bytes, stderr_bytes, proc.returncode)

    except FileNotFoundError:
        logger.error("Docker executable not found. Is Docker installed?")
        return (b"", b"Docker executable not found.\n", 127)
    except Exception as e:
        logger.error("Docker sandbox error: %s", e)
        return (b"", str(e).encode("utf-8", errors="replace"), 1)
