import json
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.flow_engine import handle_turn

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session_id = str(uuid.uuid4())

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)

            if data.get("type") == "user_message":
                user_text = data.get("text") or ""
                resp = handle_turn(session_id, user_text)
                for a in resp.actions:
                    await ws.send_json(a.model_dump())

            if data.get("type") == "ui_event":
                target = data.get("target") or ""
                resp = handle_turn(session_id, f"__clicked__:{target}")
                for a in resp.actions:
                    await ws.send_json(a.model_dump())

    except WebSocketDisconnect:
        return
