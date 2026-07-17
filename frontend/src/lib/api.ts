"use server";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type ChatRequest = {
  message: string;
  history: ChatMessage[];
};

export type ChatResponse = {
  response: string;
};

export type STTResponse = {
  transcript: string;
};

export async function sendChatMessage(
  message: string,
  history: ChatMessage[]
): Promise<string> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history } as ChatRequest),
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Chat request failed: ${res.status} ${res.statusText}`);
  }

  const data: ChatResponse = await res.json();
  return data.response;
}

export async function synthesizeSpeech(text: string, voice = "af_heart"): Promise<Blob> {
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
