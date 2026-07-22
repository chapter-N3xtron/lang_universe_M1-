"use server";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export type ApiChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type ChatRequest = {
  message: string;
  history: ApiChatMessage[];
  thread_id?: string;
  target_agent?: "jasper" | "opencode" | "uncensored-coder" | "research";
  workspace?: string;
  mode?: "live" | "async";
  model?: string;
};

export type ChatResponse = {
  response: string;
};

export type ModelInfo = {
  id: string;
  name: string;
  provider: string;
};

export type ModelsResponse = {
  default: string;
  models: ModelInfo[];
};

export type STTResponse = {
  transcript: string;
};

export type JobInfo = {
  id: string;
  status: "pending" | "running" | "completed" | "failed";
  result: string | null;
  error: string | null;
  created_at: number;
  updated_at: number;
};

export type FSEntry = {
  name: string;
  path: string;
  type: "dir" | "file";
};

export type FSListResponse = {
  path: string;
  entries: FSEntry[];
};

export async function sendChatMessage(
  message: string,
  history: ApiChatMessage[],
  target_agent?: "jasper" | "opencode" | "uncensored-coder" | "research",
  workspace?: string,
  mode?: "live" | "async",
  model?: string,
  thread_id?: string
): Promise<string> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, thread_id, target_agent, workspace, mode, model } as ChatRequest),
    cache: "no-store",
    signal: AbortSignal.timeout(900000),
  });

  if (!res.ok) {
    throw new Error(`Chat request failed: ${res.status} ${res.statusText}`);
  }

  const data: ChatResponse = await res.json();
  return data.response;
}

export async function getAvailableModels(): Promise<ModelsResponse> {
  const res = await fetch(`${API_BASE}/api/models`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch models: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function synthesizeSpeech(text: string, voice = "alba"): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, voice }),
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`TTS request failed: ${res.status} ${res.statusText}`);
  }

  return res.blob();
}

export type VoiceInfo = {
  id: string;
  name: string;
  category?: string;
};

export async function listVoices(): Promise<VoiceInfo[]> {
  const res = await fetch(`${API_BASE}/api/tts/voices`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Failed to list voices: ${res.status} ${res.statusText}`);
  }

  const data = await res.json();
  return data.voices.map((v: string) => ({
    id: v,
    name: v.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
    category: "english",
  }));
}

export async function transcribeAudio(audio: Blob): Promise<string> {
  const formData = new FormData();
  formData.append("audio", audio, "recording.webm");

  const res = await fetch(`${API_BASE}/api/stt`, {
    method: "POST",
    body: formData,
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`STT request failed: ${res.status} ${res.statusText}`);
  }

  const data: STTResponse = await res.json();
  return data.transcript;
}

export async function getHomeDirectory(): Promise<string> {
  const res = await fetch(`${API_BASE}/api/fs/home`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to get home directory");
  const data = await res.json();
  return data.path;
}

export async function listDirectory(path: string): Promise<FSListResponse> {
  const res = await fetch(
    `${API_BASE}/api/fs/list?path=${encodeURIComponent(path)}`,
    { cache: "no-store" }
  );
  if (!res.ok) throw new Error(`Failed to list ${path}`);
  return res.json();
}

export type FSPickResponse = {
  path: string | null;
  cancelled: boolean;
};

export async function pickFolder(startingPath?: string): Promise<FSPickResponse> {
  const url = new URL(`${API_BASE}/api/fs/pick-folder`);
  if (startingPath) url.searchParams.set("starting_path", startingPath);
  const res = await fetch(url.toString(), { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to open folder picker");
  return res.json();
}

export async function createAgentJob(
  message: string,
  history: ApiChatMessage[],
  target_agent?: "jasper" | "opencode" | "uncensored-coder" | "research",
  workspace?: string,
  model?: string,
  thread_id?: string
): Promise<{ job_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, thread_id, target_agent, workspace, mode: "async", model } as ChatRequest),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to start job: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function getAgentJob(jobId: string): Promise<JobInfo> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to get job: ${res.status} ${res.statusText}`);
  }
  return res.json();
}
