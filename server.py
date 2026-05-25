from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

# Serve static assets
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

# Root → UI
@app.get("/")
def serve_ui():
    return FileResponse(WEB_DIR / "index.html")

# SPA fallback
@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    file_path = WEB_DIR / full_path
    if file_path.exists():
        return FileResponse(file_path)
    return FileResponse(WEB_DIR / "index.html")

# Chat endpoint
@app.post("/chat")
async def chat(data: dict):
    user_input = data.get("message", "")
    return {"response": f"Echo: {user_input}"}
