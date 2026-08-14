"use client";

/**
 * Local-only, in-memory observation capture for a manually recorded smoke
 * session. This module never reads network requests, storage, cookies, headers,
 * environment files, or model/provider internals.
 */

export const MANUAL_SCROLL_OBSERVATION_SCHEMA = "manual-scroll-observation/v1";
const MAX_EVENTS = 2000;
const MAX_CONTENT_LENGTH = 12000;

type Lifecycle = "active" | "paused" | "stopped" | "discarded" | "error";
type RecordingMetadata = {
  filename?: string;
  path?: string;
  startTime?: string;
  endTime?: string;
  notes?: string;
};

export type CaptureOptions = {
  scenarioId: string;
  threadId: string;
  recording?: RecordingMetadata;
};

type EventPayload = Record<string, unknown>;

export type ObservationManifest = {
  schema: string;
  scenario_id: string;
  session_id: string;
  lifecycle: Lifecycle;
  local_only: true;
  automatic_upload: false;
  temporary_artifact: true;
  content_capture: {
    enabled: true;
    warning_acknowledged: true;
    redaction: string;
  };
  artifacts: {
    observation_log: string;
    recording: RecordingMetadata & { status: "manual" | "not-provided" };
  };
  started_at: string;
  ended_at: string | null;
  event_count: number;
  finalization_error: string | null;
  recording_support: {
    automatic_capture: false;
    primitive: "manual-QuickTime";
    note: string;
  };
  review: null;
};

type ObservationEvent = {
  session_id: string;
  scenario_id: string;
  sequence: number;
  elapsed_ms: number;
  wall_time: string;
  type: string;
  source: string;
  correlation_id?: string;
  payload: EventPayload;
};

type ObservationBundle = {
  schema: string;
  manifest: ObservationManifest;
  events: ObservationEvent[];
};

export type CaptureController = {
  pause(): void;
  resume(): void;
  stop(): ObservationManifest | null;
  discard(): void;
  delete(): void;
  setRecording(metadata: RecordingMetadata): void;
  status(): ObservationManifest;
  redact(value: string): { value: string; redacted: boolean };
};

const SECRET_RULES = [
  /-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----/gi,
  /\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]+/gi,
  /\b(?:api[_-]?key|token|secret|password|authorization|cookie)\s*[:=]\s*[^\s,;]+/gi,
  /(?:^|[?&])(?:access_token|id_token|refresh_token|api_key|token)=[^&\s]+/gi,
  /(?:^|\s)(?:OPENAI|ANTHROPIC|LANGCHAIN|AWS|DATABASE|NEXT_PUBLIC)_[A-Z0-9_]*\s*=\s*[^\s]+/g,
];

function redacted(value: string): { value: string; redacted: boolean } {
  let result = value.slice(0, MAX_CONTENT_LENGTH);
  let didRedact = result.length !== value.length;
  for (const rule of SECRET_RULES) {
    const next = result.replace(rule, "[REDACTED]");
    didRedact ||= next !== result;
    result = next;
  }
  return { value: result, redacted: didRedact };
}

