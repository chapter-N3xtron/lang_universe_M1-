"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const TTS_API_BASE = "http://127.0.0.1:8000";
const TTS_SAMPLE_RATE = 24000;

function resample(audio: Float32Array, srcRate: number, dstRate: number): Float32Array {
  if (srcRate === dstRate) return audio;
  const ratio = srcRate / dstRate;
  const dstLength = Math.round(audio.length / ratio);
  const result = new Float32Array(dstLength);
  for (let i = 0; i < dstLength; i++) {
    const srcIdx = i * ratio;
    const lo = Math.floor(srcIdx);
    const hi = Math.min(lo + 1, audio.length - 1);
    const frac = srcIdx - lo;
    result[i] = audio[lo] + (audio[hi] - audio[lo]) * frac;
  }
  return result;
}

export type VoiceInfo = {
  id: string;
  name: string;
  category?: string;
};

export function useTTS() {
  const [speaking, setSpeaking] = useState(false);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const checkIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    if (checkIntervalRef.current) {
      clearInterval(checkIntervalRef.current);
      checkIntervalRef.current = null;
    }
    if (audioCtxRef.current && audioCtxRef.current.state !== "closed") {
      audioCtxRef.current.close().catch(() => {});
    }
    audioCtxRef.current = null;
    setSpeaking(false);
  }, []);

  useEffect(() => {
    return () => stop();
  }, [stop]);

  const speak = useCallback(
    async (text: string, voice = "alba") => {
      stop();
      setSpeaking(true);

      const abort = new AbortController();
      abortRef.current = abort;

      // Create AudioContext synchronously (before any await) so the browser
      // sees it as user-gesture-initiated.  AudioContexts created after an
      // await are suspended and will never play.
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;

      if (ctx.state === "suspended") {
        await ctx.resume();
      }
      console.log("[TTS] AudioContext state:", ctx.state, "sampleRate:", ctx.sampleRate);

      const deviceRate = ctx.sampleRate;

      try {
        const res = await fetch(`${TTS_API_BASE}/api/tts/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, voice }),
          signal: abort.signal,
        });

        if (!res.ok) throw new Error(`TTS failed: ${res.status}`);

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";
        let nextTime = ctx.currentTime;
        let chunkCount = 0;

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

            const bytes = Uint8Array.from(atob(data.audio), (c) =>
              c.charCodeAt(0)
            );
            const floatArr = new Float32Array(bytes.buffer).slice();
            const resampled = resample(floatArr, TTS_SAMPLE_RATE, deviceRate);
            const audioBuffer = ctx.createBuffer(1, resampled.length, deviceRate);
            audioBuffer.getChannelData(0).set(resampled);

            const source = ctx.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(ctx.destination);
            source.start(Math.max(ctx.currentTime, nextTime));
            nextTime = Math.max(nextTime, ctx.currentTime) + audioBuffer.duration;
            chunkCount++;
          }
        }

        console.log("[TTS] playback done, chunks:", chunkCount, "duration:", nextTime.toFixed(1) + "s");

        // Wait for playback to finish
        await new Promise<void>((resolve) => {
          checkIntervalRef.current = setInterval(() => {
            if (ctx.currentTime >= nextTime) {
              if (checkIntervalRef.current) {
                clearInterval(checkIntervalRef.current);
                checkIntervalRef.current = null;
              }
              resolve();
            }
          }, 100);
        });
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          console.error("TTS error:", err);
        }
      } finally {
        if (ctx.state !== "closed") {
          ctx.close().catch(() => {});
        }
        if (audioCtxRef.current === ctx) {
          audioCtxRef.current = null;
        }
        setSpeaking(false);
      }
    },
    [stop]
  );

  return { speak, stop, speaking };
}

export async function listVoices(): Promise<VoiceInfo[]> {
  const res = await fetch(`${TTS_API_BASE}/api/tts/voices`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Failed to list voices: ${res.status}`);
  const data = await res.json();
  return data.voices.map((v: string) => ({
    id: v,
    name: v.replace(/_/g, " ").replace(/\b\w/g, (l: string) => l.toUpperCase()),
  }));
}
