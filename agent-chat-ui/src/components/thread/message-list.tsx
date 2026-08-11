"use client";

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import { Message, Checkpoint } from "@langchain/langgraph-sdk";
import { useStreamContext } from "@/providers/Stream";
import { AssistantMessage, AssistantMessageLoading } from "./messages/ai";
import { HumanMessage } from "./messages/human";
import { useTTS } from "@/hooks/useTTS";
import type { ConceptMapArtifact } from "@/lib/visual/jasper-response.generated";
import { getContentString } from "./utils";

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
  const arrivalAnchorKey = lastMessage
    ? `${lastMessage.type}:${String(lastMessage.id ?? messages.length - 1)}`
    : undefined;
  const assistantAnchorKey = String(
    lastHuman?.id ?? lastMessage?.id ?? messages.length - 1,
  );
  // Each newly inserted turn gets one placement after layout settles. The
  // key is tied to the arriving message so assistant growth does not create
  // another scroll owner.
  const positioningKey =
    lastMessage && getContentString(lastMessage.content).trim()
      ? lastMessage.type === "ai"
        ? `assistant:${assistantAnchorKey}`
        : arrivalAnchorKey
      : undefined;
  const positioningCancelledRef = useRef(false);
  const programmaticScrollUntilRef = useRef(0);
  const previousThreadIdRef = useRef(threadId);
  const reopenPlacementThreadRef = useRef<string | null>(null);
  const reopenPlacementPendingRef = useRef(false);
  const hydratedThreadRef = useRef<string | null>(null);
  const createdThreadCandidateRef = useRef(false);

  useEffect(() => {
    // Hydrated history is top-anchored once, but a later user turn starts a
    // new arrival cycle and must allow exactly one assistant placement.
    if (
      lastMessage?.type === "human" &&
      hydratedThreadRef.current === threadId
    ) {
      hydratedThreadRef.current = null;
    }
  }, [lastMessage?.type, threadId]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const cancel = () => {
      if (performance.now() < programmaticScrollUntilRef.current) return;
      positioningCancelledRef.current = true;
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
      ) {
        cancel();
      }
    };
    const onCancel = () => cancel();
    viewport.addEventListener("wheel", cancel, { passive: true });
    viewport.addEventListener("touchstart", cancel, { passive: true });
    window.addEventListener("keydown", onKeyDown, true);
    document.addEventListener("selectionchange", cancel, { passive: true });
    window.addEventListener("conversation:cancel-positioning", onCancel);
    return () => {
      viewport.removeEventListener("wheel", cancel);
      viewport.removeEventListener("touchstart", cancel);
      window.removeEventListener("keydown", onKeyDown, true);
      document.removeEventListener("selectionchange", cancel);
      window.removeEventListener("conversation:cancel-positioning", onCancel);
    };
  }, [viewportRef]);

  useEffect(() => {
    const previousThreadId = previousThreadIdRef.current;
    const hasThreadIdInUrl =
      typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).has("threadId");
    if (!threadId && !hasThreadIdInUrl) {
      createdThreadCandidateRef.current = true;
    }
    const isReopenedCreatedThread =
      createdThreadCandidateRef.current &&
      previousThreadId === null &&
      threadId !== null &&
      messages.length > 0;
    if (!threadId || messages.length === 0) {
      previousThreadIdRef.current = threadId;
      return;
    }

    if (isReopenedCreatedThread) {
      // A newly created thread receives its server id alongside the optimistic
      // message. It is an arrival, not hydrated history.
      reopenPlacementThreadRef.current = threadId;
      reopenPlacementPendingRef.current = false;
      previousThreadIdRef.current = threadId;
      return;
    }

    if (reopenPlacementThreadRef.current === threadId) {
      previousThreadIdRef.current = threadId;
      return;
    }

    reopenPlacementThreadRef.current = threadId;
    hydratedThreadRef.current = threadId;
    reopenPlacementPendingRef.current = true;
    previousThreadIdRef.current = threadId;
    let cancelled = false;
    let frame = 0;
    let stableFrames = 0;
    let previousHeight = -1;
    const placeLatestAtTop = () => {
      const latestMessages =
        viewportRef.current?.querySelectorAll<HTMLElement>("[data-message-id]");
      if (cancelled) return;
      const viewport = viewportRef.current;
      if (!viewport) return;
      if (!latestMessages?.length) {
        window.requestAnimationFrame(placeLatestAtTop);
        return;
      }
      const height = viewport.scrollHeight;
      stableFrames = height === previousHeight ? stableFrames + 1 : 0;
      previousHeight = height;
      if (stableFrames >= 2 || frame >= 12) {
        programmaticScrollUntilRef.current = performance.now() + 100;
        viewport.scrollTo({
          top: Math.max(
            0,
            viewport.scrollTop +
              latestMessages[latestMessages.length - 1].getBoundingClientRect()
                .top -
              viewport.getBoundingClientRect().top -
              32,
          ),
          behavior: "auto",
        });
        reopenPlacementPendingRef.current = false;
        return;
      }
      frame += 1;
      window.requestAnimationFrame(placeLatestAtTop);
    };
    const frameId = window.requestAnimationFrame(placeLatestAtTop);
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(frameId);
    };
  }, [messages.length, threadId, viewportRef]);

  useEffect(() => {
    if (
      !positioningKey ||
      reopenPlacementPendingRef.current ||
      hydratedThreadRef.current === threadId
    )
      return;
    positioningCancelledRef.current = false;
    let cancelled = false;
    let frame = 0;
    let stableFrames = 0;
    let previousRect: DOMRect | undefined;
    let rafId: number | undefined;

    const positionOnce = () => {
      if (cancelled || positioningCancelledRef.current) return;
      const viewport = viewportRef.current;
      const topAnchor = viewport?.querySelector<HTMLElement>(
        `[data-conversation-arrival-anchor-top="${CSS.escape(positioningKey)}"]`,
      );
      if (!viewport || !topAnchor) return;
      const top = Math.max(
        0,
        viewport.scrollTop +
          topAnchor.getBoundingClientRect().top -
          viewport.getBoundingClientRect().top -
          32,
      );
      // Use one immediate placement so later answer growth and stream updates
      // never create a competing scroll owner.
      // Immediate placement is also the reduced-motion-safe behavior.
      programmaticScrollUntilRef.current = performance.now() + 100;
      viewport.scrollTo({ top, behavior: "auto" });
    };

    const settle = () => {
      if (cancelled || positioningCancelledRef.current) return;
      const viewport = viewportRef.current;
      const topAnchor = viewport?.querySelector<HTMLElement>(
        `[data-conversation-arrival-anchor-top="${CSS.escape(positioningKey)}"]`,
      );
      if (!viewport || !topAnchor) return;
      const rect = topAnchor.getBoundingClientRect();
      const stable =
        previousRect &&
        Math.abs(rect.top - previousRect.top) < 0.5 &&
        Math.abs(rect.height - previousRect.height) < 0.5;
      stableFrames = stable ? stableFrames + 1 : 0;
      previousRect = rect;
      if (stableFrames >= 2 || frame >= 12) {
        positionOnce();
        return;
      }
      frame += 1;
      rafId = window.requestAnimationFrame(settle);
    };

    rafId = window.requestAnimationFrame(settle);
    return () => {
      cancelled = true;
      if (rafId !== undefined) window.cancelAnimationFrame(rafId);
    };
  }, [positioningKey, threadId, viewportRef]);

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
