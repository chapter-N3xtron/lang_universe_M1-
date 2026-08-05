"use client";

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Message, Checkpoint } from "@langchain/langgraph-sdk";
import { useStreamContext } from "@/providers/Stream";
import { AssistantMessage, AssistantMessageLoading } from "./messages/ai";
import { HumanMessage } from "./messages/human";
import { useTTS } from "@/hooks/useTTS";
import type { ConceptMapArtifact } from "@/lib/visual/jasper-response.generated";

interface MessageListProps {
  isLoading: boolean;
  firstTokenReceived: boolean;
  selectedVoice: string;
  onRegenerateStart: () => void;
}

const MESSAGE_WINDOW_SIZE = 80;

function MessageListImpl({
  isLoading,
  firstTokenReceived,
  selectedVoice,
  onRegenerateStart,
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
      streamRef.current.submit(
        { messages: [newMessage] },
        {
          checkpoint,
          streamMode: ["messages"],
          streamSubgraphs: false,
          streamResumable: true,
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
          />
        ) : (
          <AssistantMessage
            key={`${message.id || message.type}-${absoluteIndex}`}
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
        />
      )}
      {isLoading && !firstTokenReceived && <AssistantMessageLoading />}
    </>
  );
}

export const MessageList = memo(MessageListImpl);
