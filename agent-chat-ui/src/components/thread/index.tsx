import {
  ReactNode,
  useEffect,
  useRef,
  useState,
  useCallback,
  memo,
  useMemo,
} from "react";
import { cn } from "@/lib/utils";
import { useStreamContext, type StreamContextType } from "@/providers/Stream";
import { Button } from "../ui/button";
import { LangGraphLogoSVG } from "../icons/langgraph";
import { TooltipIconButton } from "./tooltip-icon-button";
import {
  List,
  ListX,
  PanelRightOpen,
  PanelRightClose,
  SquarePen,
  XIcon,
} from "lucide-react";
import { useQueryState, parseAsBoolean } from "nuqs";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { toast } from "sonner";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { GitHubSVG } from "../icons/github";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";
import {
  useArtifactOpen,
  ArtifactContent,
  ArtifactTitle,
  useArtifactContext,
} from "./artifact";
import { useModelAndVoices } from "@/hooks/use-model-and-voices";
import { MessageList } from "./message-list";
import { ChatInput } from "./chat-input";
import dynamic from "next/dynamic";

const ThreadHistory = dynamic(() => import("./history"), { ssr: false });
const TodoList = dynamic(() => import("./todos").then((m) => m.TodoList), {
  ssr: false,
});

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

function ThreadImpl() {
  const [, setArtifactContext] = useArtifactContext();
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

  const {
    modelOptions,
    modelProviders,
    defaultModel,
    modelsLoadError,
    voiceOptions,
    voicesLoadError,
    selectedVoice,
    setSelectedVoice,
  } = useModelAndVoices();

  const [firstTokenReceived, setFirstTokenReceived] = useState(false);
  const isLargeScreen = useMediaQuery("(min-width: 1024px)");

  const stream = useStreamContext();
  const streamRef = useRef(stream);
  useEffect(() => {
    streamRef.current = stream;
  }, [stream]);
  const streamActions = useMemo(
    () => ({
      getMessages: () => streamRef.current.messages,
      submit: ((...args: Parameters<StreamContextType["submit"]>) =>
        streamRef.current.submit(...args)) as StreamContextType["submit"],
      stop: () => streamRef.current.stop(),
    }),
    [],
  );
  const messages = stream.messages;
  const isLoading = stream.isLoading;

  const lastError = useRef<string | undefined>(undefined);

  const setThreadId = useCallback(
    (id: string | null) => {
      _setThreadId(id);
      closeArtifact();
      setArtifactContext({});
    },
    [_setThreadId, closeArtifact, setArtifactContext],
  );

  useEffect(() => {
    if (!stream.error) {
      lastError.current = undefined;
      return;
    }
    try {
      const message = (stream.error as any).message;
      if (!message || lastError.current === message) return;
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

  const handleSubmit = useCallback(() => {
    setFirstTokenReceived(false);
  }, []);

  const handleRegenerate = useCallback(() => {
    prevMessageLength.current = prevMessageLength.current - 1;
    setFirstTokenReceived(false);
  }, []);

  const chatStarted = !!threadId || !!messages.length;

  return (
    <div className="flex h-screen w-full overflow-hidden">
      <div className="relative hidden lg:flex">
        <div
          className="bg-background absolute z-20 h-full overflow-hidden border-r transition-transform duration-200 motion-reduce:transition-none"
          style={{
            width: 300,
            transform: `translateX(${chatHistoryOpen ? 0 : -300}px)`,
          }}
        >
          <div
            className="relative h-full"
            style={{ width: 300 }}
          >
            <ThreadHistory />
          </div>
        </div>
      </div>

      <div
        className="absolute top-0 right-0 z-20 hidden h-full transition-transform duration-200 motion-reduce:transition-none lg:flex"
        style={{ transform: `translateX(${todosOpen ? 0 : 300}px)` }}
      >
        <div
          className="bg-background h-full overflow-hidden border-l"
          style={{ width: 300 }}
        >
          <TodoList todosOpen={todosOpen} />
        </div>
      </div>

      <div
        className={cn(
          "grid w-full grid-cols-[1fr_0fr] transition-all duration-500",
          artifactOpen && "grid-cols-[3fr_2fr]",
        )}
      >
        <div
          className={cn(
            "relative flex min-w-0 flex-1 flex-col overflow-hidden transition-[margin] duration-200 motion-reduce:transition-none",
            !chatStarted && "grid-rows-[1fr]",
          )}
          style={{
            marginLeft: chatHistoryOpen && isLargeScreen ? 300 : 0,
          }}
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
                <button
                  className="flex cursor-pointer items-center gap-2 transition-[margin] duration-200 motion-reduce:transition-none"
                  onClick={() => setThreadId(null)}
                  style={{ marginLeft: !chatHistoryOpen ? 48 : 0 }}
                >
                  <LangGraphLogoSVG
                    width={32}
                    height={32}
                  />
                  <span className="text-xl font-semibold tracking-tight">
                    Agent Chat
                  </span>
                </button>
              </div>

              <div className="flex items-center gap-4">
                <div className="flex items-center">
                  {stream.values?.coding_status && (
                    <span className="mr-2 flex items-center gap-1.5 rounded-full bg-blue-900/30 px-2.5 py-0.5 text-xs text-blue-300">
                      <span
                        className={`inline-block size-1.5 rounded-full bg-blue-400 ${stream.values.coding_status === "running" ? "animate-pulse" : ""}`}
                      />
                      Coding: {stream.values.coding_status}
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
                <MessageList
                  isLoading={isLoading}
                  firstTokenReceived={firstTokenReceived}
                  selectedVoice={selectedVoice}
                  onRegenerateStart={handleRegenerate}
                />
              }
              footer={
                <ChatInput
                  isLoading={isLoading}
                  selectedVoice={selectedVoice}
                  onVoiceChange={setSelectedVoice}
                  modelOptions={modelOptions}
                  modelProviders={modelProviders}
                  defaultModel={defaultModel}
                  modelsLoadError={modelsLoadError}
                  voicesLoadError={voicesLoadError}
                  voiceOptions={voiceOptions}
                  chatStarted={chatStarted}
                  streamActions={streamActions}
                  onStartSubmit={handleSubmit}
                />
              }
            />
          </StickToBottom>
        </div>
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

export const Thread = memo(ThreadImpl);
