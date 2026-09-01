import React, {
  createContext,
  useContext,
  ReactNode,
  useState,
  useEffect,
} from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import { type Message } from "@langchain/langgraph-sdk";
import {
  uiMessageReducer,
  isUIMessage,
  isRemoveUIMessage,
  type UIMessage,
  type RemoveUIMessage,
} from "@langchain/langgraph-sdk/react-ui";
import { useQueryState } from "nuqs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { LangGraphLogoSVG } from "@/components/icons/langgraph";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { ArrowRight } from "lucide-react";
import { PasswordInput } from "@/components/ui/password-input";
import { getApiKey } from "@/lib/api-key";
import { useThreads } from "./Thread";
import type { TodoSection } from "@/lib/types/todo";
import type {
  ConceptMapArtifact,
  JasperResponse,
  LayoutSuggestion,
  ResponseDiagnostic,
} from "@/lib/visual/jasper-response.generated";

export type StateType = {
  messages: Message[];
  ui?: UIMessage[];
  active_agent?: string;
  handoff_history?: Record<string, unknown>[];
  decision_log?: Record<string, unknown>[];
  target_agent?: string;
  /** Selected repository path/root; retained as `workspace` in the graph state contract. */
  workspace?: string;
  model?: string;
  mode?: string;
  execution_mode?: "read_only" | "approval" | "autonomous";
  todos?: TodoSection[];
  coding_status?: string;
  coding_session_id?: string;
  jasper_structured_response?: JasperResponse;
  visual_artifacts?: ConceptMapArtifact[];
  layout_suggestion?: LayoutSuggestion | null;
  jasper_strategy?: "native" | "tool" | "two_pass" | "text";
  jasper_diagnostic?: ResponseDiagnostic | null;
};

const useTypedStream = useStream<
  StateType,
  {
    UpdateType: {
      messages?: Message[] | Message | string;
      ui?: (UIMessage | RemoveUIMessage)[] | UIMessage | RemoveUIMessage;
      context?: Record<string, unknown>;
      active_agent?: string;
      handoff_history?: Record<string, unknown>[];
      decision_log?: Record<string, unknown>[];
      target_agent?: string;
      workspace?: string;
      model?: string;
      mode?: string;
      execution_mode?: "read_only" | "approval" | "autonomous";
      todos?: TodoSection[];
      coding_status?: string;
      coding_session_id?: string;
      jasper_structured_response?: JasperResponse;
      visual_artifacts?: ConceptMapArtifact[];
      layout_suggestion?: LayoutSuggestion | null;
      jasper_strategy?: "native" | "tool" | "two_pass" | "text";
      jasper_diagnostic?: ResponseDiagnostic | null;
    };
    CustomEventType: UIMessage | RemoveUIMessage;
  }
>;

export type StreamContextType = ReturnType<typeof useTypedStream>;
const StreamContext = createContext<StreamContextType | undefined>(undefined);

async function sleep(ms = 4000) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function checkGraphStatus(
  apiUrl: string,
  apiKey: string | null,
  authScheme?: string,
): Promise<{ ok: boolean; reason?: string }> {
  try {
    const headers = new Headers();
    if (apiKey) headers.set("X-Api-Key", apiKey);
    if (authScheme) headers.set("X-Auth-Scheme", authScheme);

    const res = await fetch(`${apiUrl}/info`, {
      headers,
    });
    if (!res.ok)
      return { ok: false, reason: "The Agent Server is unavailable." };

    const identityResponse = await fetch(`${apiUrl}/runtime-identity`, {
      headers,
    });
    if (!identityResponse.ok) {
      return {
        ok: false,
        reason: "The server did not provide a durable runtime identity.",
      };
    }
    const identity = (await identityResponse.json()) as {
      runtime_id?: unknown;
      durable?: unknown;
      persistence?: unknown;
    };
    if (
      identity.runtime_id !== "backend-postgres-v1" ||
      identity.durable !== true ||
      identity.persistence !== "postgres"
    ) {
      return {
        ok: false,
        reason:
          "This is not the canonical PostgreSQL-backed Agent Server. The UI will not connect to a development session store.",
      };
    }

    return { ok: true };
  } catch (e) {
    console.error(e);
    return { ok: false, reason: "The Agent Server could not be reached." };
  }
}

