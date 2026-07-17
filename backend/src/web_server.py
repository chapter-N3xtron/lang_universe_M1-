"""FastAPI server for the LangGraph Agent Chat UI backend."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.chat_ui import create_chat_ui
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

    result = app_graph.invoke({
        "messages": messages,
        "workspace": request.workspace,
        "target_agent": request.target_agent,
        "mode": request.mode,
    })
    response = result["messages"][-1]["content"]

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


@app.get("/")
def root() -> dict:
    return {"message": "LangGraph Agent Chat UI backend"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.web_server:app", host="127.0.0.1", port=port, reload=False)