function download(name: string, value: unknown) {
  const blob = new Blob([JSON.stringify(value, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function metrics(viewport: HTMLElement | null) {
  if (!viewport) return { viewport: null, scrollTop: null, scrollHeight: null };
  const rect = viewport.getBoundingClientRect();
  return {
    viewport: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
    scrollTop: viewport.scrollTop,
    scrollHeight: viewport.scrollHeight,
  };
}

function snapshot(threadId?: string) {
  const viewport = document.querySelector<HTMLElement>(
    "[data-conversation-viewport]",
  );
  const messages = Array.from(
    document.querySelectorAll<HTMLElement>("[data-message-id]"),
  );
  const contents = messages.map((element) => {
    const content = redacted(element.innerText || element.textContent || "");
    const rect = element.getBoundingClientRect();
    return {
      message_id: element.dataset.messageId ?? null,
      thread_id:
        threadId ?? new URLSearchParams(location.search).get("threadId"),
      observed_content: content.value,
      content_redacted: content.redacted,
      anchor_ids: Array.from(
        element.querySelectorAll<HTMLElement>(
          "[data-conversation-arrival-anchor-top]",
        ),
        (anchor) => anchor.dataset.conversationArrivalAnchorTop ?? null,
      ),
      bounding_rect: {
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
      },
    };
  });
  return {
    ...metrics(viewport),
    message_snapshots: contents,
    ui_state: {
      visibility: document.visibilityState,
      active_element: document.activeElement?.tagName ?? null,
      loading: Boolean(document.querySelector("[aria-busy='true']")),
      url_path: location.pathname,
      observable_transitions: {
        hydration: null,
        streaming: Boolean(document.querySelector("[data-streaming='true']")),
        fallback: Boolean(document.querySelector("[data-fallback='true']")),
        error: Boolean(document.querySelector("[role='alert']")),
        recovery: null,
        layout_settled: null,
      },
    },
  };
}

function installCapture(options: CaptureOptions): CaptureController {
  const sessionId = `scroll-observation-${Date.now()}-${crypto.randomUUID().slice(0, 8)}`;
  const startedAt = new Date().toISOString();
  const startedMono = performance.now();
  let lifecycle: Lifecycle = "active";
  let sequence = 0;
  let finalizationError: string | null = null;
  let recording: RecordingMetadata = options.recording ?? {};
  const events: ObservationEvent[] = [];
  const cleanup: Array<() => void> = [];

  const manifest = (): ObservationManifest => ({
    schema: MANUAL_SCROLL_OBSERVATION_SCHEMA,
    scenario_id: options.scenarioId,
    session_id: sessionId,
    lifecycle,
    local_only: true,
    automatic_upload: false,
    temporary_artifact: true,
    content_capture: {
      enabled: true,
      warning_acknowledged: true,
      redaction:
        "denylist hooks run before persistence and export; review before sharing",
    },
    artifacts: {
      observation_log: `${sessionId}.json`,
      recording: {
        ...recording,
        status:
          recording.filename || recording.path ? "manual" : "not-provided",
      },
    },
    started_at: startedAt,
    ended_at:
      lifecycle === "stopped" ||
      lifecycle === "discarded" ||
      lifecycle === "error"
        ? new Date().toISOString()
        : null,
    event_count: events.length,
    finalization_error: finalizationError,
    recording_support: {
      automatic_capture: false,
      primitive: "manual-QuickTime",
      note: "QuickTime must be started/stopped by the tester; browser permission and file location are outside this app.",
    },
    review: null,
  });

  const emit = (
    type: string,
    source: string,
    payload: EventPayload = {},
    correlationId?: string,
  ) => {
    if (lifecycle !== "active" || events.length >= MAX_EVENTS) return;
    events.push({
      session_id: sessionId,
      scenario_id: options.scenarioId,
      sequence: sequence++,
      elapsed_ms: Math.round(performance.now() - startedMono),
      wall_time: new Date().toISOString(),
      type,
      source,
      ...(correlationId ? { correlation_id: correlationId } : {}),
      payload,
    });
  };

  const viewport = () =>
    document.querySelector<HTMLElement>("[data-conversation-viewport]");
  const capture = (type: string, source: string, payload: EventPayload = {}) =>
    emit(type, source, { ...payload, observation: snapshot(options.threadId) });

  emit("session.start", "manual", { recording: recording.filename ?? null });
  capture("ui.snapshot", "initial");

  const onScroll = (event: Event) =>
    capture("user.scroll", "dom", {
      target:
        (event.target as HTMLElement).dataset.conversationViewport !==
        undefined,
    });
  const target = viewport();
  target?.addEventListener("scroll", onScroll, { passive: true });
  if (target)
    cleanup.push(() => target.removeEventListener("scroll", onScroll));

  const observer = new MutationObserver((mutations) => {
    capture("dom.mutation", "MutationObserver", {
      count: mutations.length,
      summaries: mutations.slice(0, 20).map((mutation) => ({
        type: mutation.type,
        target: (mutation.target as Element).nodeName,
        added: mutation.addedNodes.length,
        removed: mutation.removedNodes.length,
      })),
    });
  });
  observer.observe(document.body, {
    subtree: true,
    childList: true,
    attributes: true,
    characterData: true,
  });
  cleanup.push(() => observer.disconnect());

  const resize = new ResizeObserver(() =>
    capture("layout.resize", "ResizeObserver"),
  );
  if (target) resize.observe(target);
  cleanup.push(() => resize.disconnect());

  const originalScrollTo = Element.prototype.scrollTo;
  const originalScrollBy = Element.prototype.scrollBy;
  Element.prototype.scrollTo = function (this: Element, ...args: unknown[]) {
    const before = metrics(this as HTMLElement);
    (originalScrollTo as (...values: unknown[]) => void).apply(this, args);
    const requested = args[0];
    emit("programmatic.scroll", "scrollTo", {
      args:
        typeof requested === "object" && requested !== null ? requested : args,
      before,
      after: metrics(this as HTMLElement),
    });
  } as typeof originalScrollTo;
  Element.prototype.scrollBy = function (this: Element, ...args: unknown[]) {
    const before = metrics(this as HTMLElement);
    (originalScrollBy as (...values: unknown[]) => void).apply(this, args);
    const requested = args[0];
    emit("programmatic.scroll", "scrollBy", {
      args:
        typeof requested === "object" && requested !== null ? requested : args,
      before,
      after: metrics(this as HTMLElement),
    });
  } as typeof originalScrollBy;
  cleanup.push(() => {
    Element.prototype.scrollTo = originalScrollTo;
    Element.prototype.scrollBy = originalScrollBy;
  });

  const finish = (next: Lifecycle) => {
    if (lifecycle === "stopped" || lifecycle === "discarded") return;
    lifecycle = next;
    cleanup.splice(0).forEach((dispose) => dispose());
  };

  return {
    pause: () => {
      if (lifecycle === "active") {
        emit("session.pause", "manual");
        lifecycle = "paused";
      }
    },
    resume: () => {
      if (lifecycle === "paused") {
        lifecycle = "active";
        emit("session.resume", "manual");
      }
    },
    stop: () => {
      if (lifecycle === "stopped" || lifecycle === "discarded") return null;
      if (lifecycle === "active" || lifecycle === "paused")
        emit("session.stop", "manual");
      finish("stopped");
      const finalManifest = manifest();
      const bundle: ObservationBundle = {
        schema: MANUAL_SCROLL_OBSERVATION_SCHEMA,
        manifest: finalManifest,
        events,
      };
      try {
        download(finalManifest.artifacts.observation_log, bundle);
      } catch (error) {
        finalizationError =
          error instanceof Error ? error.message : "download failed";
      }
      return manifest();
    },
    discard: () => {
      finish("discarded");
      events.length = 0;
    },
    delete: () => {
      finish("discarded");
      events.length = 0;
    },
    setRecording: (metadata) => {
      recording = { ...recording, ...metadata };
      emit("recording.metadata", "manual", { recording });
    },
    status: () => manifest(),
    redact: redacted,
  };
}

export function startManualScrollObservation(
  options: CaptureOptions,
): CaptureController {
  if (!options.scenarioId.trim())
    throw new Error("Capture requires a scenario ID");
  if (!options.threadId.trim()) throw new Error("Capture requires a thread ID");
  if (
    !window.confirm(
      "JSON capture records rendered message content. Keep the downloaded file local and review it before sharing. Start capture?",
    )
  )
    throw new Error("Content-capture warning declined");
  return installCapture(options);
}
