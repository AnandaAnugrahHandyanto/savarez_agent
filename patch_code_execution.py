import sys

# manually implement get_client_connect_code since we can't import
connect_code = '''def _connect():
    global _sock
    if _sock is None:
        port = int(os.environ.get("HERMES_RPC_PORT", "0"))
        token = os.environ.get("HERMES_RPC_TOKEN", "")
        socket_path = os.environ.get("HERMES_RPC_SOCKET", "")

        if port:
            _sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            _sock.connect(("127.0.0.1", port))
            _sock.settimeout(300)
            _sock.sendall((token + "\\\\n").encode())
        else:
            _sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            _sock.connect(socket_path)
            _sock.settimeout(300)
    return _sock
'''

with open("tools/code_execution_tool.py", "r") as f:
    content = f.read()

uds_start = content.find("_UDS_TRANSPORT_HEADER =")
uds_end = content.find("_FILE_TRANSPORT_HEADER =")
old_uds_section = content[uds_start:uds_end]

new_uds_section = '''_UDS_TRANSPORT_HEADER = \'\'\'\\
"""Auto-generated Hermes tools RPC stubs."""
import json, os, socket, shlex, time

_sock = None
\'\'\' + _COMMON_HELPERS + \'\'\'\\
''' + connect_code + '''
def _call(tool_name, args):
    """Send a tool call to the parent process and return the parsed result."""
    conn = _connect()
    request = json.dumps({"tool": tool_name, "args": args}) + "\\\\n"
    conn.sendall(request.encode())
    buf = b""
    while True:
        chunk = conn.recv(65536)
        if not chunk:
            raise RuntimeError("Agent process disconnected")
        buf += chunk
        if buf.endswith(b"\\\\n"):
            break
    raw = buf.decode().strip()
    result = json.loads(raw)
    if isinstance(result, str):
        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return result
    return result

\'\'\'

'''

content = content.replace(old_uds_section, new_uds_section)

with open("tools/code_execution_tool.py", "w") as f:
    f.write(content)
