"""FastAPI server for the LangGraph Agent Chat UI backend."""

import os
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.chat_ui import create_chat_ui
from src.jobs import create_job, get_job, job_to_dict, run_job
from src.ollama_client import list_ollama_models
from src.stt import transcribe
from src.tts import synthesize

load_dotenv()

app_graph = create_chat_ui()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
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


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    messages = [m.model_dump() for m in request.history]
    messages.append({"role": "user", "content": request.message})

    # If a specific model is requested, inject it into the env for this call
    # so run_opencode picks it up without mutating global state.
    import os
    original_model = os.environ.get("OPENCODE_CLI_MODEL")
    if request.model:
        os.environ["OPENCODE_CLI_MODEL"] = request.model
    try:
        result = app_graph.invoke({
            "messages": messages,
            "workspace": request.workspace,
            "target_agent": request.target_agent,
            "mode": request.mode,
        })
        response = result["messages"][-1]["content"]
    finally:
        if original_model is not None:
            os.environ["OPENCODE_CLI_MODEL"] = original_model
        else:
            os.environ.pop("OPENCODE_CLI_MODEL", None)

    return ChatResponse(response=response)


class TTSRequest(BaseModel):
    text: str
    voice: str = "af_heart"


@app.post("/api/tts")
def tts(request: TTSRequest) -> Response:
    try:
        audio = synthesize(request.text, voice=request.voice)
        return Response(
            content=audio,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline; filename=tts.wav",
                "Content-Length": str(len(audio)),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stt")
def stt(audio: UploadFile = File(...)) -> dict:
    try:
        audio_bytes = audio.file.read()
        text = transcribe(audio_bytes)
        return {"transcript": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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

    messages = [m.model_dump() for m in request.history]
    messages.append({"role": "user", "content": request.message})

    import os
    original_model = os.environ.get("OPENCODE_CLI_MODEL")
    if request.model:
        os.environ["OPENCODE_CLI_MODEL"] = request.model

    def job_fn() -> str:
        try:
            result = app_graph.invoke({
                "messages": messages,
                "workspace": request.workspace,
                "target_agent": request.target_agent,
                "mode": "async",
            })
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
