"use client";

import {
  useState,
  FormEvent,
  useCallback,
  memo,
  useEffect,
  useRef,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { v4 as uuidv4 } from "uuid";
import { Button } from "../ui/button";
import { Message } from "@langchain/langgraph-sdk";
import type { StreamContextType } from "@/providers/Stream";
import { useSTT } from "@/hooks/useSTT";
import { useQueryState, parseAsBoolean } from "nuqs";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../ui/tooltip";
import { Label } from "../ui/label";
import {
  ChevronRight,
  Folder,
  LoaderCircle,
  Mic,
  Phone,
  Plus,
  Send,
  Square,
  Wrench,
} from "lucide-react";
import { ContentBlocksPreview } from "./ContentBlocksPreview";
import { useFileUpload } from "@/hooks/use-file-upload";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { DOCUMENT_ACCEPT } from "@/lib/multimodal-utils";
import {
  fetchModelPreference,
  saveModelPreference,
} from "@/lib/session-catalog";

const AGENT_OPTIONS = [
  { value: "", label: "Auto" },
  { value: "jasper", label: "Jasper" },
  { value: "coding", label: "Deep Agent" },
  { value: "librarian", label: "The Librarian" },
  { value: "magic-coder", label: "Magic Coder" },
] as const;

const DEFAULT_AGENT = "jasper";

function agentValue(targetAgent: string | undefined): string {
  if (targetAgent === "research") return "librarian";
  return targetAgent === undefined ? DEFAULT_AGENT : targetAgent;
}

interface ModelOption {
  value: string;
  label: string;
}

function sortModelOptions(options: ModelOption[]): ModelOption[] {
  return [...options].sort((left, right) =>
    left.label.localeCompare(right.label, undefined, {
      numeric: true,
      sensitivity: "base",
    }),
  );
}

interface ChatInputProps {
  isLoading: boolean;
  selectedVoice: string;
  onVoiceChange: (v: string) => void;
  modelOptions: ModelOption[];
  modelProviders: Record<string, string>;
  defaultModel: string;
  modelsLoadError: boolean;
  voicesLoadError: boolean;
  voiceOptions: { id: string; name: string }[];
  chatStarted: boolean;
  targetAgent?: string;
  threadId: string | null;
  workspace?: string;
  streamActions: {
    submit: StreamContextType["submit"];
    stop: () => void;
  };
  onStartSubmit: () => void;
  apiUrl: string;
  authScheme?: string;
  workspaceControls: ReactNode;
}

function isCloudModel(
  modelId: string,
  providers: Record<string, string>,
  defaultId: string,
): boolean {
  const id = modelId || defaultId;
  if (!id) return false;
  const provider = providers[id];
  if (provider && provider !== "ollama") return true;
  return false;
}

function ChatInputImpl({
  isLoading,
  selectedVoice,
  onVoiceChange,
  modelOptions,
  modelProviders,
  defaultModel,
  modelsLoadError,
  voicesLoadError,
  voiceOptions,
  chatStarted,
  targetAgent,
  threadId,
  workspace,
  streamActions,
  onStartSubmit,
  apiUrl,
  authScheme,
  workspaceControls,
}: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [agentSelection, setAgentSelection] = useState({
    source: targetAgent,
    value: agentValue(targetAgent),
  });
  const selectedAgent =
    agentSelection.source === targetAgent
      ? agentSelection.value
      : agentValue(targetAgent);
  const [workspaceDrafts, setWorkspaceDrafts] = useState<
    Record<string, string>
  >({});
  const workspaceKey = threadId ?? "__new_thread__";
  const effectiveWorkspace = Object.prototype.hasOwnProperty.call(
    workspaceDrafts,
    workspaceKey,
  )
    ? workspaceDrafts[workspaceKey]
    : workspace;
  const [isPickingWorkspace, setIsPickingWorkspace] = useState(false);
  const [selectedModel, setSelectedModel] = useState("");
  useEffect(() => {
    let active = true;
    fetchModelPreference(apiUrl, authScheme)
      .then(({ model_id }) => {
        if (active && model_id) setSelectedModel(model_id);
      })
      .catch(() => {
        // A persisted preference is optional; the profile/thread default remains usable.
      });
    return () => {
      active = false;
    };
  }, [apiUrl, authScheme]);
  const effectiveSelectedModel = selectedModel || defaultModel;
  const selectedModelLabel =
    modelOptions.find((option) => option.value === effectiveSelectedModel)
      ?.label ?? effectiveSelectedModel;
  const selectedModelProvider = modelProviders[effectiveSelectedModel] ?? "";
  const selectedModelLocation =
    selectedModelProvider === "ollama"
      ? "Ollama · Local"
      : selectedModelProvider === "ollama-cloud"
        ? "Ollama · Cloud"
        : selectedModelProvider === "fireworks"
          ? "Fireworks"
          : "Cloud";
  const [executionMode, setExecutionMode] = useState<
    "read_only" | "approval" | "autonomous"
  >("approval");
  const [expandedModelGroups, setExpandedModelGroups] = useState<
    Record<string, boolean>
  >({});

  const localOllamaModels = sortModelOptions(
    modelOptions.filter((option) => modelProviders[option.value] === "ollama"),
  );
  const cloudOllamaModels = sortModelOptions(
    modelOptions.filter(
      (option) => modelProviders[option.value] === "ollama-cloud",
    ),
  );
  const fireworksModels = sortModelOptions(
    modelOptions.filter((option) => modelProviders[option.value] === "fireworks"),
  );
  const openaiModels = sortModelOptions(
    modelOptions.filter((option) => modelProviders[option.value] === "openai"),
  );
  const otherCloudModels = sortModelOptions(
    modelOptions.filter((option) => {
      const provider = modelProviders[option.value];
      return !["ollama", "ollama-cloud", "fireworks", "openai"].includes(
        provider,
      );
    }),
  );
  const openaiVersionGroups = Array.from(
    openaiModels.reduce((groups, option) => {
      const match = option.label.match(/^(gpt-\d+(?:\.\d+)?)/i);
      const version = match ? match[1].toUpperCase() : "Other";
      groups.set(version, [...(groups.get(version) ?? []), option]);
      return groups;
    }, new Map<string, ModelOption[]>()),
  );
  const isModelGroupExpanded = (group: string, containsSelection: boolean) =>
    expandedModelGroups[group] ?? containsSelection;
  const toggleModelGroup = (group: string, containsSelection: boolean) => {
    setExpandedModelGroups((groups) => ({
      ...groups,
      [group]: !isModelGroupExpanded(group, containsSelection),
    }));
  };
  const ollamaContainsSelection = ["ollama", "ollama-cloud"].includes(
    selectedModelProvider,
  );
  const ollamaExpanded = isModelGroupExpanded("ollama", ollamaContainsSelection);
  const localOllamaExpanded = isModelGroupExpanded(
    "ollama-local",
    selectedModelProvider === "ollama",
  );
  const cloudOllamaExpanded = isModelGroupExpanded(
    "ollama-cloud",
    selectedModelProvider === "ollama-cloud",
  );
  const fireworksExpanded = isModelGroupExpanded(
    "fireworks",
    selectedModelProvider === "fireworks",
  );
  const openaiExpanded = isModelGroupExpanded(
    "openai",
    selectedModelProvider === "openai",
  );
  const otherCloudExpanded = isModelGroupExpanded(
    "other-cloud",
    !selectedModelProvider ||
      !["ollama", "ollama-cloud", "fireworks", "openai"].includes(
        selectedModelProvider,
      ),
  );
  const [hideToolCalls, setHideToolCalls] = useQueryState(
    "hideToolCalls",
    parseAsBoolean.withDefault(false),
  );
  useEffect(() => {
    const discussNode = (event: Event) => {
      const prompt = (event as CustomEvent<{ prompt?: string }>).detail?.prompt;
      if (!prompt) return;
      setInput(prompt);
      setAgentSelection({ source: targetAgent, value: "jasper" });
      window.requestAnimationFrame(() => textareaRef.current?.focus());
    };
    window.addEventListener("jasper:discuss-node", discussNode);
    return () => window.removeEventListener("jasper:discuss-node", discussNode);
  }, [targetAgent]);
  const {
    contentBlocks,
    setContentBlocks,
    handleFileUpload,
    dropRef,
    removeBlock,
    dragOver,
    handlePaste,
  } = useFileUpload();

  const {
    startRecording,
    stopRecording,
    isRecording,
    isProcessing,
    isAcquiring,
  } = useSTT();

  const finishVoiceRecording = useCallback(() => {
    stopRecording(
      (text) => setInput((prev) => prev + text),
      (err) => console.error(err),
    );
  }, [stopRecording]);

  const handleVoiceKeyDown = useCallback(
    (event: KeyboardEvent<HTMLButtonElement>) => {
      if (event.key !== " " && event.key !== "Spacebar") return;

      event.preventDefault();
      if (event.repeat) return;

      if (isRecording || isAcquiring) {
        finishVoiceRecording();
      } else {
        startRecording();
      }
    },
    [finishVoiceRecording, isAcquiring, isRecording, startRecording],
  );

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      if (
        (input.trim().length === 0 && contentBlocks.length === 0) ||
        isLoading
      )
        return;

      const newHumanMessage: Message = {
        id: uuidv4(),
        type: "human",
        content: [
          ...(input.trim().length > 0 ? [{ type: "text", text: input }] : []),
          ...contentBlocks,
        ] as Message["content"],
      };

      onStartSubmit();
      streamActions.submit(
        {
          messages: [newHumanMessage],
          context: undefined,
          target_agent: selectedAgent,
          workspace: effectiveWorkspace,
          model: effectiveSelectedModel || undefined,
          execution_mode: executionMode,
        },
        {
          streamMode: ["messages"],
          streamSubgraphs: false,
          streamResumable: true,
          multitaskStrategy: "reject",
          onDisconnect: executionMode === "autonomous" ? "continue" : "cancel",
          config: isCloudModel(
            effectiveSelectedModel,
            modelProviders,
            defaultModel,
          )
            ? { tags: ["langsmith:nostream"] }
            : undefined,
          optimisticValues: (prev) => ({
            ...prev,
            context: undefined,
            target_agent: selectedAgent,
            workspace: effectiveWorkspace,
            model: effectiveSelectedModel || undefined,
            execution_mode: executionMode,
            messages: [...(prev.messages ?? []), newHumanMessage],
          }),
        },
      );

      setInput("");
      setContentBlocks([]);
    },
    [
      input,
      contentBlocks,
      isLoading,
      selectedAgent,
      effectiveWorkspace,
      effectiveSelectedModel,
      executionMode,
      modelProviders,
      defaultModel,
      streamActions,
      onStartSubmit,
      setContentBlocks,
    ],
  );

  return (
    <div className="bg-background flex shrink-0 flex-col items-center px-4 pt-2 lg:pb-6">
      {!chatStarted && null}

      <div
        ref={dropRef}
        className={cn(
          "bg-muted relative z-10 mx-auto mb-4 h-72 w-full max-w-6xl overflow-hidden rounded-2xl shadow-xs transition-all lg:h-48",
          dragOver
            ? "border-primary border-2 border-dotted"
            : "border border-solid",
        )}
      >
        <form
          onSubmit={handleSubmit}
          className="mx-auto grid h-full w-full max-w-6xl gap-2 lg:grid-cols-[minmax(190px,240px)_minmax(0,1fr)_minmax(190px,240px)] lg:grid-rows-[auto_minmax(0,1fr)]"
        >
          <div className="lg:col-span-3">
            <ContentBlocksPreview
              blocks={contentBlocks}
              onRemove={removeBlock}
            />
          </div>
          <div
            className="flex min-h-0 min-w-0 items-end gap-1.5 lg:col-start-2 lg:row-start-2 lg:flex-col lg:items-center lg:justify-end lg:gap-2"
            data-composer-column="center"
          >
            <textarea
              ref={textareaRef}
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
              className="focus-visible:ring-ring/50 h-24 min-h-24 min-w-0 flex-1 resize-none overflow-y-auto rounded-md border border-white/30 bg-transparent p-3.5 shadow-none outline-none focus-visible:border-white/60 focus-visible:ring-2 lg:col-start-2 lg:row-start-2 lg:w-full lg:flex-none"
            />
            <div className="mt-0.5 flex shrink-0 items-center justify-center gap-1.5 lg:mt-0">
              <Button
                type="button"
                size="icon"
                variant={isRecording || isAcquiring ? "destructive" : "brand"}
                className="size-9 rounded-md text-white shadow-md transition-all"
                aria-label={
                  isRecording || isAcquiring
                    ? "Recording. Press Space again to stop and transcribe, or release the button."
                    : isProcessing
                      ? "Transcribing..."
                      : "Voice recording. Focus this button and press Space to start, then press Space again to stop. Hold the button to record."
                }
                title={
                  isRecording || isAcquiring
                    ? "Press Space again to stop and transcribe, or release the button"
                    : "Focus this button and press Space to start recording, then press Space again to stop. Hold to record"
                }
                aria-keyshortcuts="Space"
                onKeyDown={handleVoiceKeyDown}
                onMouseDown={() => startRecording()}
                onMouseUp={finishVoiceRecording}
                onMouseLeave={() => {
                  if (isRecording) finishVoiceRecording();
                }}
              >
                {isProcessing ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <Mic className="size-4" />
                )}
              </Button>
              {isLoading ? (
                <Button
                  key="stop"
                  type="button"
                  size="icon"
                  variant="destructive"
                  aria-label="Cancel response"
                  title="Cancel response"
                  onClick={() => {
                    window.dispatchEvent(
                      new Event("conversation:cancel-positioning"),
                    );
                    streamActions.stop();
                  }}
                  className="size-9 rounded-md text-white shadow-md transition-all"
                >
                  <Square className="size-4 fill-current" />
                </Button>
              ) : (
                <Button
                  type="submit"
                  size="icon"
                  variant="brand"
                  className="size-9 rounded-md text-white shadow-md transition-all"
                  aria-label="Send message"
                  title="Send message"
                  disabled={
                    isLoading || (!input.trim() && contentBlocks.length === 0)
                  }
                >
                  <Send className="size-4" />
                </Button>
              )}
            </div>
          </div>

          <div className="flex items-start justify-between gap-1.5 p-1.5 pt-3 lg:contents">
            <div
              className="flex flex-col gap-1.5 lg:col-start-1 lg:row-start-2 lg:items-start"
              data-composer-column="left"
            >
              <div className="flex items-center gap-1">
                <span className="text-xs text-gray-600">Model</span>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span>
                        <Select
                          value={effectiveSelectedModel}
                          onValueChange={(value) => {
                            if (!value) return;
                            setSelectedModel(value);
                            void saveModelPreference(
                              apiUrl,
                              value,
                              authScheme,
                            ).catch(() =>
                              toast.error(
                                "The model preference could not be saved.",
                              ),
                            );
                          }}
                          disabled={modelsLoadError}
                        >
                          <SelectTrigger
                            className="h-7 w-[128px] text-xs"
                            aria-label="Select model"
                          >
                            <SelectValue placeholder="Loading…">
                              {effectiveSelectedModel
                                ? `${selectedModelLocation} · ${selectedModelLabel}`
                                : undefined}
                            </SelectValue>
                          </SelectTrigger>
                          <SelectContent><div className="bg-muted/50 sticky top-0 z-10 mx-1 rounded-sm px-2 py-1.5 text-xs"><div className="text-muted-foreground">Current model</div><div className="truncate font-medium" title={effectiveSelectedModel}>{selectedModelLocation} · {effectiveSelectedModel}</div></div><SelectSeparator /><details open={ollamaContainsSelection}><summary>Ollama ({localOllamaModels.length + cloudOllamaModels.length})</summary><details open={selectedModelProvider === "ollama"}><summary>Local ({localOllamaModels.length})</summary>{localOllamaModels.map((opt) => <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>)}</details><details open={selectedModelProvider === "ollama-cloud"}><summary>Cloud ({cloudOllamaModels.length})</summary>{cloudOllamaModels.map((opt) => <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>)}</details></details><details open={selectedModelProvider === "fireworks"}><summary>Fireworks ({fireworksModels.length})</summary>{fireworksModels.map((opt) => <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>)}</details><details open={selectedModelProvider === "openai"}><summary>OpenAI ({openaiModels.length})</summary>{openaiVersionGroups.map(([version, models]) => <details key={version}><summary>{version} ({models.length})</summary>{models.map((opt) => <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>)}</details>)}</details></SelectContent>
                        </Select>
                      </span>
                    </TooltipTrigger>
                    {modelsLoadError && (
                      <TooltipContent side="top">
                        No models available (sidecar may not be running)
                      </TooltipContent>
                    )}
                  </Tooltip>
                </TooltipProvider>
              </div>
              {workspaceControls}
              <div className="flex items-center space-x-1.5 lg:order-4">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        type="button"
                        size="icon"
                        variant={hideToolCalls ? "secondary" : "ghost"}
                        role="switch"
                        aria-checked={hideToolCalls}
                        aria-label={
                          hideToolCalls ? "Show tool calls" : "Hide tool calls"
                        }
                        onClick={() => setHideToolCalls(!hideToolCalls)}
                      >
                        <Wrench className="size-4" />
                        <Phone className="mt-2 -ml-2 size-2.5" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      {hideToolCalls ? "Show tool calls" : "Hide tool calls"}
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
              <Label
                htmlFor="file-input"
                className="flex cursor-pointer items-center gap-1.5 lg:order-3"
              >
                <Plus className="size-4 text-gray-600" />
                <span className="text-xs text-gray-600">Upload file</span>
              </Label>
              <input
                id="file-input"
                type="file"
                onChange={handleFileUpload}
                multiple
                accept={`image/jpeg,image/png,image/gif,image/webp,${DOCUMENT_ACCEPT}`}
                className="hidden"
              />
            </div>
            <div
              className="flex flex-col items-end gap-1.5 lg:col-start-3 lg:row-start-2 lg:gap-1.5"
              data-composer-column="right"
            >
              <div className="flex items-center gap-1 lg:order-1">
                <span className="text-xs text-gray-600">Agent</span>
                <Select
                  value={selectedAgent}
                  onValueChange={(value) =>
                    setAgentSelection({ source: targetAgent, value })
                  }
                >
                  <SelectTrigger
                    className="h-7 w-[112px] text-xs"
                    aria-label="Select agent"
                  >
                    <SelectValue placeholder="Auto" />
                  </SelectTrigger>
                  <SelectContent>
                    {AGENT_OPTIONS.map((opt) => (
                      <SelectItem
                        key={opt.value || "auto"}
                        value={opt.value}
                      >
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <button
                type="button"
                aria-label="Select repository folder"
                disabled={isPickingWorkspace}
                onClick={async () => {
                  setIsPickingWorkspace(true);
                  try {
                    const pickerUrl = new URL(
                      "http://127.0.0.1:8765/api/fs/pick-folder",
                    );
                    pickerUrl.searchParams.set(
                      "starting_path",
                      effectiveWorkspace ?? "",
                    );
                    const res = await fetch(pickerUrl);
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    const data = (await res.json()) as {
                      cancelled?: boolean;
                      path?: unknown;
                    };
                    if (
                      !data.cancelled &&
                      typeof data.path === "string" &&
                      data.path.length > 0
                    ) {
                      setWorkspaceDrafts((drafts) => ({
                        ...drafts,
                        [workspaceKey]: data.path as string,
                      }));
                    }
                  } catch (error) {
                    console.error("[Repo picker] failed:", error);
                    toast.error("Could not open folder picker", {
                      description:
                        "Check that the host worker is running and macOS allows Finder access.",
                    });
                  } finally {
                    setIsPickingWorkspace(false);
                  }
                }}
                className="flex cursor-pointer items-center gap-1.5 disabled:cursor-wait disabled:opacity-60 lg:order-3"
              >
                {isPickingWorkspace ? (
                  <LoaderCircle className="size-4 animate-spin text-gray-600" />
                ) : (
                  <Folder className="size-4 text-gray-600" />
                )}
                <span
                  className="max-w-56 truncate text-xs text-gray-600"
                  data-testid="effective-workspace"
                  title={effectiveWorkspace}
                >
                  {isPickingWorkspace
                    ? "Opening…"
                    : (effectiveWorkspace ?? "Repo selector")}
                </span>
              </button>
              <div className="flex items-center gap-1 lg:order-4">
                <span className="text-xs text-gray-600">Access</span>
                <Select
                  value={executionMode}
                  onValueChange={(value) =>
                    setExecutionMode(
                      value as "read_only" | "approval" | "autonomous",
                    )
                  }
                >
                  <SelectTrigger
                    className="h-7 w-[112px] text-xs"
                    aria-label="Select coding access"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="read_only">Read only</SelectItem>
                    <SelectItem value="approval">Full repo (review)</SelectItem>
                    <SelectItem value="autonomous">
                      Full repo (autonomous)
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-1 lg:order-2">
                <span className="text-xs text-gray-600">Voice</span>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span>
                        <Select
                          value={selectedVoice}
                          onValueChange={onVoiceChange}
                          disabled={
                            voicesLoadError || voiceOptions.length === 0
                          }
                        >
                          <SelectTrigger
                            className="h-7 w-[112px] text-xs"
                            aria-label="Select voice"
                          >
                            <SelectValue placeholder="Auto" />
                          </SelectTrigger>
                          <SelectContent>
                            {voiceOptions.map((opt) => (
                              <SelectItem
                                key={opt.id}
                                value={opt.id}
                              >
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
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

export const ChatInput = memo(ChatInputImpl);
