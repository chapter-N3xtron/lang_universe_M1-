import { v4 as uuidv4 } from "uuid";
import { ReactNode, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { useStreamContext } from "@/providers/Stream";
import { useState, FormEvent } from "react";
import { Button } from "../ui/button";
import { Checkpoint, Message } from "@langchain/langgraph-sdk";
import { AssistantMessage, AssistantMessageLoading } from "./messages/ai";
import { HumanMessage } from "./messages/human";
import { useTTS } from "@/hooks/useTTS";
import { useSTT } from "@/hooks/useSTT";
import { getContentString } from "./utils";
import {
  DO_NOT_RENDER_ID_PREFIX,
  ensureToolCallsHaveResponses,
} from "@/lib/ensure-tool-responses";
import { LangGraphLogoSVG } from "../icons/langgraph";
import { TooltipIconButton } from "./tooltip-icon-button";
import {
  ArrowDown,
  List,
  ListX,
  LoaderCircle,
  PanelRightOpen,
  PanelRightClose,
  SquarePen,
  XIcon,
  Plus,
  Mic,
  Folder,
} from "lucide-react";
import { useQueryState, parseAsBoolean } from "nuqs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";

const AGENT_OPTIONS = [
  { value: "", label: "Auto" },
  { value: "jasper", label: "Jasper" },
  { value: "opencode", label: "OpenCode" },
  { value: "research", label: "Research" },
  { value: "magic-coder", label: "Magic Coder" },
] as const;

interface ModelOption {
  value: string;
  label: string;
}
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import ThreadHistory from "./history";
import { TodoList } from "./todos";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { toast } from "sonner";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { Label } from "../ui/label";
import { Switch } from "../ui/switch";
import { GitHubSVG } from "../icons/github";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";
import { useFileUpload } from "@/hooks/use-file-upload";
import { ContentBlocksPreview } from "./ContentBlocksPreview";
import {
  useArtifactOpen,
  ArtifactContent,
  ArtifactTitle,
  useArtifactContext,
} from "./artifact";

function StickyToBottomContent(props: {
  content: ReactNode;
  footer?: ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  const context = useStickToBottomContext();
  return (
    <div
      ref={context.scrollRef}
      style={{ width: "100%", height: "100%" }}
      className={props.className}
    >
      <div
        ref={context.contentRef}
        className={props.contentClassName}
      >
        {props.content}
      </div>

      {props.footer}
    </div>
  );
}

function ScrollToBottom(props: { className?: string }) {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext();

  if (isAtBottom) return null;
  return (
    <Button
      variant="outline"
      className={props.className}
      onClick={() => scrollToBottom()}
    >
      <ArrowDown className="h-4 w-4" />
      <span>Scroll to bottom</span>
    </Button>
  );
}

function OpenGitHubRepo() {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <a
            href="https://github.com/langchain-ai/agent-chat-ui"
            target="_blank"
            className="flex items-center justify-center"
          >
            <GitHubSVG
              width="24"
              height="24"
            />
          </a>
        </TooltipTrigger>
        <TooltipContent side="left">
          <p>Open GitHub repo</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export function Thread() {
  const [artifactContext, setArtifactContext] = useArtifactContext();
  const [artifactOpen, closeArtifact] = useArtifactOpen();

  const [threadId, _setThreadId] = useQueryState("threadId");
  const [chatHistoryOpen, setChatHistoryOpen] = useQueryState(
    "chatHistoryOpen",
    parseAsBoolean.withDefault(false),
  );
  const [todosOpen, setTodosOpen] = useQueryState(
    "todosOpen",
    parseAsBoolean.withDefault(false),
  );
  const [hideToolCalls, setHideToolCalls] = useQueryState(
    "hideToolCalls",
    parseAsBoolean.withDefault(false),
  );
  const [input, setInput] = useState("");
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>("");
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([{ value: "", label: "Auto" }]);
  const [modelProviders, setModelProviders] = useState<Record<string, string>>({});
  const [defaultModel, setDefaultModel] = useState<string>("");
  const [modelsLoadError, setModelsLoadError] = useState(false);
  const [voicesLoadError, setVoicesLoadError] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState<string>("");
  const [voiceOptions, setVoiceOptions] = useState<{ id: string; name: string }[]>([]);
  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/models")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: { default: string; models: { id: string; name: string; provider: string }[] }) => {
        setDefaultModel(data.default);
        const providers: Record<string, string> = {};
        const options: ModelOption[] = [{ value: "", label: "Auto" }];
        for (const m of data.models) {
          options.push({ value: m.id, label: m.name });
          providers[m.id] = m.provider;
        }
        setModelOptions(options);
        setModelProviders(providers);
      })
      .catch((err) => {
        setModelsLoadError(true);
        toast.error("Could not load models", {
          description: "Model sidecar at http://127.0.0.1:8000 may not be running.",
        });
        console.error("[Models] failed to load:", err);
      });
    fetch("http://127.0.0.1:8000/api/tts/voices")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: { voices: string[] }) => {
        const options = data.voices.map((v: string) => ({
          id: v,
          name: v.replace(/_/g, " ").replace(/\b\w/g, (l: string) => l.toUpperCase()),
        }));
        setVoiceOptions(options);
      })
      .catch((err) => {
        setVoicesLoadError(true);
        toast.error("Could not load voices", {
          description: "TTS sidecar at http://127.0.0.1:8000 may not be running.",
        });
        console.error("[Voices] failed to load:", err);
      });
  }, []);
  const {
    contentBlocks,
    setContentBlocks,
    handleFileUpload,
    dropRef,
    removeBlock,
    resetBlocks: _resetBlocks,
    dragOver,
    handlePaste,
  } = useFileUpload();
  const [firstTokenReceived, setFirstTokenReceived] = useState(false);
  const isLargeScreen = useMediaQuery("(min-width: 1024px)");
  const { speak, stop: stopTts, speaking } = useTTS();
  const { startRecording, stopRecording, isRecording, isProcessing } = useSTT();
  const speakingMessageIdRef = useRef<string | undefined>(undefined);

  const stream = useStreamContext();
  const messages = stream.messages;
  const isLoading = stream.isLoading;

  const lastError = useRef<string | undefined>(undefined);

  const setThreadId = (id: string | null) => {
    _setThreadId(id);

    // close artifact and reset artifact context
    closeArtifact();
    setArtifactContext({});
  };

  useEffect(() => {
    if (!stream.error) {
      lastError.current = undefined;
      return;
    }
    try {
      const message = (stream.error as any).message;
      if (!message || lastError.current === message) {
        // Message has already been logged. do not modify ref, return early.
        return;
      }

      // Message is defined, and it has not been logged yet. Save it, and send the error
      lastError.current = message;
      toast.error("An error occurred. Please try again.", {
        description: (
          <p>
            <strong>Error:</strong> <code>{message}</code>
          </p>
        ),
        richColors: true,
        closeButton: true,
      });
    } catch {
      // no-op
    }
  }, [stream.error]);

  // TODO: this should be part of the useStream hook
  const prevMessageLength = useRef(0);
  useEffect(() => {
    if (
      messages.length !== prevMessageLength.current &&
      messages?.length &&
      messages[messages.length - 1].type === "ai"
    ) {
      setFirstTokenReceived(true);
    }

    prevMessageLength.current = messages.length;
  }, [messages]);

    function isCloudModel(modelId: string, providers: Record<string, string>, defaultId: string): boolean {
    const id = modelId || defaultId;
    if (!id) return false;
    const provider = providers[id];
    if (provider && provider !== "ollama") return true;
    return false;
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    stopTts();
    if ((input.trim().length === 0 && contentBlocks.length === 0) || isLoading)
      return;
    setFirstTokenReceived(false);

    const newHumanMessage: Message = {
      id: uuidv4(),
      type: "human",
      content: [
        ...(input.trim().length > 0 ? [{ type: "text", text: input }] : []),
        ...contentBlocks,
      ] as Message["content"],
    };

    const toolMessages = ensureToolCallsHaveResponses(stream.messages);

    const context =
      Object.keys(artifactContext).length > 0 ? artifactContext : undefined;

    stream.submit(
      {
        messages: [...toolMessages, newHumanMessage],
        context,
        target_agent: selectedAgent || undefined,
        workspace: selectedWorkspace || undefined,
        model: selectedModel || undefined,
      },
      {
        streamMode: ["messages"],
        streamSubgraphs: true,
        streamResumable: true,
        config: isCloudModel(selectedModel, modelProviders, defaultModel) ? { tags: ["langsmith:nostream"] } : undefined,
        optimisticValues: (prev) => ({
          ...prev,
          context,
          target_agent: selectedAgent || undefined,
          workspace: selectedWorkspace || undefined,
          model: selectedModel || undefined,
          messages: [
            ...(prev.messages ?? []),
            ...toolMessages,
            newHumanMessage,
          ],
        }),
      },
    );

    setInput("");
    setContentBlocks([]);
  };

  const handleRegenerate = (
    parentCheckpoint: Checkpoint | null | undefined,
  ) => {
    // Do this so the loading state is correct
    prevMessageLength.current = prevMessageLength.current - 1;
    setFirstTokenReceived(false);
    stream.submit(undefined, {
      checkpoint: parentCheckpoint,
      streamMode: ["messages"],
      streamSubgraphs: true,
      streamResumable: true,
    });
  };

  const chatStarted = !!threadId || !!messages.length;
  const hasNoAIOrToolMessages = !messages.find(
    (m) => m.type === "ai" || m.type === "tool",
  );

  return (
    <div className="flex h-screen w-full overflow-hidden">
      <div className="relative hidden lg:flex">
        <motion.div
          className="absolute z-20 h-full overflow-hidden border-r bg-background"
          style={{ width: 300 }}
          animate={
            isLargeScreen
              ? { x: chatHistoryOpen ? 0 : -300 }
              : { x: chatHistoryOpen ? 0 : -300 }
          }
          initial={{ x: -300 }}
          transition={
            isLargeScreen
              ? { type: "spring", stiffness: 300, damping: 30 }
              : { duration: 0 }
          }
        >
          <div
            className="relative h-full"
            style={{ width: 300 }}
          >
            <ThreadHistory />
          </div>
        </motion.div>
      </div>

      <motion.div
        className="absolute right-0 top-0 z-20 hidden h-full lg:flex"
        animate={{
          x: isLargeScreen ? (todosOpen ? 0 : 300) : (todosOpen ? 0 : 300),
        }}
        initial={{ x: 300 }}
        transition={
          isLargeScreen
            ? { type: "spring", stiffness: 300, damping: 30 }
            : { duration: 0 }
        }
      >
        <div className="h-full overflow-hidden border-l bg-background" style={{ width: 300 }}>
          <TodoList todosOpen={todosOpen} />
        </div>
      </motion.div>

      <div
        className={cn(
          "grid w-full grid-cols-[1fr_0fr] transition-all duration-500",
          artifactOpen && "grid-cols-[3fr_2fr]",
        )}
      >
        <motion.div
          className={cn(
            "relative flex min-w-0 flex-1 flex-col overflow-hidden",
            !chatStarted && "grid-rows-[1fr]",
          )}

          animate={{
            marginLeft: chatHistoryOpen ? (isLargeScreen ? 300 : 0) : 0,
          }}
          transition={
            isLargeScreen
              ? { type: "spring", stiffness: 300, damping: 30 }
              : { duration: 0 }
          }
        >
          {!chatStarted && (
            <div className="absolute top-0 left-0 z-10 flex w-full items-center justify-between gap-3 p-2 pl-4">
              <div>
                {(!chatHistoryOpen || !isLargeScreen) && (
                  <Button
                    className="hover:bg-gray-100"
                    variant="ghost"
                    onClick={() => setChatHistoryOpen((p) => !p)}
                  >
                    {chatHistoryOpen ? (
                      <PanelRightOpen className="size-5" />
                    ) : (
                      <PanelRightClose className="size-5" />
                    )}
                  </Button>
                )}
              </div>
              <div className="absolute top-2 right-4 flex items-center">
                <TooltipIconButton
                  size="lg"
                  className="p-4"
                  tooltip={todosOpen ? "Close todos" : "Show todos"}
                  variant="ghost"
                  onClick={() => setTodosOpen((p) => !p)}
                >
                  {todosOpen ? (
                    <ListX className="size-5" />
                  ) : (
                    <List className="size-5" />
                  )}
                </TooltipIconButton>
                <ThemeToggle />
                <OpenGitHubRepo />
              </div>
            </div>
          )}
          {chatStarted && (
            <div className="relative z-10 flex items-center justify-between gap-3 p-2">
              <div className="relative flex items-center justify-start gap-2">
                <div className="absolute left-0 z-10">
                  {(!chatHistoryOpen || !isLargeScreen) && (
                    <Button
                      className="hover:bg-gray-100"
                      variant="ghost"
                      onClick={() => setChatHistoryOpen((p) => !p)}
                    >
                      {chatHistoryOpen ? (
                        <PanelRightOpen className="size-5" />
                      ) : (
                        <PanelRightClose className="size-5" />
                      )}
                    </Button>
                  )}
                </div>
                <motion.button
                  className="flex cursor-pointer items-center gap-2"
                  onClick={() => setThreadId(null)}
                  animate={{
                    marginLeft: !chatHistoryOpen ? 48 : 0,
                  }}
                  transition={{
                    type: "spring",
                    stiffness: 300,
                    damping: 30,
                  }}
                >
                  <LangGraphLogoSVG
                    width={32}
                    height={32}
                  />
                  <span className="text-xl font-semibold tracking-tight">
                    Agent Chat
                  </span>
                </motion.button>
              </div>

              <div className="flex items-center gap-4">
                <div className="flex items-center">
                  {stream.values?.opencode_status && (
                    <span className="mr-2 flex items-center gap-1.5 rounded-full bg-red-900/30 px-2.5 py-0.5 text-xs text-red-300">
                      <span className="inline-block size-1.5 animate-pulse rounded-full bg-red-400" />
                      OC: {stream.values.opencode_status}
                    </span>
                  )}
                  <TooltipIconButton
                    size="lg"
                    className="p-4"
                    tooltip={todosOpen ? "Close todos" : "Show todos"}
                    variant="ghost"
                    onClick={() => setTodosOpen((p) => !p)}
                  >
                    {todosOpen ? (
                      <ListX className="size-5" />
                    ) : (
                      <List className="size-5" />
                    )}
                  </TooltipIconButton>
                  <ThemeToggle />
                  <OpenGitHubRepo />
                </div>
                <TooltipIconButton
                  size="lg"
                  className="p-4"
                  tooltip="New thread"
                  variant="ghost"
                  onClick={() => setThreadId(null)}
                >
                  <SquarePen className="size-5" />
                </TooltipIconButton>
              </div>

              <div className="from-background to-background/0 absolute inset-x-0 top-full h-5 bg-gradient-to-b" />
            </div>
          )}

          <StickToBottom className="relative flex-1 overflow-hidden">
            <StickyToBottomContent
              className={cn(
                "absolute inset-0 overflow-y-scroll px-4 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-track]:bg-transparent",
                !chatStarted && "mt-[25vh] flex flex-col items-stretch",
                chatStarted && "grid grid-rows-[1fr_auto]",
              )}
              contentClassName="pt-8 pb-16 max-w-3xl mx-auto flex flex-col gap-4 w-full"
              content={
                <>
                  {messages
                    .filter((m) => !m.id?.startsWith(DO_NOT_RENDER_ID_PREFIX))
                    .map((message, index) =>
                      message.type === "human" ? (
                        <HumanMessage
                          key={`${message.id || message.type}-${index}`}
                          message={message}
                          isLoading={isLoading}
                        />
                      ) : (
                        <AssistantMessage
                          key={`${message.id || message.type}-${index}`}
                          message={message}
                          isLoading={isLoading}
                          handleRegenerate={handleRegenerate}
                          isSpeaking={speaking && speakingMessageIdRef.current === message.id}
                          onSpeak={() => {
                            if (speaking && speakingMessageIdRef.current === message.id) {
                              stopTts();
                            } else {
                              speakingMessageIdRef.current = message.id;
                              speak(getContentString(message.content), selectedVoice || undefined);
                            }
                          }}
                        />
                      ),
                    )}
                  {/* Special rendering case where there are no AI/tool messages, but there is an interrupt.
                    We need to render it outside of the messages list, since there are no messages to render */}
                  {hasNoAIOrToolMessages && !!stream.interrupt && (
                    <AssistantMessage
                      key="interrupt-msg"
                      message={undefined}
                      isLoading={isLoading}
                      handleRegenerate={handleRegenerate}
                    />
                  )}
                  {isLoading && !firstTokenReceived && (
                    <AssistantMessageLoading />
                  )}
                </>
              }
              footer={
                <div className="sticky bottom-0 flex flex-col items-center gap-8 bg-background">
                  {!chatStarted && (
                    <div className="flex items-center gap-3">
                      <LangGraphLogoSVG className="h-8 flex-shrink-0" />
                      <h1 className="text-2xl font-semibold tracking-tight">
                        Agent Chat
                      </h1>
                    </div>
                  )}

                  <ScrollToBottom className="animate-in fade-in-0 zoom-in-95 absolute bottom-full left-1/2 mb-4 -translate-x-1/2" />

                  <div
                    ref={dropRef}
                    className={cn(
                      "bg-muted relative z-10 mx-auto mb-8 w-full max-w-3xl rounded-2xl shadow-xs transition-all",
                      dragOver
                        ? "border-primary border-2 border-dotted"
                        : "border border-solid",
                    )}
                  >
                    <form
                      onSubmit={handleSubmit}
                      className="mx-auto grid max-w-3xl grid-rows-[1fr_auto] gap-2"
                    >
                      <ContentBlocksPreview
                        blocks={contentBlocks}
                        onRemove={removeBlock}
                      />
                      <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onPaste={handlePaste}
                        onKeyDown={(e) => {
                          if (
                            e.key === "Enter" &&
                            !e.shiftKey &&
                            !e.metaKey &&
                            !e.nativeEvent.isComposing
                          ) {
                            e.preventDefault();
                            const el = e.target as HTMLElement | undefined;
                            const form = el?.closest("form");
                            form?.requestSubmit();
                          }
                        }}
                        placeholder="Type your message..."
                        className="field-sizing-content resize-none border-none bg-transparent p-3.5 pb-0 shadow-none ring-0 outline-none focus:ring-0 focus:outline-none"
                      />

                      <div className="flex items-start justify-between gap-1.5 p-1.5 pt-3">
                        <div className="flex flex-col gap-1.5">
                          <div className="flex items-center space-x-1.5">
                            <Switch
                              id="render-tool-calls"
                              checked={hideToolCalls ?? false}
                              onCheckedChange={setHideToolCalls}
                            />
                            <Label
                              htmlFor="render-tool-calls"
                              className="text-xs text-gray-600"
                            >
                              Hide Tool Calls
                            </Label>
                          </div>
                          <Label
                            htmlFor="file-input"
                            className="flex cursor-pointer items-center gap-1.5"
                          >
                            <Plus className="size-4 text-gray-600" />
                            <span className="text-xs text-gray-600">
                              Upload PDF or Image
                            </span>
                          </Label>
                          <input
                            id="file-input"
                            type="file"
                            onChange={handleFileUpload}
                            multiple
                            accept="image/jpeg,image/png,image/gif,image/webp,application/pdf"
                            className="hidden"
                          />
                          <button
                            type="button"
                            onClick={async () => {
                              try {
                                const res = await fetch("http://127.0.0.1:8000/api/fs/pick-folder");
                                const data = await res.json();
                                if (!data.cancelled && data.path) {
                                  setSelectedWorkspace(data.path);
                                }
                              } catch {
                                toast.error("Could not open folder picker.");
                              }
                            }}
                            className="flex cursor-pointer items-center gap-1.5"
                          >
                            <Folder className="size-4 text-gray-600" />
                            <span className="text-xs text-gray-600">
                              {selectedWorkspace
                                ? selectedWorkspace.replace(/\/+$/, "").split("/").pop() || selectedWorkspace
                                : "Repo selector"}
                            </span>
                          </button>
                        </div>
                        <div className="flex flex-col items-end gap-1.5">
                          <div className="flex items-center gap-1">
                            <span className="text-xs text-gray-600">Agent</span>
                            <Select
                              value={selectedAgent}
                              onValueChange={setSelectedAgent}
                            >
                              <SelectTrigger
                                className="h-7 w-[112px] text-xs"
                                aria-label="Select agent"
                              >
                                <SelectValue placeholder="Auto" />
                              </SelectTrigger>
                              <SelectContent>
                                {AGENT_OPTIONS.map((opt) => (
                                  <SelectItem key={opt.value || "auto"} value={opt.value}>
                                    {opt.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="flex items-center gap-1">
                            <span className="text-xs text-gray-600">Model</span>
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <span>
                                    <Select
                                      value={selectedModel}
                                      onValueChange={setSelectedModel}
                                      disabled={modelsLoadError}
                                    >
                                      <SelectTrigger
                                        className="h-7 w-[128px] text-xs"
                                        aria-label="Select model"
                                      >
                                        <SelectValue placeholder="Auto" />
                                      </SelectTrigger>
                                      <SelectContent>
                                        {modelOptions.map((opt) => (
                                          <SelectItem key={opt.value || "auto"} value={opt.value}>
                                            {opt.label}
                                          </SelectItem>
                                        ))}
                                      </SelectContent>
                                    </Select>
                                  </span>
                                </TooltipTrigger>
                                {(modelsLoadError || selectedModel === "") && (
                                  <TooltipContent side="top">
                                    {modelsLoadError
                                      ? "No models available (sidecar may not be running)"
                                      : "Auto: uses agent default (glm-5.2 for chat, qwen3.5:397b for coding)"}
                                  </TooltipContent>
                                )}
                              </Tooltip>
                            </TooltipProvider>
                          </div>
                          <div className="flex items-center gap-1">
                            <span className="text-xs text-gray-600">Voice</span>
                            <TooltipProvider>
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <span>
                                    <Select
                                      value={selectedVoice}
                                      onValueChange={setSelectedVoice}
                                      disabled={voicesLoadError || voiceOptions.length === 0}
                                    >
                                      <SelectTrigger
                                        className="h-7 w-[112px] text-xs"
                                        aria-label="Select voice"
                                      >
                                        <SelectValue placeholder="Auto" />
                                      </SelectTrigger>
                                      <SelectContent>
                                        {voiceOptions.map((opt) => (
                                          <SelectItem key={opt.id} value={opt.id}>
                                            {opt.name}
                                          </SelectItem>
                                        ))}
                                      </SelectContent>
                                    </Select>
                                  </span>
                                </TooltipTrigger>
                                {(voicesLoadError || voiceOptions.length === 0) && (
                                  <TooltipContent side="top">
                                    No voices available (TTS sidecar may not be running)
                                  </TooltipContent>
                                )}
                              </Tooltip>
                            </TooltipProvider>
                          </div>
                          <div className="mt-0.5 flex items-center gap-1.5">
                            <button
                              type="button"
                              onMouseDown={() => startRecording()}
                              onMouseUp={() =>
                                stopRecording(
                                  (text) => setInput((prev) => prev + text),
                                  (err) => console.error(err),
                                )
                              }
                              onMouseLeave={() => {
                                if (isRecording) {
                                  stopRecording(
                                    (text) => setInput((prev) => prev + text),
                                    (err) => console.error(err),
                                  );
                                }
                              }}
                              className={`flex cursor-pointer items-center gap-1 ${isRecording ? "text-red-500" : "text-gray-600"}`}
                              title={isRecording ? "Recording... release to transcribe" : "Hold to record"}
                            >
                              {isProcessing ? (
                                <LoaderCircle className="size-4 animate-spin" />
                              ) : (
                                <Mic className="size-4" />
                              )}
                              <span className="text-xs">
                                {isRecording ? "Recording..." : isProcessing ? "Transcribing..." : "Voice"}
                              </span>
                            </button>
                            {stream.isLoading ? (
                              <Button
                                key="stop"
                                onClick={() => stream.stop()}
                                className="h-7 text-xs"
                              >
                                <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                                Cancel
                              </Button>
                            ) : (
                              <Button
                                type="submit"
                                className="h-7 text-xs shadow-md transition-all"
                                disabled={
                                  isLoading ||
                                  (!input.trim() && contentBlocks.length === 0)
                                }
                              >
                                Send
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    </form>
                  </div>
                </div>
              }
            />
          </StickToBottom>
        </motion.div>
        <div className="relative flex flex-col border-l">
          <div className="absolute inset-0 flex min-w-[30vw] flex-col">
            <div className="grid grid-cols-[1fr_auto] border-b p-4">
              <ArtifactTitle className="truncate overflow-hidden" />
              <button
                onClick={closeArtifact}
                className="cursor-pointer"
              >
                <XIcon className="size-5" />
              </button>
            </div>
            <ArtifactContent className="relative flex-grow" />
          </div>
        </div>
      </div>
    </div>
  );
}
