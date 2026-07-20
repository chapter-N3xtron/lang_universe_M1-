# LangGraph Agent Chat UI + OpenCode CLI

A multi-agent system built with LangGraph, featuring a modern React chat UI and a Python FastAPI backend.

## Architecture

- **backend/**: LangGraph agents + FastAPI server
  - `src/chat_ui.py`: orchestrates OpenCode, Research, Jasper, and Magic Coder agents; compiled once with a LangGraph `MemorySaver` checkpointer for durable, per-thread conversation state
  - `src/opencode_agent.py`: coding agent via the real OpenCode CLI; reuses the CLI's `session_id` across turns so the headless agent retains its own context
  - `src/magic_coder_agent.py`: local Ollama-based magic coding agent with filesystem tools and image-generation framework
  - `src/jobs.py`: in-memory async job runner for long-running agents
  - `src/research_agent.py`: research agent via Ollama Cloud
  - `src/llm.py`: Ollama Cloud connection using `langchain-ollama`
  - `src/ollama_client.py`: local Ollama bridge for models prefixed `ollama/`
  - `src/web_server.py`: FastAPI app with `POST /api/chat`, `/api/models`, and `/api/jobs`; persists conversation state by `thread_id`
  - `.env`: Ollama Cloud API key + model names
- **frontend/**: Next.js 16 + shadcn/ui + agents-kit components
  - `src/app/page.tsx`: non-streaming dark-mode chat interface with sidebar, model selector, agent selector, repo picker, and live/async switch; each chat thread owns a persistent `threadId` used by the backend checkpointer
  - `src/lib/api.ts`: backend client including `/api/jobs` helpers; sends `thread_id` with every chat request
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
- **Magic Coder**: Local Ollama-based agent for creating super cute and cool SFW anime-style images with a deterministic pipeline
- **Research Agent**: Deep research using web knowledge (Firecrawl optional)
- **Jasper**: General LangGraph assistant

## Image Generation Framework

The **Magic Coder** agent can scaffold a complete, deterministic character + image-generation pipeline:

- `build_image_framework` — creates a reusable character sheet, prompt engine, and batch generator.
- `build_comfyui_workflow` — creates a separate ComfyUI API workflow JSON that locks the anime checkpoint, sampler, dimensions, and seed strategy so every character shares the same style.
- `register_character` — reads a SillyTavern `character.json` + `lorebook.json` and creates a persistent image profile in `image_profiles/<name>/profile.json`.
- `update_physical_description` — overrides the persistent physical description used for every image of that character.
- `place_image_order` — assembles a deterministic positive/negative prompt from the character profile and a scene order, patches the ComfyUI workflow, and queues it to the local ComfyUI server immediately.

### Deterministic image order flow

1. **Register the character** (once):
   > "Register Amber for images."
   The agent reads `~/fun-multi-character-chats/characters/Amber/character.json` and `lorebook.json`.

2. **Lock the physical description** (once, or refine anytime):
   > "Amber looks like: young woman in her early twenties, fit and curvy, long honey-blonde hair, warm brown eyes, fair smooth skin, 90s anime pinup expression."
   The agent writes this to `image_profiles/Amber/profile.json` and uses it for every image.

3. **Place an image order** (queues immediately):
   > "Image Amber: making coffee in the kitchen, stretching and yawning, leaning against the counter, tiny white cotton tank and panties, sunlit kitchen, alone, sleepy and flirty."
   The agent builds the prompt, patches `comfyui_workflow/workflow_api.json`, writes the order to `image_orders/Amber/`, and POSTs the workflow to `http://127.0.0.1:8188/prompt`. No separate dry-run or confirmation step is required.

### Locked style (never changes unless you edit the workflow)

- **Model**: `anima-base-v1.0.safetensors`
- **Text encoder**: `qwen_3_06b_base.safetensors`
- **VAE**: `qwen_image_vae.safetensors`
- **LoRA**: `dakota_anima_lora.safetensors` (strength 0.7)
- **Sampler**: `dpmpp_2m` / `karras`, 30 steps, CFG 7.0
- **Resolution**: 1920×1080

### Image-order parser model

Image orders are parsed by a dedicated small local model. Set in `backend/.env`:

```env
IMAGE_ORDER_MODEL=mistral-small:22b
```

Defaults to `mistral-small:22b`. A smaller magic model can be substituted (e.g. `dolphin-llama3:8b`) if VRAM is tight.

## Conversation Memory

The backend uses a LangGraph `MemorySaver` checkpointer to keep conversation state per `thread_id`. Each chat thread in the frontend owns a durable `threadId` that is sent on every request. On the first message the backend seeds the thread with the conversation history; on later turns it only appends the new user message and restores prior turns from the checkpointer.

The OpenCode CLI agent also reuses its own `session_id` across turns, so the headless agent continues its internal conversation context in addition to the LangGraph-level state. To move from in-memory persistence to a production database, replace `MemorySaver` with a LangGraph `PostgresSaver` or `RedisSaver` in `backend/src/chat_ui.py`.

## Async Jobs

Long-running tasks (especially **Magic Coder**) run as background jobs to keep the UI responsive. Jobs also use the same `thread_id` so their results are written into the persistent conversation state.

- `POST /api/jobs` — start a job; returns `{ job_id, status }`
- `GET /api/jobs/{job_id}` — poll for status/result
- The frontend polls every 2 seconds and replaces the placeholder message when the job completes.

## UI Parts

See `ui parts.txt` for evaluated UI libraries.

## License

MIT
