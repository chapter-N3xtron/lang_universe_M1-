# LangGraph Agent Chat UI + OpenCode CLI

A multi-agent system built with LangGraph, featuring a modern React chat UI and a Python FastAPI backend.

## Architecture

- **backend/**: LangGraph agents + FastAPI server
  - `src/chat_ui.py`: orchestrates OpenCode and Research agents
  - `src/opencode_agent.py`: coding agent via Ollama Cloud
  - `src/research_agent.py`: research agent via Ollama Cloud
  - `src/llm.py`: Ollama Cloud connection using `langchain-ollama`
  - `src/web_server.py`: FastAPI app with `POST /api/chat`
  - `.env`: Ollama Cloud API key + model names
- **frontend/**: Next.js 16 + shadcn/ui + agents-kit components
  - `src/app/page.tsx`: non-streaming dark-mode chat interface with sidebar
  - `src/lib/api.ts`: backend client
  - `src/components/prompt-kit/`: chat components from [agents-kit](https://github.com/agents-ui/agents-kit)
  - `src/components/agents-ui/`: agent-specific components from [agents-kit](https://github.com/agents-ui/agents-kit)
  - `src/components/chat/ArtifactMessage.tsx`: code/document artifact renderer

## Getting Started

### 1. Backend

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -e .
python -m uvicorn src.web_server:app --host 127.0.0.1 --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 in your browser.

### Voice Layer

- **TTS**: assistant messages have a "Read aloud" button powered by Kokoro (`POST /api/tts`).
- **STT**: click the microphone button to record audio; it is transcribed locally using faster-whisper (`POST /api/stt`) and sent as text.

### Chat UI Components

- **AgentChatHistory**: left sidebar with searchable, filterable, persistent chat sessions (`localStorage`).
- **AgentArtifact**: IDE-style viewer for code and documents extracted from assistant responses.
- **AgentInquiry**: interactive follow-up cards for multiple-choice, text, confirmation, or star-rating questions.

## Configuration

Edit `backend/.env`:

```env
LLM_BASE_URL=https://ollama.com
LLM_API_KEY=<your-ollama-cloud-key>
CHAT_UI_MODEL=glm-5.2
OPENCODE_MODEL=qwen3.5:397b
```

## Agents

- **OpenCode CLI**: Primary coding agent for software tasks
- **Research Agent**: Deep research using web knowledge (Firecrawl optional)

## UI Parts

See `ui parts.txt` for evaluated UI libraries.

## License

MIT
