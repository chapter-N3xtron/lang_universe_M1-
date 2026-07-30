"use client";

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Message, Checkpoint } from "@langchain/langgraph-sdk";
import { useStreamContext } from "@/providers/Stream";
import { AssistantMessage, AssistantMessageLoading } from "./messages/ai";
import { HumanMessage } from "./messages/human";
import { useTTS } from "@/hooks/useTTS";
import { DO_NOT_RENDER_ID_PREFIX } from "@/lib/ensure-tool-responses";

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
          streamSubgraphs: true,
          streamResumable: true,
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
        streamSubgraphs: true,
        streamResumable: true,
      });
    },
    [onRegenerateStart],
  );

  const handleSpeak = useCallback(
    (messageId: string | undefined, content: string) => {
      if (speaking && speakingMessageId === messageId) {
        stopTts();
      } else {
        setSpeakingMessageId(messageId);
        speak(content, selectedVoice || undefined);
      }
    },
    [speaking, speakingMessageId, stopTts, speak, selectedVoice],
  );

  const hasNoAIOrToolMessages = !messages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );
  const renderableMessages = useMemo(
    () =>
      messages.filter(
        (message) => !message.id?.startsWith(DO_NOT_RENDER_ID_PREFIX),
      ),
    [messages],
  );
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
        const isSpeakingThis = speaking && speakingMessageId === message.id;
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
