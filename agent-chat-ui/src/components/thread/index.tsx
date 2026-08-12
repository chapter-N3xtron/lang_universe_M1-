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
import { useQueryState, parseAsBoolean, parseAsStringLiteral } from "nuqs";
import { StickToBottom, useStickToBottomContext } from "use-stick-to-bottom";
import { toast } from "sonner";
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
import { openSession } from "@/lib/session-catalog";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";
import { SessionWorkspaceTopBar } from "@/components/workspace/session-workspace-top-bar";
import type { JasperResponse } from "@/lib/visual/jasper-response.generated";

const TodoList = dynamic(() => import("./todos").then((m) => m.TodoList), {
  ssr: false,
});
const SessionVisualPane = dynamic(
  () =>
    import("@/components/workspace/session-visual-pane").then(
      (module) => module.SessionVisualPane,
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
        data-conversation-viewport
      >
        <div
          ref={context.contentRef}
          className={props.contentClassName}
          data-conversation-content-shell
        >
          {props.content}
        </div>
      </div>
    </div>
  );
}

function ThreadImpl() {
  const [, setArtifactContext] = useArtifactContext();
  const [artifactOpen, closeArtifact] = useArtifactOpen();

  const [threadId, _setThreadId] = useQueryState("threadId");
  const [, setSessionView] = useQueryState(
    "sessionView",
    parseAsStringLiteral(["library", "session", "sources"] as const),
  );
  const [apiUrl] = useQueryState("apiUrl", {
    defaultValue: process.env.NEXT_PUBLIC_API_URL || "",
  });
  const [authScheme] = useQueryState("authScheme", {
    defaultValue: process.env.NEXT_PUBLIC_AUTH_SCHEME || "",
  });
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
  const [isOpeningSession, setIsOpeningSession] = useState(false);
  const stream = useStreamContext();
  const streamRef = useRef(stream);
  useEffect(() => {
    streamRef.current = stream;
  }, [stream]);
  const streamActions = useMemo(
    () => ({
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
      setSessionView(id ? "session" : "library");
      closeArtifact();
      setArtifactContext({});
    },
    [_setThreadId, closeArtifact, setArtifactContext, setSessionView],
  );

  const handleOpenSession = useCallback(async () => {
    if (!apiUrl || isOpeningSession) return;
    setIsOpeningSession(true);
    try {
      const result = await openSession(apiUrl, authScheme || undefined);
      setThreadId(result.thread_id);
    } catch (error) {
      toast.error("The session could not be opened.", {
        description: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setIsOpeningSession(false);
    }
  }, [apiUrl, authScheme, isOpeningSession, setThreadId]);

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
  const visualAvailable = true;

  return (
    <div className="flex h-screen w-full overflow-hidden">
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
        topBar={
          <SessionWorkspaceTopBar
            apiUrl={apiUrl}
            authScheme={authScheme || undefined}
            threadId={threadId}
            todosOpen={todosOpen}
            isOpeningSession={isOpeningSession}
            onToggleTodos={() => setTodosOpen((open) => !open)}
            onOpenSession={handleOpenSession}
            onSelectThread={setThreadId}
          />
        }
        chat={
          <div
            className={cn(
              "relative flex h-full min-w-0 flex-1 flex-col overflow-hidden transition-[margin] duration-200 motion-reduce:transition-none",
              !chatStarted && "grid-rows-[1fr]",
            )}
          >



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
          <SessionVisualPane
            apiUrl={apiUrl}
            authScheme={authScheme || undefined}
            threadId={threadId}
            latestArtifact={latestVisualArtifact}
            selectedVoice={selectedVoice}
            legacyActive={artifactOpen}
            legacyTitle={<ArtifactTitle className="truncate overflow-hidden" />}
            legacyContent={<ArtifactContent className="relative h-full" />}
            onSelectThread={(selectedThreadId) => setThreadId(selectedThreadId)}
          />
        }
        composer={(workspaceControls) => (
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
            streamActions={streamActions}
            onStartSubmit={handleSubmit}
            apiUrl={apiUrl}
            authScheme={authScheme || undefined}
            workspaceControls={workspaceControls}
          />
        )}
      />
    </div>
  );
}

export const Thread = memo(ThreadImpl);
