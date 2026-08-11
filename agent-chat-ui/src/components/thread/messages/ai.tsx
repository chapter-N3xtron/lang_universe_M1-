import { parsePartialJson } from "@langchain/core/output_parsers";
import { useStreamContext } from "@/providers/Stream";
import { AIMessage, Checkpoint, Message } from "@langchain/langgraph-sdk";
import { useStream } from "@langchain/langgraph-sdk/react";
import { memo, useEffect } from "react";
import { getContentString } from "../utils";
import { BranchSwitcher, CommandBar } from "./shared";
import { MarkdownText } from "../markdown-text";
import { LoadExternalComponent } from "@langchain/langgraph-sdk/react-ui";
import { cn } from "@/lib/utils";
import { ToolCalls, ToolResult } from "./tool-calls";
import { MessageContentComplex } from "@langchain/core/messages";
import { Fragment } from "react/jsx-runtime";
import { LoaderCircle } from "lucide-react";
import { isAgentInboxInterruptSchema } from "@/lib/agent-inbox-interrupt";
import { ThreadView } from "../agent-inbox";
import { useQueryState, parseAsBoolean } from "nuqs";
import { GenericInterruptView } from "./generic-interrupt";
import { useArtifact } from "../artifact";

const VISUAL_ARTIFACT_TOOLS = new Set(["draw_concept_map"]);

function isVisualArtifactTool(name: string | undefined): boolean {
  return Boolean(name && VISUAL_ARTIFACT_TOOLS.has(name));
}

function CustomComponent({ message }: { message: Message }) {
  const artifact = useArtifact();
  const thread = useStreamContext();
  const { values } = thread;
  const customComponents = values.ui?.filter(
    (ui) => ui.metadata?.message_id === message.id,
  );

  if (!customComponents?.length) return null;
  return (
    <Fragment key={message.id}>
      {customComponents.map((customComponent) => (
        <LoadExternalComponent
          key={customComponent.id}
          stream={thread as unknown as ReturnType<typeof useStream>}
          message={customComponent}
          meta={{ ui: customComponent, artifact }}
        />
      ))}
    </Fragment>
  );
}

function parseAnthropicStreamedToolCalls(
  content: MessageContentComplex[],
): AIMessage["tool_calls"] {
  const toolCallContents = content.filter((c) => c.type === "tool_use" && c.id);

  return toolCallContents.map((tc) => {
    const toolCall = tc as Record<string, any>;
    let json: Record<string, any> = {};
    if (toolCall?.input) {
      try {
        json = parsePartialJson(toolCall.input) ?? {};
      } catch {
        // Pass
      }
    }
    return {
      name: toolCall.name ?? "",
      id: toolCall.id ?? "",
      args: json,
      type: "tool_call",
    };
  });
}

interface InterruptProps {
  interrupt?: unknown;
  isLastMessage: boolean;
  hasNoAIOrToolMessages: boolean;
}

function Interrupt({
  interrupt,
  isLastMessage,
  hasNoAIOrToolMessages,
}: InterruptProps) {
  const fallbackValue = Array.isArray(interrupt)
    ? (interrupt as Record<string, any>[])
    : (((interrupt as { value?: unknown } | undefined)?.value ??
        interrupt) as Record<string, any>);

  return (
    <>
      {isAgentInboxInterruptSchema(interrupt) &&
        (isLastMessage || hasNoAIOrToolMessages) && (
          <ThreadView interrupt={interrupt} />
        )}
      {interrupt &&
      !isAgentInboxInterruptSchema(interrupt) &&
      (isLastMessage || hasNoAIOrToolMessages) ? (
        <GenericInterruptView interrupt={fallbackValue} />
      ) : null}
    </>
  );
}