const DurableRuntimeBoundary = ({
  children,
  apiKey,
  apiUrl,
  authScheme,
}: {
  children: ReactNode;
  apiKey: string | null;
  apiUrl: string;
  authScheme?: string;
}) => {
  const [status, setStatus] = useState<{
    checking: boolean;
    ok: boolean;
    reason?: string;
  }>({ checking: true, ok: false });

  useEffect(() => {
    let active = true;
    checkGraphStatus(apiUrl, apiKey, authScheme).then((result) => {
      if (active) setStatus({ checking: false, ...result });
    });
    return () => {
      active = false;
    };
  }, [apiKey, apiUrl, authScheme]);

  if (status.checking) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <p className="text-muted-foreground">
          Verifying durable session storage…
        </p>
      </div>
    );
  }
  if (!status.ok) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <div className="max-w-xl rounded-lg border p-6">
          <h1 className="text-lg font-semibold">Session storage unavailable</h1>
          <p className="text-muted-foreground mt-2">{status.reason}</p>
          <p className="text-muted-foreground mt-2 text-sm">
            Start the canonical Docker-backed Agent Server, then refresh this
            page. No development runtime has been connected.
          </p>
        </div>
      </div>
    );
  }
  return children;
};

const StreamSession = ({
  children,
  apiKey,
  apiUrl,
  assistantId,
  authScheme,
}: {
  children: ReactNode;
  apiKey: string | null;
  apiUrl: string;
  assistantId: string;
  authScheme?: string;
}) => {
  const [threadId, setThreadId] = useQueryState("threadId");
  const { getThreads, setThreads } = useThreads();
  const streamValue = useTypedStream({
    apiUrl,
    apiKey: apiKey ?? undefined,
    assistantId,
    throttle: 150,
    ...(authScheme && {
      defaultHeaders: {
        "X-Auth-Scheme": authScheme,
      },
    }),
    threadId: threadId ?? null,
    fetchStateHistory: true,
    onCustomEvent: (event, options) => {
      if (isUIMessage(event) || isRemoveUIMessage(event)) {
        options.mutate((prev) => {
          const ui = uiMessageReducer(prev.ui ?? [], event);
          return { ...prev, ui };
        });
      }
    },
    onThreadId: (id) => {
      setThreadId(id);
      // Refetch threads list when thread ID changes.
      // Wait for some seconds before fetching so we're able to get the new thread that was created.
      sleep().then(() => getThreads().then(setThreads).catch(console.error));
    },
  });

  return (
    <StreamContext.Provider value={streamValue}>
      {children}
    </StreamContext.Provider>
  );
};

// Default values for the form
const DEFAULT_API_URL = "http://localhost:2024";
const DEFAULT_ASSISTANT_ID = "agent";
const AGENT_BUILDER_AUTH_SCHEME = "langsmith-api-key";

