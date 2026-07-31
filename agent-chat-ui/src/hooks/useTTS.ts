"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const TTS_API_BASE = "http://127.0.0.1:8000";
const TTS_SAMPLE_RATE = 24000;
const PLAYBACK_BLOCK_SAMPLES = TTS_SAMPLE_RATE / 2;
const PLAYBACK_START_DELAY_SECONDS = 0.1;
const MAX_SCHEDULE_AHEAD_SECONDS = 3;
const SCHEDULE_POLL_MS = 25;

function mergeAudioChunks(
  chunks: Float32Array[],
  totalSamples: number,
): Float32Array {
  const merged = new Float32Array(totalSamples);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return merged;
}

function abortableDelay(ms: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) {
    return Promise.reject(
      new DOMException("TTS playback stopped", "AbortError"),
    );
  }
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(new DOMException("TTS playback stopped", "AbortError"));
    };
    signal.addEventListener("abort", onAbort, { once: true });
  });
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
  const playbackIdRef = useRef(0);

  const stop = useCallback(() => {
    playbackIdRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
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
      const playbackId = playbackIdRef.current;
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
      console.log(
        "[TTS] AudioContext state:",
        ctx.state,
        "sampleRate:",
        ctx.sampleRate,
      );

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
        let nextTime = 0;
        let chunkCount = 0;
        let playbackBlockCount = 0;
        let totalDuration = 0;
        let pendingChunks: Float32Array[] = [];
        let pendingSamples = 0;
        const activeSources = new Set<AudioBufferSourceNode>();

        const schedulePendingAudio = async (force = false) => {
          if (pendingSamples === 0) return;
          if (!force && pendingSamples < PLAYBACK_BLOCK_SAMPLES) return;

          while (
            nextTime > 0 &&
            nextTime - ctx.currentTime > MAX_SCHEDULE_AHEAD_SECONDS
          ) {
            await abortableDelay(SCHEDULE_POLL_MS, abort.signal);
          }

          if (abort.signal.aborted || ctx.state === "closed") {
            throw new DOMException("TTS playback stopped", "AbortError");
          }

          const pcm = mergeAudioChunks(pendingChunks, pendingSamples);
          pendingChunks = [];
          pendingSamples = 0;

          // Keep PCM at its native rate. AudioContext performs output-device
          // resampling, avoiding a second full-size allocation for every chunk.
          const audioBuffer = ctx.createBuffer(1, pcm.length, TTS_SAMPLE_RATE);
          audioBuffer.getChannelData(0).set(pcm);

          const source = ctx.createBufferSource();
          source.buffer = audioBuffer;
          source.connect(ctx.destination);
          activeSources.add(source);
          source.onended = () => {
            source.disconnect();
            activeSources.delete(source);
          };

          if (nextTime === 0 || nextTime < ctx.currentTime) {
            nextTime = ctx.currentTime + PLAYBACK_START_DELAY_SECONDS;
          }
          source.start(nextTime);
          nextTime += audioBuffer.duration;
          totalDuration += audioBuffer.duration;
          playbackBlockCount += 1;
        };

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
              c.charCodeAt(0),
            );
            const floatArr = new Float32Array(bytes.buffer).slice();
            pendingChunks.push(floatArr);
            pendingSamples += floatArr.length;
            chunkCount++;
            await schedulePendingAudio(Boolean(data.last));
          }
        }

        await schedulePendingAudio(true);

        console.log(
          "[TTS] playback queued, chunks:",
          chunkCount,
          "blocks:",
          playbackBlockCount,
          "duration:",
          totalDuration.toFixed(1) + "s",
        );

        // Wait for playback to finish
        if (nextTime > 0)
          await new Promise<void>((resolve) => {
            checkIntervalRef.current = setInterval(() => {
              if (ctx.currentTime >= nextTime) {
                if (checkIntervalRef.current) {
                  clearInterval(checkIntervalRef.current);
                  checkIntervalRef.current = null;
                }
                resolve();
              }
            }, 250);
          });
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          console.error("TTS error:", err);
        }
        return false;
      } finally {
        if (ctx.state !== "closed") {
          ctx.close().catch(() => {});
        }
        if (audioCtxRef.current === ctx) {
          audioCtxRef.current = null;
        }
        if (playbackIdRef.current === playbackId) {
          setSpeaking(false);
        }
      }
      return true;
    },
    [stop],
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
