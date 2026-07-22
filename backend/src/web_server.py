"""FastAPI server for the LangGraph Agent Chat UI backend."""

import os
import subprocess
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.chat_ui import create_chat_ui
from src.jobs import create_job, get_job, job_to_dict, run_job
from src.ollama_client import list_ollama_models
from src.stt import transcribe

load_dotenv()

app_graph = create_chat_ui()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    thread_id: str | None = None
    workspace: str = None
    target_agent: str = "opencode"
    mode: str = "live"
    model: str = None


class ChatResponse(BaseModel):
    response: str


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan hook."""
    yield


app = FastAPI(
    title="LangGraph Agent Chat UI",
    description="Backend API for the multi-agent chat interface.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _has_checkpoint(thread_id: str | None) -> bool:
    if not thread_id:
        return False
    try:
        snapshot = app_graph.get_state({"configurable": {"thread_id": thread_id}})
        return bool(snapshot and snapshot.values)
    except Exception:
        return False


def _build_invocation_input(request: ChatRequest) -> tuple[dict, list[dict]]:
    """
    Build the graph input and config for a chat request.

    With checkpointing enabled, messages accumulate per thread. On the first
    request for a thread we seed the graph with the full conversation history;
    on later requests we only append the new user message to avoid duplication.
    """
    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # First call for this thread: send the full history plus the new message.
    # Subsequent calls: rely on the checkpointer for prior turns and only send
    # the new user message.
    if _has_checkpoint(request.thread_id):
        messages = [{"role": "user", "content": request.message}]
    else:
        messages = [m.model_dump() for m in request.history]
        messages.append({"role": "user", "content": request.message})

    input_state = {
        "messages": messages,
        "workspace": request.workspace,
        "target_agent": request.target_agent,
        "mode": request.mode,
        "model": request.model,
    }
    return input_state, config


def _log_request(request: ChatRequest) -> None:
    """Emit a concise log line for debugging thread/session continuity."""
    import logging

    logger = logging.getLogger("langgraph-chat")
    logger.info(
        "chat request thread_id=%s agent=%s mode=%s history_len=%d",
        request.thread_id,
        request.target_agent,
        request.mode,
        len(request.history),
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    _log_request(request)

    # If a specific model is requested, inject it into the env for this call
    # so run_opencode picks it up without mutating global state.
    import os

    original_model = os.environ.get("OPENCODE_CLI_MODEL")
    if request.model:
        os.environ["OPENCODE_CLI_MODEL"] = request.model

    input_state, config = _build_invocation_input(request)
    try:
        result = app_graph.invoke(input_state, config=config)
        response = result["messages"][-1]["content"]
    finally:
        if original_model is not None:
            os.environ["OPENCODE_CLI_MODEL"] = original_model
        else:
            os.environ.pop("OPENCODE_CLI_MODEL", None)

    return ChatResponse(response=response)


class TTSRequest(BaseModel):
    text: str
    voice: str = ""


@app.post("/api/tts")
async def tts(request: TTSRequest) -> Response:
    """Synthesize speech using Kyutai TTS 1.6B."""
    from src.kyutai_tts import get_tts_engine
    import io
    import wave
    
    try:
        engine = get_tts_engine()
        audio_array, duration = await engine.synthesize_full(request.text, voice=request.voice)
        
        # Convert to WAV format
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(24000)  # 24kHz
            audio_int16 = (audio_array * 32767).astype(np.int16)
            wav_file.writeframes(audio_int16.tobytes())
        
        wav_buffer.seek(0)
        audio_bytes = wav_buffer.read()
        
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline; filename=tts.wav",
                "Content-Length": str(len(audio_bytes)),
                "X-Duration-Sec": str(duration),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


class TTSStreamRequest(BaseModel):
    text: str
    voice: str = ""
    chunk_size: int = 20


@app.post("/api/tts/stream")
async def tts_stream(request: TTSStreamRequest):
    """Stream TTS audio chunks as they're synthesized."""
    from src.kyutai_tts import get_tts_engine
    import json
    import base64
    
    engine = get_tts_engine()
    
    async def generate():
        try:
            async for chunk, metadata in engine.synthesize_streaming(
                text=request.text,
                voice=request.voice,
                chunk_size=request.chunk_size,
            ):
                # Convert numpy array to base64
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


