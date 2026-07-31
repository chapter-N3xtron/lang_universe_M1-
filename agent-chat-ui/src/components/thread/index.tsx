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
import { WorkspaceShell } from "@/components/workspace/workspace-shell";
import type { JasperResponse } from "@/lib/visual/jasper-response.generated";

const ThreadHistory = dynamic(() => import("./history"), { ssr: false });
const TodoList = dynamic(() => import("./todos").then((m) => m.TodoList), {
  ssr: false,
});
const VisualSurface = dynamic(
  () =>
    import("@/components/workspace/visual-surface").then(
      (module) => module.VisualSurface,
    ),
  { ssr: false },
);

function StickyToBottomContent(props: {
  content: ReactNode;
  className?: string;
  scrollClassName?: string;
  contentClassName?: string;
}) {
  const context = useStickToBottomContext();
  return (
    <div className={props.className}>
      <div
        ref={context.scrollRef}
        className={props.scrollClassName}
      >
        <div
          ref={context.contentRef}
          className={props.contentClassName}
        >
          {props.content}
        </div>
      </div>
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
  const structuredCandidate = stream.values?.jasper_structured_response;
  const [validatedEntry, setValidatedEntry] = useState<{
    candidate: unknown;
    value: JasperResponse | null;
  } | null>(null);
  useEffect(() => {
    if (!structuredCandidate) return;
    let active = true;
    void import("@/lib/visual/validate").then(({ validateJasperResponse }) => {
      if (!active) return;
      const result = validateJasperResponse(structuredCandidate);
      setValidatedEntry({
        candidate: structuredCandidate,
        value: result.valid ? result.value : null,
      });
    });
    return () => {
      active = false;
    };
  }, [structuredCandidate]);
  const validatedJasperResponse =
    validatedEntry && validatedEntry.candidate === structuredCandidate
      ? validatedEntry.value
      : null;
  const visualArtifacts = validatedJasperResponse?.artifacts ?? [];
  const latestVisualArtifact = visualArtifacts.at(-1);
  const visualAvailable = Boolean(latestVisualArtifact || artifactOpen);

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

      <WorkspaceShell
        threadId={threadId}
        visualAvailable={visualAvailable}
        suggestion={validatedJasperResponse?.layout_suggestion ?? null}
        chat={
          <div
            className={cn(
              "relative flex h-full min-w-0 flex-1 flex-col overflow-hidden transition-[margin] duration-200 motion-reduce:transition-none",
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
                className="absolute inset-0 flex min-h-0 flex-col overflow-hidden"
                scrollClassName="min-h-0 flex-1 overflow-y-auto px-4 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-track]:bg-transparent"
                contentClassName={cn(
                  "mx-auto flex w-full max-w-3xl flex-col gap-4 pt-8 pb-8",
                  !chatStarted && "min-h-full justify-end",
                )}
                content={
                  <MessageList
                    isLoading={isLoading}
                    firstTokenReceived={firstTokenReceived}
                    selectedVoice={selectedVoice}
                    onRegenerateStart={handleRegenerate}
                  />
                }
              />
            </StickToBottom>
          </div>
        }
        visual={
          <VisualSurface
            artifact={latestVisualArtifact}
            selectedVoice={selectedVoice}
            legacyActive={artifactOpen}
            legacyTitle={<ArtifactTitle className="truncate overflow-hidden" />}
            legacyContent={<ArtifactContent className="relative h-full" />}
          />
        }
        composer={
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
            targetAgent={stream.values?.target_agent}
            targetModel={stream.values?.model}
            streamActions={streamActions}
            onStartSubmit={handleSubmit}
          />
        }
      />
    </div>
  );
}

export const Thread = memo(ThreadImpl);
