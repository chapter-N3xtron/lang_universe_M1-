"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const STT_API_BASE = "http://127.0.0.1:8000";

export function useSTT() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isAcquiring, setIsAcquiring] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const cachedStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const stopRequestedRef = useRef(false);
  const onResultRef = useRef<((text: string) => void) | null>(null);
  const onErrorRef = useRef<((err: Error) => void) | null>(null);

  useEffect(() => {
    return () => {
      if (
        mediaRecorderRef.current &&
        mediaRecorderRef.current.state === "recording"
      ) {
        mediaRecorderRef.current.stop();
      }
      if (cachedStreamRef.current) {
        cachedStreamRef.current.getTracks().forEach((t) => t.stop());
        cachedStreamRef.current = null;
      }
    };
  }, []);

  const getStream = useCallback(async (): Promise<MediaStream> => {
    if (
      cachedStreamRef.current &&
      cachedStreamRef.current
        .getAudioTracks()
        .some((t) => t.readyState === "live")
    ) {
      return cachedStreamRef.current;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    cachedStreamRef.current = stream;
    return stream;
  }, []);

  const transcribeAndFinish = useCallback(
    (recorder: MediaRecorder, blob: Blob) => {
      const onResult = onResultRef.current;
      const onError = onErrorRef.current;

      if (blob.size < 100) {
        console.warn("[STT] blob too small, skipping transcription");
        setIsProcessing(false);
        return;
      }

      const ext = recorder.mimeType.includes("webm") ? "webm" : "mp4";
      const formData = new FormData();
      formData.append("audio", blob, `recording.${ext}`);

      fetch(`${STT_API_BASE}/api/stt`, { method: "POST", body: formData })
        .then((res) => {
          if (!res.ok) {
            return res
              .json()
              .catch(() => ({}))
              .then((body) => {
                throw new Error(
                  `STT failed (${res.status}): ${body.detail || "unknown"}`,
                );
              });
          }
          return res.json();
        })
        .then((data) => onResult?.(data.transcript))
        .catch((err) => {
          console.error("STT error:", err);
          onError?.(err instanceof Error ? err : new Error(String(err)));
        })
        .finally(() => setIsProcessing(false));
    },
    [],
  );

  const handleStop = useCallback(
    (recorder: MediaRecorder) => {
      setIsRecording(false);
      setIsProcessing(true);
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
      console.log("[STT] stop", {
        chunks: chunksRef.current.length,
        blobSize: blob.size,
        blobType: blob.type,
      });
      chunksRef.current = [];
      transcribeAndFinish(recorder, blob);
    },
    [transcribeAndFinish],
  );

  const startRecording = useCallback(() => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state === "recording"
    ) {
      console.warn(
        "[STT] startRecording called while already recording — ignoring",
      );
      return;
    }
    chunksRef.current = [];
    stopRequestedRef.current = false;
    setIsAcquiring(true);
    getStream()
      .then((stream) => {
        if (stopRequestedRef.current) {
          console.log("[STT] stop requested during acquisition; not starting");
          setIsAcquiring(false);
          return;
        }
        const mimeType = MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "audio/mp4";
        const recorder = new MediaRecorder(stream, { mimeType });
        mediaRecorderRef.current = recorder;
        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunksRef.current.push(e.data);
        };
        recorder.onerror = (e) =>
          console.error("[STT] MediaRecorder error:", e);
        recorder.onstop = () => handleStop(recorder);
        recorder.start(1000);
        setIsRecording(true);
      })
      .catch((err) => {
        console.error("Microphone access denied:", err);
      })
      .finally(() => setIsAcquiring(false));
  }, [getStream, handleStop]);

  const stopRecording = useCallback(
    (onResult: (text: string) => void, onError?: (err: Error) => void) => {
      onResultRef.current = onResult;
      onErrorRef.current = onError ?? null;

      const recorder = mediaRecorderRef.current;

      if (!recorder || recorder.state !== "recording") {
        console.warn("[STT] stopRecording called but recorder not recording", {
          hasRecorder: !!recorder,
          state: recorder?.state,
          isAcquiring,
        });
        if (isAcquiring) {
          stopRequestedRef.current = true;
          setIsRecording(false);
        }
        return;
      }

      try {
        recorder.stop();
      } catch (err) {
        console.error("[STT] recorder.stop() threw:", err);
      }
    },
    [isAcquiring],
  );

  return {
    startRecording,
    stopRecording,
    isRecording,
    isProcessing,
    isAcquiring,
  };
}
