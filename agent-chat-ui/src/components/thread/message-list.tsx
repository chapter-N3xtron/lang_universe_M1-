"use client";

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import { Message, Checkpoint } from "@langchain/langgraph-sdk";
import { useStreamContext } from "@/providers/Stream";
import { AssistantMessage, AssistantMessageLoading } from "./messages/ai";
import { HumanMessage } from "./messages/human";
import { useTTS } from "@/hooks/useTTS";
import type { ConceptMapArtifact } from "@/lib/visual/jasper-response.generated";

interface MessageListProps {
  isLoading: boolean;
  threadId: string | null;
  selectedVoice: string;
  onRegenerateStart: () => void;
  viewportRef: RefObject<HTMLDivElement | null>;
}

const MESSAGE_WINDOW_SIZE = 80;

function MessageListImpl({
  isLoading,
  threadId,
  selectedVoice,
  onRegenerateStart,
  viewportRef,
}: MessageListProps) {
  useEffect(() => {
    const target = window as typeof window & { __messageListRenders?: number };
    if (typeof target.__messageListRenders === "number") {
      target.__messageListRenders += 1;
    }
  });
  const stream = useStreamContext();
  const messages = stream.messages;
  const { speak, stop: stopTts, speaking } = useTTS();
  const [speakingMessageId, setSpeakingMessageId] = useState<
    string | undefined
  >(undefined);
  const [narrating, setNarrating] = useState(false);
  const narrationRunRef = useRef(0);
  const streamRef = useRef(stream);
  useEffect(() => {
    streamRef.current = stream;
  }, [stream]);
  const [visibleLimit, setVisibleLimit] = useState(MESSAGE_WINDOW_SIZE);

  const submitEdit = useCallback(
    (
      newMessage: Message,
      checkpoint: Checkpoint | null | undefined,
      values: Record<string, unknown> | undefined,
    ) => {
      const executionMode = values?.execution_mode;
      streamRef.current.submit(
        {
          messages: [newMessage],
          ...(values?.context && typeof values.context === "object"
            ? { context: values.context as Record<string, unknown> }
            : {}),
          ...(typeof values?.target_agent === "string"
            ? { target_agent: values.target_agent }
            : {}),
          ...(typeof values?.workspace === "string"
            ? { workspace: values.workspace }
            : {}),
          ...(typeof values?.model === "string" ? { model: values.model } : {}),
          ...(executionMode === "read_only" ||
          executionMode === "approval" ||
          executionMode === "autonomous"
            ? { execution_mode: executionMode }
            : {}),
        },
        {
          checkpoint,
          streamMode: ["messages"],
          streamSubgraphs: false,
          streamResumable: true,
          multitaskStrategy: "reject",
          onDisconnect: "cancel",
          optimisticValues: (previous) => {
            if (!values) return previous;
            const previousMessages = Array.isArray(values.messages)
              ? values.messages
              : [];
            return {
              ...values,
              messages: [...previousMessages, newMessage],
            } as typeof previous;
          },
        },
      );
    },
    [],
  );

  const selectBranch = useCallback((branch: string) => {
    streamRef.current.setBranch(branch);
  }, []);

  const handleRegenerate = useCallback(
    (parentCheckpoint: Checkpoint | null | undefined) => {
      onRegenerateStart();
      streamRef.current.submit(undefined, {
        checkpoint: parentCheckpoint,
        streamMode: ["messages"],
        streamSubgraphs: false,
        streamResumable: true,
        multitaskStrategy: "reject",
        onDisconnect: "cancel",
      });
    },
    [onRegenerateStart],
  );

  const visualArtifacts = useMemo(
    () => (stream.values?.visual_artifacts ?? []) as ConceptMapArtifact[],
    [stream.values?.visual_artifacts],
  );

  useEffect(() => {
    const stopNarration = () => {
      narrationRunRef.current += 1;
      stopTts();
      setNarrating(false);
    };
    window.addEventListener("jasper:stop-message-narration", stopNarration);
    return () =>
      window.removeEventListener(
        "jasper:stop-message-narration",
        stopNarration,
      );
  }, [stopTts]);

  const handleSpeak = useCallback(
    async (messageId: string | undefined, content: string) => {
      if ((speaking || narrating) && speakingMessageId === messageId) {
        narrationRunRef.current += 1;
        stopTts();
        setNarrating(false);
        window.dispatchEvent(
          new CustomEvent("visual:narration-node", { detail: null }),
        );
      } else {
        window.dispatchEvent(new Event("jasper:stop-node-audio"));
        const runId = narrationRunRef.current + 1;
        narrationRunRef.current = runId;
        setSpeakingMessageId(messageId);
        const artifact = visualArtifacts.find(
          (candidate) => candidate.source_message_id === messageId,
        );
        if (!artifact) {
          await speak(content, selectedVoice || undefined);
          return;
        }
        setNarrating(true);
        try {
          if (content.trim()) {
            const completed = await speak(content, selectedVoice || undefined);
            if (!completed || narrationRunRef.current !== runId) return;
          }
          const nodes = new Map(
            artifact.payload.nodes.map((node) => [node.id, node]),
          );
          for (const nodeId of artifact.payload.narration_order) {
            if (narrationRunRef.current !== runId) break;
            const node = nodes.get(nodeId);
            if (!node) continue;
            window.dispatchEvent(
              new CustomEvent("visual:narration-node", {
                detail: { artifactId: artifact.artifact_id, nodeId },
              }),
            );
            const completed = await speak(
              node.narration,
              selectedVoice || undefined,
            );
            if (!completed) break;
          }
        } finally {
          if (narrationRunRef.current === runId) {
            setNarrating(false);
            window.dispatchEvent(
              new CustomEvent("visual:narration-node", { detail: null }),
            );
          }
        }
      }
    },
    [
      speaking,
      narrating,
      speakingMessageId,
      stopTts,
      visualArtifacts,
      speak,
      selectedVoice,
    ],
  );

  const hasNoAIOrToolMessages = !messages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );
  const renderableMessages = messages;
  const customComponentMessageIds = useMemo(
    () =>
      new Set(
        (stream.values?.ui ?? [])
          .map((component) => component.metadata?.message_id)
          .filter((id): id is string => typeof id === "string"),
      ),
    [stream.values?.ui],
  );
  let windowStart = Math.max(0, renderableMessages.length - visibleLimit);
  while (windowStart > 0 && renderableMessages[windowStart]?.type === "tool") {
    windowStart -= 1;
  }
  const visibleMessages = renderableMessages.slice(windowStart);

  const lastMessage = messages.at(-1);
  const lastHuman = [...messages]
    .reverse()
    .find((message) => message.type === "human");
  const messageId = (message: Message | undefined, fallback: number) =>
    String(message?.id ?? fallback);
  const lastMessageId = messageId(lastMessage, messages.length - 1);
  const lastHumanId = messageId(lastHuman, messages.length - 1);
  const arrivalAnchorKey = lastMessage
    ? `${lastMessage.type}:${lastMessageId}`
    : undefined;
  const assistantAnchorKey = lastMessageId;
  const positioningCancelledRef = useRef(false);
  const programmaticScrollRef = useRef<{ top: number; until: number } | null>(
    null,
  );
  const placementStatesRef = useRef(
    new Map<
      string,
      {
        phase:
          | "hydrated"
          | "user-arrived"
          | "assistant-completed"
          | "human-controlled";
        hydrated: boolean;
        userMessageId?: string;
        assistantMessageId?: string;
      }
    >(),
  );
  const previousThreadIdRef = useRef(threadId);
  const createdThreadCandidateRef = useRef(false);
  const [placementRequest, setPlacementRequest] = useState<{
    threadId: string;
    phase: "hydrated" | "user-arrived" | "assistant-completed";
  } | null>(null);

  const requestPlacement = useCallback(
    (
      nextThreadId: string,
      phase: "hydrated" | "user-arrived" | "assistant-completed",
    ) => {
      const state = placementStatesRef.current.get(nextThreadId);
      if (state?.phase === "human-controlled") return;
      setPlacementRequest({ threadId: nextThreadId, phase });
    },
    [],
  );

  useEffect(() => {
    const previousThreadId = previousThreadIdRef.current;
    const hasThreadIdInUrl =
      typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).has("threadId");
    if (!threadId && !hasThreadIdInUrl)
      createdThreadCandidateRef.current = true;
    if (previousThreadId !== threadId) {
      positioningCancelledRef.current = false;
      setPlacementRequest(null);
    }
    previousThreadIdRef.current = threadId;
    if (!threadId || messages.length === 0) return;
    let state = placementStatesRef.current.get(threadId);
    if (!state) {
      state = { phase: "hydrated", hydrated: false };
      placementStatesRef.current.set(threadId, state);
    }
    const isNewlyCreatedThread =
      createdThreadCandidateRef.current && previousThreadId === null;
    if (!state.hydrated && !isNewlyCreatedThread) {
      state.hydrated = true;
      state.phase = "hydrated";
      requestPlacement(threadId, "hydrated");
      return;
    }
    if (
      lastMessage?.type === "human" &&
      state.userMessageId !== lastMessageId
    ) {
      state.userMessageId = lastMessageId;
      state.phase = "user-arrived";
      requestPlacement(threadId, "user-arrived");
      return;
    }
    // Completion is semantic: streaming content changes while loading do not qualify.
    if (
      lastMessage?.type === "ai" &&
      !isLoading &&
      state.assistantMessageId !== lastMessageId
    ) {
      state.assistantMessageId = lastMessageId;
      state.phase = "assistant-completed";
      requestPlacement(threadId, "assistant-completed");
    }
  }, [
    isLoading,
    lastHumanId,
    lastMessage,
    lastMessageId,
    messages.length,
    requestPlacement,
    threadId,
  ]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const cancel = () => {
      const programmatic = programmaticScrollRef.current;
      if (
        programmatic &&
        performance.now() < programmatic.until &&
        Math.abs(viewport.scrollTop - programmatic.top) < 1
      )
        return;
      positioningCancelledRef.current = true;
      if (threadId) {
        const state = placementStatesRef.current.get(threadId);
        if (state) state.phase = "human-controlled";
      }
      setPlacementRequest(null);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (
        [
          "ArrowUp",
          "ArrowDown",
          "PageUp",
          "PageDown",
          "Home",
          "End",
          " ",
        ].includes(event.key)
      )
        cancel();
    };
    viewport.addEventListener("wheel", cancel, { passive: true });
    viewport.addEventListener("touchstart", cancel, { passive: true });
    viewport.addEventListener("touchmove", cancel, { passive: true });
    viewport.addEventListener("pointermove", cancel, { passive: true });
    viewport.addEventListener("selectstart", cancel, { passive: true });
    viewport.addEventListener("dragstart", cancel, { passive: true });
    viewport.addEventListener("pointerdown", cancel, { passive: true });
    viewport.addEventListener("scroll", cancel, { passive: true });
    window.addEventListener("keydown", onKeyDown, true);
    window.addEventListener("conversation:cancel-positioning", cancel);
    return () => {
      viewport.removeEventListener("wheel", cancel);
      viewport.removeEventListener("touchstart", cancel);
      viewport.removeEventListener("touchmove", cancel);
      viewport.removeEventListener("pointermove", cancel);
      viewport.removeEventListener("selectstart", cancel);
      viewport.removeEventListener("dragstart", cancel);
      viewport.removeEventListener("pointerdown", cancel);
      viewport.removeEventListener("scroll", cancel);
      window.removeEventListener("keydown", onKeyDown, true);
      window.removeEventListener("conversation:cancel-positioning", cancel);
    };
  }, [threadId, viewportRef]);

  useEffect(() => {
    if (!placementRequest || placementRequest.threadId !== threadId) return;
    positioningCancelledRef.current = false;
    let cancelled = false;
    let frame = 0;
    let stableFrames = 0;
    let previousRect: DOMRect | undefined;
    let rafId: number | undefined;
    const anchor =
      placementRequest.phase === "hydrated"
        ? "[data-message-id]"
        : `[data-conversation-arrival-anchor-top="${CSS.escape(placementRequest.phase === "user-arrived" ? `human:${lastMessageId}` : `assistant:${lastMessageId}`)}"]`;
    const positionOnce = () => {
      if (cancelled || positioningCancelledRef.current) return;
      const viewport = viewportRef.current;
      const nodes = viewport?.querySelectorAll<HTMLElement>(anchor);
      const target = nodes?.[nodes.length - 1];
      if (!viewport || !target) return;
      const contentShell = viewport.firstElementChild as HTMLElement | null;
      if (!contentShell) return;
      const usableTop = Number.parseFloat(
        getComputedStyle(contentShell).paddingTop || "0",
      );
      const top = Math.max(
        0,
        viewport.scrollTop +
          target.getBoundingClientRect().top -
          viewport.getBoundingClientRect().top -
          usableTop,
      );
      programmaticScrollRef.current = { top, until: performance.now() + 100 };
      viewport.scrollTo({ top, behavior: "auto" });
      setPlacementRequest(null);
    };
    const settle = () => {
      if (cancelled || positioningCancelledRef.current) return;
      const viewport = viewportRef.current;
      const nodes = viewport?.querySelectorAll<HTMLElement>(anchor);
      const target = nodes?.[nodes.length - 1];
      if (!viewport || !target) {
        rafId = window.requestAnimationFrame(settle);
        return;
      }
      const rect = target.getBoundingClientRect();
      const stable =
        previousRect &&
        Math.abs(rect.top - previousRect.top) < 0.5 &&
        Math.abs(rect.height - previousRect.height) < 0.5;
      stableFrames = stable ? stableFrames + 1 : 0;
      previousRect = rect;
      if (stableFrames >= 2 || frame >= 12) return positionOnce();
      frame += 1;
      rafId = window.requestAnimationFrame(settle);
    };
    rafId = window.requestAnimationFrame(settle);
    return () => {
      cancelled = true;
      if (rafId !== undefined) window.cancelAnimationFrame(rafId);
    };
  }, [lastHumanId, lastMessageId, placementRequest, threadId, viewportRef]);

  return (
    <>
      {windowStart > 0 && (
        <button
          type="button"
          className="text-muted-foreground mx-auto rounded-md border px-3 py-1 text-sm"
          onClick={() =>
            setVisibleLimit((limit) => limit + MESSAGE_WINDOW_SIZE)
          }
        >
          Show {Math.min(MESSAGE_WINDOW_SIZE, windowStart)} earlier messages
        </button>
      )}
      {visibleMessages.map((message, index) => {
        const absoluteIndex = windowStart + index;
        const isLastMessage = absoluteIndex === renderableMessages.length - 1;
        const rowIsLoading = isLoading && isLastMessage;
        const metadata = stream.getMessagesMetadata(message);
        const isSpeakingThis =
          (speaking || narrating) && speakingMessageId === message.id;
        return message.type === "human" ? (
          <HumanMessage
            key={`${message.id || message.type}-${absoluteIndex}`}
            message={message}
            isLoading={rowIsLoading}
            parentCheckpoint={metadata?.firstSeenState?.parent_checkpoint}
            firstSeenValues={metadata?.firstSeenState?.values}
            branch={metadata?.branch}
            branchOptions={metadata?.branchOptions}
            onSelectBranch={selectBranch}
            onSubmitEdit={submitEdit}
            arrivalAnchorKey={
              absoluteIndex === renderableMessages.length - 1
                ? arrivalAnchorKey
                : undefined
            }
          />
        ) : (
          <AssistantMessage
            key={String(
              [...renderableMessages.slice(0, absoluteIndex)]
                .reverse()
                .find((item) => item.type === "human")?.id ??
                message.id ??
                `assistant-${absoluteIndex}`,
            )}
            message={message}
            isLoading={rowIsLoading}
            handleRegenerate={handleRegenerate}
            isSpeaking={isSpeakingThis}
            onSpeakMessage={handleSpeak}
            isLastMessage={isLastMessage}
            hasNoAIOrToolMessages={hasNoAIOrToolMessages}
            parentCheckpoint={metadata?.firstSeenState?.parent_checkpoint}
            branch={metadata?.branch}
            branchOptions={metadata?.branchOptions}
            onSelectBranch={selectBranch}
            threadInterrupt={stream.interrupt}
            hasCustomComponent={
              !!message.id && customComponentMessageIds.has(message.id)
            }
            arrivalAnchorKey={
              absoluteIndex === renderableMessages.length - 1
                ? assistantAnchorKey
                : undefined
            }
            anchorKey={String(
              [...renderableMessages.slice(0, absoluteIndex)]
                .reverse()
                .find((item) => item.type === "human")?.id ??
                message.id ??
                `assistant-${absoluteIndex}`,
            )}
          />
        );
      })}
      {hasNoAIOrToolMessages && !!stream.interrupt && (
        <AssistantMessage
          key="interrupt-msg"
          message={undefined}
          isLoading={isLoading}
          handleRegenerate={handleRegenerate}
          isLastMessage={true}
          hasNoAIOrToolMessages={hasNoAIOrToolMessages}
          parentCheckpoint={undefined}
          branch={undefined}
          branchOptions={undefined}
          onSelectBranch={selectBranch}
          threadInterrupt={stream.interrupt}
          hasCustomComponent={false}
          anchorKey="interrupt"
        />
      )}
      {isLoading && lastMessage?.type !== "ai" && (
        <AssistantMessageLoading
          anchorKey={String(
            [...renderableMessages]
              .reverse()
              .find((item) => item.type === "human")?.id ?? "pending",
          )}
        />
      )}
      {renderableMessages.length > 0 && (
        <div
          aria-hidden="true"
          style={{ height: "100vh", flexShrink: 0 }}
        />
      )}
    </>
  );
}

export const MessageList = memo(MessageListImpl);
