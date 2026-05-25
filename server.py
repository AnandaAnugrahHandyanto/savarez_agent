"""
INSTRUCTIONS:

1. Place this file at the root of your repo.
2. Ensure /web folder exists with:
   - index.html
   - styles.css
   - app.js
   - components/*
3. This server:
   - Serves UI at "/"
   - Serves static assets automatically
   - Keeps API space open for Hermes endpoints
4. Railway will run this using start.sh
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

app = FastAPI()

# Path to web folder
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

# ✅ 1. Serve static files (CSS, JS, etc.)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

# ✅ 2. Root route → load index.html
@app.get("/")
def serve_ui():
    return FileResponse(WEB_DIR / "index.html")

# ✅ 3. Catch-all route for SPA behavior (prevents 404 on reload)
@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    file_path = WEB_DIR / full_path

    # If file exists → serve it
    if file_path.exists():
        return FileResponse(file_path)

    # Otherwise fallback to index.html
    return FileResponse(WEB_DIR / "index.html")


# ✅ 4. (OPTIONAL) Basic chat endpoint placeholder
@app.post("/chat")
async def chat_endpoint(data: dict):
    """
    INSTRUCTIONS:
    Replace this with Hermes agent logic.
    Frontend will call this endpoint later.
    """
    user_input = data.get("message", "")

    return {
        "response": f"Echo: {user_input}"
    }
