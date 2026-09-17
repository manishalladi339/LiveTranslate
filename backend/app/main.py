import logging
from functools import lru_cache

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .languages import LANGUAGES, validate_pair
from .models import TranslateRequest, TranslateResponse
from .translator import Translator, TranslationBusyError

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@lru_cache
def get_translator() -> Translator:
    return Translator(settings)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "provider": settings.translation_provider}


@app.get("/api/v1/languages")
async def languages() -> dict[str, object]:
    return {"languages": LANGUAGES, "provider": settings.translation_provider}


@app.post("/api/v1/translate", response_model=TranslateResponse)
async def translate(payload: TranslateRequest) -> TranslateResponse:
    try:
        return await get_translator().translate(
            payload.text, payload.source_language, payload.target_language
        )
    except TranslationBusyError as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": "60"}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (httpx.HTTPError, RuntimeError, KeyError, TypeError) as exc:
        logger.exception("Translation failed")
        raise HTTPException(status_code=502, detail="Translation provider unavailable") from exc


@app.websocket("/api/v1/live/{session_id}")
async def live_translate(websocket: WebSocket, session_id: str) -> None:
    origin = websocket.headers.get("origin")
    if origin and origin not in settings.allowed_origins:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    await websocket.send_json({"type": "ready", "session_id": session_id})
    try:
        while True:
            try:
                message = await websocket.receive_json()
            except ValueError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue
            if not isinstance(message, dict):
                await websocket.send_json({"type": "error", "message": "Expected a JSON object"})
                continue
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if message.get("type") != "translate":
                await websocket.send_json({"type": "error", "message": "Unsupported message type"})
                continue
            text = message.get("text", "")
            if not isinstance(text, str) or not text.strip() or len(text) > settings.max_text_length:
                await websocket.send_json({"type": "error", "message": "Text must be 1–2000 characters"})
                continue
            text = text.strip()
            source = str(message.get("source_language", ""))
            target = str(message.get("target_language", ""))
            try:
                validate_pair(source, target)
                result = await get_translator().translate(text, source, target)
                await websocket.send_json(
                    {
                        "type": "translation",
                        "turn_id": message.get("turn_id"),
                        "is_final": bool(message.get("is_final", True)),
                        **result.model_dump(),
                    }
                )
            except (ValueError, TranslationBusyError) as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
            except Exception:
                logger.exception("WebSocket translation failed")
                await websocket.send_json({"type": "error", "message": "Translation provider unavailable"})
    except WebSocketDisconnect:
        logger.info("LiveTranslate session disconnected: %s", session_id)
