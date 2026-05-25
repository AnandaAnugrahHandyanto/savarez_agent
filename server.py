import os
import subprocess
import threading
import time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI()

# ✅ Static UI
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def home():
    with open("static/index.html") as f:
        return f.read()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/status")
async def status():
    return {"status": "running"}


@app.get("/logs")
async def logs():
    return {"logs": ["Logs coming soon"]}


@app.post("/restart")
async def restart():
    return {"status": "restart triggered"}


# ✅ CHAT ENDPOINT (your UI will use this)
@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")

    try:
        result = subprocess.run(
            ["hermes", "chat", "-z", message],
            capture_output=True,
            text=True
        )
        return {"response": result.stdout.strip()}

    except Exception as e:
        return {"response": str(e)}


# ✅ Gateway background runner
def run_gateway():
    while True:
        print("[gateway] starting...")
        p = subprocess.Popen(
            ["hermes", "gateway", "run"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        for line in p.stdout:
            print("[gateway]", line.strip())

        print("[gateway] crashed → restarting...")
        time.sleep(2)


# ✅ Start everything
if __name__ == "__main__":
    threading.Thread(target=run_gateway, daemon=True).start()

    port = int(os.environ.get("PORT", 8080))
    print(f"[server] listening on {port}")

    uvicorn.run(app, host="0.0.0.0", port=port)