function AssistantMessageImpl({
  message,
  isLoading,
  handleRegenerate,
  onSpeakMessage,
  isSpeaking,
  isLastMessage,
  hasNoAIOrToolMessages,
  parentCheckpoint,
  branch,
  branchOptions,
  onSelectBranch,
  threadInterrupt,
  hasCustomComponent,
  arrivalAnchorKey,
  anchorKey,
}: {
  message: Message | undefined;
  isLoading: boolean;
  handleRegenerate: (parentCheckpoint: Checkpoint | null | undefined) => void;
  onSpeakMessage?: (messageId: string | undefined, content: string) => void;
  isSpeaking?: boolean;
  isLastMessage: boolean;
  hasNoAIOrToolMessages: boolean;
  parentCheckpoint: Checkpoint | null | undefined;
  branch: string | undefined;
  branchOptions: string[] | undefined;
  onSelectBranch: (branch: string) => void;
  threadInterrupt: unknown;
  hasCustomComponent: boolean;
  arrivalAnchorKey?: string;
  anchorKey: string;
}) {
  useEffect(() => {
    if (!message?.id) return;
    const target = window as typeof window & {
      __messageRenders?: Record<string, number>;
    };
    if (target.__messageRenders) {
      target.__messageRenders[message.id] =
        (target.__messageRenders[message.id] ?? 0) + 1;
    }
  });
  const content = message?.content ?? [];
  const contentString = getContentString(content);
  const isPendingAnswer = isLoading && isLastMessage && message?.type === "ai";
  const conversationArrivalAnchorKey = arrivalAnchorKey ?? anchorKey;
  const showBottomControls = contentString.length >= 800;
  const additionalKwargs = (
    message as
      | (Message & {
          additional_kwargs?: {
            jasper_confidence_score?: unknown;
            jasper_confidence_basis?: unknown;
          };
        })
      | undefined
  )?.additional_kwargs;
  const confidenceScore =
    typeof additionalKwargs?.jasper_confidence_score === "number"
      ? additionalKwargs.jasper_confidence_score
      : null;
  const confidenceBasis =
    typeof additionalKwargs?.jasper_confidence_basis === "string"
      ? additionalKwargs.jasper_confidence_basis
      : null;
  const [hideToolCalls] = useQueryState(
    "hideToolCalls",
    parseAsBoolean.withDefault(false),
  );

  const anthropicStreamedToolCalls = Array.isArray(content)
    ? parseAnthropicStreamedToolCalls(content)
    : undefined;

  const hasToolCalls =
    message &&
    "tool_calls" in message &&
    message.tool_calls &&
    message.tool_calls.length > 0;
  const visibleToolCalls = hasToolCalls
    ? message.tool_calls?.filter(
        (toolCall) => !isVisualArtifactTool(toolCall.name),
      )
    : undefined;
  const toolCallsHaveContents =
    visibleToolCalls &&
    visibleToolCalls.some((tc) => tc.args && Object.keys(tc.args).length > 0);
  const visibleAnthropicToolCalls = anthropicStreamedToolCalls?.filter(
    (toolCall) => !isVisualArtifactTool(toolCall.name),
  );
  const hasVisibleToolCalls = Boolean(visibleToolCalls?.length);
  const hasAnthropicToolCalls = Boolean(visibleAnthropicToolCalls?.length);
  const isToolResult = message?.type === "tool";
  const isVisualToolResult = isToolResult && isVisualArtifactTool(message.name);

  if (isVisualToolResult || (isToolResult && hideToolCalls)) {
    return null;
  }

  if (
    !isToolResult &&
    contentString.length === 0 &&
    !hasVisibleToolCalls &&
    !hasAnthropicToolCalls &&
    !hasCustomComponent &&
    !threadInterrupt
  ) {
    return null;
  }

  return (
    <div
      className="group mr-auto flex w-full items-start gap-2"
      data-message-id={message?.id}
      data-answer-shell={isToolResult ? undefined : anchorKey}
      data-answer-anchor={isToolResult ? undefined : anchorKey}
      data-conversation-arrival-anchor-top={
        isToolResult ? undefined : `assistant:${conversationArrivalAnchorKey}`
      }
    >
      <div
        className="border-border/60 relative flex w-full flex-col gap-2 border-y py-2 pl-10"
        data-answer-anchor-bottom={isToolResult ? undefined : anchorKey}
      >
        {!isToolResult && (
          <span
            aria-hidden="true"
            data-answer-anchor-top={anchorKey}
            data-conversation-arrival-anchor-top={`assistant:${conversationArrivalAnchorKey}`}
          />
        )}
        {isToolResult ? (
          <>
            <ToolResult message={message} />
            <Interrupt
              interrupt={threadInterrupt}
              isLastMessage={isLastMessage}
              hasNoAIOrToolMessages={hasNoAIOrToolMessages}
            />
          </>
        ) : (
          <>
            {!isPendingAnswer && (
              <div className="flex items-center gap-2">
                <BranchSwitcher
                  branch={branch}
                  branchOptions={branchOptions}
                  onSelect={onSelectBranch}
                  isLoading={isLoading}
                />
                <div className="absolute top-0 left-0">
                  <CommandBar
                    content={contentString}
                    isLoading={isLoading}
                    isAiMessage={true}
                    handleRegenerate={() => handleRegenerate(parentCheckpoint)}
                    onSpeak={
                      onSpeakMessage
                        ? () => onSpeakMessage(message?.id, contentString)
                        : undefined
                    }
                    isSpeaking={isSpeaking}
                    orientation="vertical"
                  />
                </div>
              </div>
            )}
            {!isPendingAnswer && contentString.length > 0 && (
              <div className={cn("answer-reveal answer-reveal-active py-1")}>
                <MarkdownText streaming={false}>{contentString}</MarkdownText>
              </div>
            )}
            {confidenceScore !== null && (
              <p
                className="text-muted-foreground text-xs"
                data-jasper-confidence
              >
                Confidence {confidenceScore.toFixed(2)} — model estimate, not
                empirically calibrated
                {confidenceBasis ? ` · ${confidenceBasis}` : ""}
              </p>
            )}

            {!hideToolCalls && (
              <>
                {(hasVisibleToolCalls && toolCallsHaveContents && (
                  <ToolCalls toolCalls={visibleToolCalls} />
                )) ||
                  (hasAnthropicToolCalls && (
                    <ToolCalls toolCalls={visibleAnthropicToolCalls} />
                  )) ||
                  (hasVisibleToolCalls && (
                    <ToolCalls toolCalls={visibleToolCalls} />
                  ))}
              </>
            )}

            {message && hasCustomComponent && (
              <CustomComponent message={message} />
            )}
            <Interrupt
              interrupt={threadInterrupt}
              isLastMessage={isLastMessage}
              hasNoAIOrToolMessages={hasNoAIOrToolMessages}
            />
            {showBottomControls && (
              <div
                className={cn(
                  "border-border/60 mr-auto flex items-center gap-2 border-b py-1 transition-opacity",
                  "opacity-100 group-focus-within:opacity-100 group-hover:opacity-100",
                  isPendingAnswer && "hidden",
                )}
              >
                <BranchSwitcher
                  branch={branch}
                  branchOptions={branchOptions}
                  onSelect={onSelectBranch}
                  isLoading={isLoading}
                />
                <div className="absolute bottom-0 left-0">
                  <CommandBar
                    content={contentString}
                    isLoading={isLoading}
                    isAiMessage={true}
                    handleRegenerate={() => handleRegenerate(parentCheckpoint)}
                    onSpeak={
                      onSpeakMessage
                        ? () => onSpeakMessage(message?.id, contentString)
                        : undefined
                    }
                    isSpeaking={isSpeaking}
                    orientation="vertical"
                  />
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export const AssistantMessage = memo(AssistantMessageImpl);

export function AssistantMessageLoading({ anchorKey }: { anchorKey: string }) {
  return (
    <div
      className="mr-auto flex items-start gap-2"
      data-answer-shell={anchorKey}
      data-answer-anchor={anchorKey}
    >
      <div
        data-answer-anchor-top={anchorKey}
        data-conversation-arrival-anchor-top={`assistant:${anchorKey}`}
        aria-hidden="true"
      />
      <div
        className="text-muted-foreground flex h-8 items-center rounded-2xl px-3 py-2"
        role="status"
        aria-label="Response in progress"
        data-answer-anchor-bottom={anchorKey}
      >
        <LoaderCircle className="size-4 animate-spin motion-reduce:animate-none" />
        <span className="sr-only">Response in progress</span>
      </div>
    </div>
  );
}