class VoiceCloneRequest(BaseModel):
    name: str


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


@app.post("/api/tts/voices/clone")
async def clone_voice(request: VoiceCloneRequest) -> dict:
    """
    Clone a voice by name from the pre-computed repository.
    
    Note: True voice cloning from audio samples requires the voice encoder model.
    This endpoint selects a pre-computed voice embedding by name.
    """
    from src.kyutai_tts import get_tts_engine
    
    engine = get_tts_engine()
    try:
        await engine.load_voice(request.name)
        return {"voice_id": request.name, "status": "loaded"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.post("/api/stt")
def stt(audio: UploadFile) -> dict:
    try:
        audio_bytes = audio.file.read()
        text = transcribe(audio_bytes)
        return {"transcript": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


class FSListResponse(BaseModel):
    path: str
    entries: list[dict]


class FSPickResponse(BaseModel):
    path: str | None
    cancelled: bool


@app.get("/api/fs/home")
def fs_home() -> dict:
    return {"path": str(Path.home())}


@app.get("/api/fs/list")
def fs_list(path: str) -> FSListResponse:
    try:
        target = Path(path).expanduser().resolve()
        if not target.exists() or not target.is_dir():
            raise HTTPException(status_code=400, detail="Not a valid directory")
        entries = []
        for child in sorted(target.iterdir()):
            if child.name.startswith("."):
                continue
            try:
                entries.append({
                    "name": child.name,
                    "path": str(child),
                    "type": "dir" if child.is_dir() else "file",
                })
            except PermissionError:
                continue
        return FSListResponse(path=str(target), entries=entries)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/fs/pick-folder", response_model=FSPickResponse)
def fs_pick_folder(starting_path: str | None = None) -> FSPickResponse:
    """Open native macOS folder picker via AppleScript."""
    try:
        default = starting_path or str(Path.home())
        script = f'''
        set defaultPath to POSIX file "{default}"
        try
            set chosenFolder to choose folder with prompt "Select a repo or folder:" default location defaultPath
            return POSIX path of chosenFolder
        on error
            return "__CANCELLED__"
        end try
        '''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip()
        if output == "__CANCELLED__" or not output:
            return FSPickResponse(path=None, cancelled=True)
        return FSPickResponse(path=output, cancelled=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/models")
def list_models() -> dict:
    """List available models: OpenCode cloud default plus local Ollama models."""
    cloud_default = os.getenv("OPENCODE_CLI_MODEL", "ollama-cloud/qwen3.5:397b")
    local_models = [
        {"id": f"ollama/{m['name']}", "name": m["name"], "provider": "ollama"}
        for m in list_ollama_models()
    ]
    return {
        "default": cloud_default,
        "models": [
            {"id": cloud_default, "name": cloud_default, "provider": "opencode"},
            *local_models,
        ],
    }


class JobResponse(BaseModel):
    id: str
    status: str
    result: str | None = None
    error: str | None = None
    created_at: float
    updated_at: float


@app.post("/api/jobs")
def create_job_endpoint(request: ChatRequest) -> dict:
    """Start an async agent job. Returns a job ID for polling."""
    job_id = create_job()

    import os
    original_model = os.environ.get("OPENCODE_CLI_MODEL")
    if request.model:
        os.environ["OPENCODE_CLI_MODEL"] = request.model

    input_state, config = _build_invocation_input(request)
    # Force async mode for jobs.
    input_state["mode"] = "async"

    def job_fn() -> str:
        try:
            result = app_graph.invoke(input_state, config=config)
            return result["messages"][-1]["content"]
        finally:
            if original_model is not None:
                os.environ["OPENCODE_CLI_MODEL"] = original_model
            else:
                os.environ.pop("OPENCODE_CLI_MODEL", None)

    run_job(job_id, job_fn)
    return {"job_id": job_id, "status": "pending"}


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job_endpoint(job_id: str) -> JobResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(**job_to_dict(job))


@app.get("/")
def root() -> dict:
    return {"message": "LangGraph Agent Chat UI backend"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.web_server:app", host="127.0.0.1", port=port, reload=False)
