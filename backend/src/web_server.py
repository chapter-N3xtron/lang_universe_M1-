"""FastAPI sidecar for the LangGraph Agent Chat UI.

Single-responsibility bridge for the few things the browser cannot do directly:
Kyutai Pocket TTS streaming, faster-whisper STT, the local Ollama model list,
and the native macOS folder picker. The LangGraph graph itself runs separately
on port 8123 — the sidecar intentionally owns no graph state.
"""

import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.coding_agent import export_coding_session_state
from src.document_attachments import (
    MAX_ATTACHMENT_BYTES,
    DocumentAttachmentError,
    load_selected_document,
    preserve_ocr_upload,
    supported_extensions,
)
from src.epub_attachments import (
    MAX_EPUB_BYTES,
    EpubAttachmentError,
    extract_epub,
)
from src.ollama_client import list_ollama_cloud_models, list_ollama_models
from src.openai_client import list_openai_gpt_models
from src.stt import transcribe
from src.workspace_policy import WorkspacePolicyError, canonical_workspace

load_dotenv()


def _allowed_origins() -> list[str]:
    """Allowed origins for CORS, configurable via env.

    Per the FastAPI CORS docs, `allow_origins=["*"]` combined with
    `allow_credentials=True` is invalid for credentialed requests, so we
    default to the two localhost origins the UI uses.
    """
    raw = os.getenv("SIDECAR_ALLOWED_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]


app = FastAPI(
    title="LangGraph Agent Chat UI — Sidecar",
    description="Local bridge for TTS, STT, model list, and folder picker.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


TODOS_FILE = os.getenv(
    "TODOS_FILE", str(Path(__file__).resolve().parent.parent.parent / "todos.json")
)


def _load_todos() -> dict:
    try:
        with open(TODOS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"version": 1, "sections": []}


@app.get("/api/todos")
def get_todos() -> dict:
    return _load_todos()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


class CodingSessionScope(BaseModel):
    thread_id: str
    workspace: str
    user_id: str = "anonymous"


def _session_workspace(raw_workspace: str) -> Path:
    try:
        return canonical_workspace(raw_workspace)
    except WorkspacePolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/coding-sessions/reset")
async def reset_coding_session_api(_scope: CodingSessionScope) -> dict:
    raise HTTPException(
        status_code=410,
        detail="Coder-only reset is retired; start a linked thread or fork instead.",
    )


@app.get("/api/coding-sessions/export")
async def export_coding_session_api(
    thread_id: str, workspace: str, user_id: str = "anonymous"
) -> dict:
    return await export_coding_session_state(
        thread_identity=thread_id,
        workspace=_session_workspace(workspace),
        user_identity=user_id,
    )


class TTSStreamRequest(BaseModel):
    text: str
    voice: str = ""
    chunk_size: int = 20


@app.post("/api/tts/stream")
async def tts_stream(request: TTSStreamRequest):
    """Stream TTS audio chunks as they're synthesized (Server-Sent Events)."""
    import base64

    from src.kyutai_tts import get_tts_engine

    engine = get_tts_engine()

    async def generate():
        try:
            async for chunk, metadata in engine.synthesize_streaming(
                text=request.text,
                voice=request.voice,
                chunk_size=request.chunk_size,
            ):
                audio_b64 = base64.b64encode(chunk.tobytes()).decode()
                event_data = {
                    "audio": audio_b64,
                    "shape": list(chunk.shape),
                    "dtype": str(chunk.dtype),
                    **metadata,
                }
                yield f"data: {json.dumps(event_data)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/tts/voices")
async def list_voices() -> dict:
    """List available voice embeddings."""
    from src.kyutai_tts import get_tts_engine

    engine = get_tts_engine()
    voices = await engine.list_voices()
    return {
        "voices": voices,
        "total": len(voices),
    }


@app.post("/api/stt")
def stt(audio: UploadFile) -> dict:
    try:
        audio_bytes = audio.file.read()
        text = transcribe(audio_bytes)
        return {"transcript": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/attachments/epub")
async def extract_epub_attachment(publication: UploadFile) -> dict:
    """Extract only the explicitly uploaded EPUB; no local path is accepted."""

    data = await publication.read(MAX_EPUB_BYTES + 1)
    try:
        return extract_epub(data, publication.filename or "publication.epub")
    except EpubAttachmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/attachments/formats")
def attachment_formats() -> dict:
    return {"extensions": supported_extensions()}


@app.post("/api/attachments/document")
async def extract_document_attachment(document: UploadFile) -> dict:
    """Normalize one explicitly uploaded file; local paths are never accepted."""

    data = await document.read(MAX_ATTACHMENT_BYTES + 1)
    try:
        filename = document.filename or "attachment"
        try:
            normalized = load_selected_document(data, filename)
        except DocumentAttachmentError as exc:
            # A validated image-only/scanned document still needs a durable
            # upload reference so the OCR specialist can process it. Keep
            # rejecting malformed or unsupported files as before.
            if str(exc) != "No readable text was found in the selected file":
                raise
            normalized = {
                "filename": Path(filename).name,
                "format": Path(filename).suffix.removeprefix("."),
                "text": "",
                "segments": [],
                "truncated": False,
            }
        normalized["ocr_upload"] = preserve_ocr_upload(data, filename)
        return normalized
    except DocumentAttachmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class FSPickResponse(BaseModel):
    path: str | None
    cancelled: bool


@app.get("/api/fs/pick-folder", response_model=FSPickResponse)
def fs_pick_folder(starting_path: str | None = None) -> FSPickResponse:
    """Open native macOS folder picker via AppleScript and return the absolute POSIX path."""
    try:
        default = starting_path or str(Path.home())
        script = """
        on run argv
        set defaultPath to POSIX file (item 1 of argv)
        tell application "Finder" to activate
        delay 0.2
        try
            set chosenFolder to choose folder with prompt "Select a repo or folder:" default location defaultPath
            return POSIX path of chosenFolder
        on error errorMessage number errorNumber
            if errorNumber is -128 then return "__CANCELLED__"
            error errorMessage number errorNumber
        end try
        end run
        """
        result = subprocess.run(
            ["osascript", "-e", script, default],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail="Folder picker failed to open")
        output = result.stdout.strip()
        if output == "__CANCELLED__" or not output:
            return FSPickResponse(path=None, cancelled=True)
        return FSPickResponse(path=output, cancelled=False)
    except HTTPException:
        raise
    except subprocess.TimeoutExpired as e:
        raise HTTPException(status_code=504, detail="Folder picker timed out") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Folder picker failed") from e


@app.get("/api/models")
def list_models() -> dict:
    """List configured Deep Agents models plus discovered local Ollama models."""
    default = os.getenv("CODING_MODEL", "openai/gpt-5.6-luna")
    configured = list(
        dict.fromkeys(
            [
                default,
                *[
                    model.strip()
                    for model in os.getenv("CODING_MODELS", "").split(",")
                    if model.strip()
                ],
            ]
        )
    )

    def provider(model_id: str) -> str:
        if model_id.startswith("openai/"):
            return "openai"
        if model_id.startswith(("huggingface/", "hf/")):
            return "huggingface"
        if model_id.startswith("ollama-cloud/"):
            return "ollama-cloud"
        return "ollama"

    models = [
        {"id": model_id, "name": model_id, "provider": provider(model_id)}
        for model_id in configured
    ]
    cloud_models = [
        {
            "id": f"ollama-cloud/{m['name']}",
            "name": m["name"],
            "provider": "ollama-cloud",
        }
        for m in list_ollama_cloud_models()
        if m.get("name")
    ]
    local_models = [
        {"id": f"ollama/{m['name']}", "name": m["name"], "provider": "ollama"}
        for m in list_ollama_models()
        if m.get("name")
    ]
    openai_models = list_openai_gpt_models()
    seen = {model["id"] for model in models}
    for discovered in (openai_models, cloud_models, local_models):
        for model in discovered:
            if model["id"] not in seen:
                models.append(model)
                seen.add(model["id"])
    return {
        "default": default,
        "models": models,
    }


@app.get("/")
def root() -> dict:
    return {"message": "LangGraph Agent Chat UI sidecar"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.web_server:app", host="127.0.0.1", port=port, reload=False)
