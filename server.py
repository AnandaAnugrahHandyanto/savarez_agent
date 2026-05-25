import os
import subprocess
import threading
import time
from fastapi import FastAPI
import uvicorn

print("[server] Booting system...")

# --- HTTP App ---
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

# --- Start Hermes Gateway ---
def start_gateway():
    print("[server] Starting Hermes Gateway...")
    return subprocess.Popen(
        ["hermes", "gateway", "run"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

# --- Stream logs ---
def stream_logs(proc):
    for line in proc.stdout:
        line = line.strip()
        print(f"[gateway] {line}")

        if "error" in line.lower():
            print(f"[DEBUG-ERROR] {line}")

# --- Gateway Manager ---
def manage_gateway():
    global gateway_process
    gateway_process = start_gateway()

    log_thread = threading.Thread(
        target=stream_logs,
        args=(gateway_process,),
        daemon=True
    )
    log_thread.start()

    while True:
        time.sleep(5)

        if gateway_process.poll() is not None:
            print("[server] Gateway crashed!")
            print(f"[server] Exit code: {gateway_process.returncode}")

            print("[server] Restarting gateway...")
            gateway_process = start_gateway()

# --- Start everything ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))

    # Start gateway in background thread
    threading.Thread(target=manage_gateway, daemon=True).start()

    print(f"[server] Starting HTTP server on port {port}...")

    uvicorn.run(app, host="0.0.0.0", port=port)