export const StreamProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  // Get environment variables
  const envApiUrl: string | undefined = process.env.NEXT_PUBLIC_API_URL;
  const envAssistantId: string | undefined =
    process.env.NEXT_PUBLIC_ASSISTANT_ID;
  const envAuthScheme: string | undefined = process.env.NEXT_PUBLIC_AUTH_SCHEME;
  const authRequired = process.env.NEXT_PUBLIC_AUTH_REQUIRED === "true";

  // Use URL params with env var fallbacks
  const [apiUrl, setApiUrl] = useQueryState("apiUrl", {
    defaultValue: envApiUrl || "",
  });
  const [assistantId, setAssistantId] = useQueryState("assistantId", {
    defaultValue: envAssistantId || "",
  });
  const [authScheme, setAuthScheme] = useQueryState("authScheme", {
    defaultValue: envAuthScheme || "",
  });
  const [isAgentBuilder, setIsAgentBuilder] = useState(
    () =>
      (authScheme || envAuthScheme || "").toLowerCase() ===
      AGENT_BUILDER_AUTH_SCHEME,
  );

  // For API key, use localStorage with env var fallback
  const [apiKey, _setApiKey] = useState(() => {
    const storedKey = getApiKey();
    return storedKey || "";
  });

  const setApiKey = (key: string) => {
    window.localStorage.setItem("lg:chat:apiKey", key);
    _setApiKey(key);
  };

  // Determine final values to use, prioritizing URL params then env vars
  const finalApiUrl = apiUrl || envApiUrl;
  const finalAssistantId = assistantId || envAssistantId;
  const finalAuthScheme = authScheme || envAuthScheme || "";

  // Custom-auth installations still need a browser-entered credential when public
  // URL/assistant configuration bypasses the rest of the setup form.
  if (!finalApiUrl || !finalAssistantId || (authRequired && !apiKey)) {
    return (
      <div className="flex min-h-screen w-full items-center justify-center p-4">
        <div className="animate-in fade-in-0 zoom-in-95 bg-background flex max-w-3xl flex-col rounded-lg border shadow-lg">
          <div className="mt-14 flex flex-col gap-2 border-b p-6">
            <div className="flex flex-col items-start gap-2">
              <LangGraphLogoSVG className="h-7" />
              <h1 className="text-xl font-semibold tracking-tight">
                Agent Chat
              </h1>
            </div>
            <p className="text-muted-foreground">
              Welcome to Agent Chat! Before you get started, you need to enter
              the URL of the deployment and the assistant / graph ID.
            </p>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();

              const form = e.target as HTMLFormElement;
              const formData = new FormData(form);
              const apiUrl = formData.get("apiUrl") as string;
              const assistantId = formData.get("assistantId") as string;
              const apiKey = formData.get("apiKey") as string;

              setApiUrl(apiUrl);
              setApiKey(apiKey);
              setAssistantId(assistantId);
              setAuthScheme(isAgentBuilder ? AGENT_BUILDER_AUTH_SCHEME : "");

              form.reset();
            }}
            className="bg-muted/50 flex flex-col gap-6 p-6"
          >
            <div className="flex flex-col gap-2">
              <Label htmlFor="apiUrl">
                Deployment URL<span className="text-rose-500">*</span>
              </Label>
              <p className="text-muted-foreground text-sm">
                This is the URL of your LangGraph deployment. Can be a local, or
                production deployment.
              </p>
              <Input
                id="apiUrl"
                name="apiUrl"
                className="bg-background"
                defaultValue={apiUrl || DEFAULT_API_URL}
                required
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="assistantId">
                Assistant / Graph ID<span className="text-rose-500">*</span>
              </Label>
              <p className="text-muted-foreground text-sm">
                This is the ID of the graph (can be the graph name), or
                assistant to fetch threads from, and invoke when actions are
                taken.
              </p>
              <Input
                id="assistantId"
                name="assistantId"
                className="bg-background"
                defaultValue={assistantId || DEFAULT_ASSISTANT_ID}
                required
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="apiKey">
                Agent Server API Key
                {authRequired && <span className="text-rose-500">*</span>}
              </Label>
              <p className="text-muted-foreground text-sm">
                Enter the credential required by this Agent Server. It is stored
                in your browser's local storage and is only sent to that server;
                no secret is read from public frontend configuration.
              </p>
              <PasswordInput
                id="apiKey"
                name="apiKey"
                defaultValue={apiKey ?? ""}
                className="bg-background"
                placeholder="API key"
                required={authRequired}
              />
            </div>

            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between gap-4">
                <div className="flex flex-col gap-1">
                  <Label htmlFor="agentBuilderEnabled">
                    Built with Agent Builder
                  </Label>
                  <p className="text-muted-foreground text-sm">
                    Enable this for Agent Builder deployments.
                  </p>
                </div>
                <Switch
                  id="agentBuilderEnabled"
                  checked={isAgentBuilder}
                  onCheckedChange={setIsAgentBuilder}
                />
              </div>
            </div>

            <div className="mt-2 flex justify-end">
              <Button
                type="submit"
                size="lg"
              >
                Continue
                <ArrowRight className="size-5" />
              </Button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <DurableRuntimeBoundary
      key={`${finalApiUrl}|${finalAuthScheme}|${apiKey}`}
      apiKey={apiKey}
      apiUrl={finalApiUrl}
      authScheme={finalAuthScheme || undefined}
    >
      <StreamSession
        apiKey={apiKey}
        apiUrl={finalApiUrl}
        assistantId={finalAssistantId}
        authScheme={finalAuthScheme || undefined}
      >
        {children}
      </StreamSession>
    </DurableRuntimeBoundary>
  );
};

// Create a custom hook to use the context
export const useStreamContext = (): StreamContextType => {
  const context = useContext(StreamContext);
  if (context === undefined) {
    throw new Error("useStreamContext must be used within a StreamProvider");
  }
  return context;
};

export default StreamContext;
