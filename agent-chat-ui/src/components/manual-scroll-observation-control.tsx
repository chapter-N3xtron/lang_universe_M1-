"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { Button } from "@/components/ui/button";
import {
  startManualScrollObservation,
  type CaptureController,
} from "@/lib/manual-scroll-observation";

function formatElapsed(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

const subscribeToHostname = () => () => {};
const getServerLocalHost = () => false;
const getBrowserLocalHost = () =>
  ["localhost", "127.0.0.1"].includes(window.location.hostname);

export function ManualScrollObservationControl({
  threadId,
}: {
  threadId: string | null;
}) {
  const controllerRef = useRef<CaptureController | null>(null);
  const isLocal = useSyncExternalStore(
    subscribeToHostname,
    getBrowserLocalHost,
    getServerLocalHost,
  );
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (startedAt === null) return;
    const update = () =>
      setElapsed(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
    update();
    const interval = window.setInterval(update, 250);
    return () => window.clearInterval(interval);
  }, [startedAt]);

  useEffect(
    () => () => {
      controllerRef.current?.discard();
      controllerRef.current = null;
    },
    [],
  );

  const start = useCallback(() => {
    if (!threadId) return;
    setError(null);
    setMessage(null);
    try {
      controllerRef.current = startManualScrollObservation({
        scenarioId: `conversation-scroll-${Date.now()}`,
        threadId,
      });
      setElapsed(0);
      setStartedAt(Date.now());
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Capture did not start",
      );
    }
  }, [threadId]);

  const stop = useCallback(() => {
    const controller = controllerRef.current;
    if (!controller) return;
    setError(null);
    const result = controller.stop();
    controllerRef.current = null;
    setStartedAt(null);
    setElapsed(0);
    if (!result) {
      setError("Capture did not stop normally");
      return;
    }
    if (result.finalization_error) {
      setError(result.finalization_error);
      return;
    }
    setMessage(`Downloaded ${result.artifacts.observation_log}`);
  }, []);

  if (!isLocal) return null;

  const active = startedAt !== null;
  return (
    <div className="flex min-w-0 items-center gap-2">
      <Button
        size="sm"
        variant={active ? "destructive" : "outline"}
        disabled={!active && !threadId}
        onClick={active ? stop : start}
      >
        {active ? "Stop Capture" : "Start JSON Capture"}
      </Button>
      {active && (
        <span
          role="status"
          aria-live="polite"
          className="flex shrink-0 items-center gap-1.5 text-xs font-medium"
        >
          <span
            aria-hidden="true"
            className="size-2 rounded-full bg-red-600"
          />
          Capturing JSON · {formatElapsed(elapsed)}
        </span>
      )}
      {!active && !threadId && (
        <span className="text-muted-foreground text-xs">
          Open a thread to capture JSON
        </span>
      )}
      {!active && message && (
        <span
          role="status"
          aria-live="polite"
          className="text-muted-foreground max-w-56 truncate text-xs"
        >
          {message}
        </span>
      )}
      {error && (
        <span
          role="alert"
          className="text-destructive max-w-56 truncate text-xs"
        >
          {error}
        </span>
      )}
    </div>
  );
}
