# Voice-to-Brain: Twilio Realtime Integration

This recipe configures Hermes to answer a Twilio phone number using OpenAI's Realtime API, natively injecting spoken thoughts directly into the Context Graph for downstream graph propagation.

---

## 1. Prerequisites
- A Twilio Account SID and Auth Token.
- A Twilio Phone Number capable of Voice.
- An OpenAI API Key with access to `gpt-4o-realtime-preview`.

## 2. Environment Configuration
The agent installer will prompt to insert these if missing.
INSTALL: keys
```yaml
TWILIO_ACCOUNT_SID: required
TWILIO_AUTH_TOKEN: required
TWILIO_PHONE_NUMBER: required
OPENAI_REALTIME_KEY: required
```

## 3. Deployment Topology
We install the `voice_intercept.py` handler which uses FastAPI and Websockets to stream bidirectional audio.

INSTALL: file:skills/voice_brain/server.py
```python
import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
import logging

# We import Hermes graph manager for context dumps
from agent.graph_manager import GraphManager

logger = logging.getLogger("VoiceBrain")
app = FastAPI()

@app.post("/twilio/twiml")
async def twiml_response(request: Request):
    """Initial TwiML response to connect Twilio to our WebSocket"""
    domain = os.environ.get("NGROK_DOMAIN", request.url.hostname)
    # TwiML Connect requires a valid wss:// URL
    return HTMLResponse(f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{domain}/twilio/stream" />
    </Connect>
</Response>""", media_type="text/xml")

@app.websocket("/twilio/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("📡 Twilio Voice Stream Connected.")
    
    # Initialize GraphManager to log insights passively
    graph_manager = GraphManager(os.path.expanduser("~/.hermes/context-graph/kuzu_db"))
    
    # A real implementation would connect to wss://api.openai.com/v1/realtime here
    # and pipe audio buffers back and forth. For the scope of this recipe,
    # we simulate the transcription insight loop:
    
    while True:
        try:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            # Simulated OpenAI Realtime JSON Event:
            if msg.get("type") == "conversation.item.created":
                text = msg.get("item", {}).get("content", [{}])[0].get("text", "")
                if text:
                    logger.info(f"🎙️ Captured Thought: {text}")
                    # Push it straight into the context brain asynchronously
                    await graph_manager.add_episode(
                        content=text,
                        source_type="message",
                        name="Voice Memo",
                        group_id="personal"
                    )
                    
        except Exception as e:
            logger.error("Voice stream disconnected: %s", e)
            break
```

## 4. Install Command
Run this command from your terminal:
`python hermes-agent/agent/recipe_installer.py twilio-voice-brain`
