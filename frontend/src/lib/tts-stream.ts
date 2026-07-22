const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export async function* synthesizeSpeechStream(
  text: string,
  voice = "alba",
): AsyncGenerator<Float32Array, void, unknown> {
  const res = await fetch(`${API_BASE}/api/tts/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, voice }),
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`TTS stream request failed: ${res.status} ${res.statusText}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = JSON.parse(line.slice(6));
      if (data.error) throw new Error(data.error);

      const bytes = Uint8Array.from(atob(data.audio), (c) => c.charCodeAt(0));
      const floatArr = new Float32Array(bytes.buffer);
      yield floatArr.slice() as Float32Array;
    }
  }
}
