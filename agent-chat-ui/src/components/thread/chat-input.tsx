"use client";

import {
  useState,
  FormEvent,
  useCallback,
  memo,
  useEffect,
  useRef,
} from "react";
import { v4 as uuidv4 } from "uuid";
import { Button } from "../ui/button";
import { Message } from "@langchain/langgraph-sdk";
import type { StreamContextType } from "@/providers/Stream";
import { useSTT } from "@/hooks/useSTT";
import { ensureToolCallsHaveResponses } from "@/lib/ensure-tool-responses";
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
import { Switch } from "../ui/switch";
import { Plus, Mic, LoaderCircle, Folder } from "lucide-react";
import { ContentBlocksPreview } from "./ContentBlocksPreview";
import { useFileUpload } from "@/hooks/use-file-upload";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { DOCUMENT_ACCEPT } from "@/lib/multimodal-utils";

const AGENT_OPTIONS = [
  { value: "", label: "Auto" },
  { value: "jasper", label: "Jasper" },
  { value: "coding", label: "Deep Agent" },
  { value: "research", label: "Research" },
  { value: "magic-coder", label: "Magic Coder" },
] as const;

const DEFAULT_AGENT = "jasper";

function agentValue(targetAgent: string | undefined): string {
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
  targetModel?: string;
  streamActions: {
    getMessages: () => Message[];
    submit: StreamContextType["submit"];
    stop: () => void;
  };
  onStartSubmit: () => void;
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
  targetModel,
  streamActions,
  onStartSubmit,
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
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>("");
  const [isPickingWorkspace, setIsPickingWorkspace] = useState(false);
  const [modelSelection, setModelSelection] = useState({
    source: targetModel,
    value: targetModel ?? "",
  });
  const selectedModel =
    modelSelection.source === targetModel
      ? modelSelection.value
      : (targetModel ?? "");
  const effectiveSelectedModel = selectedModel || defaultModel;
  const selectedModelLabel =
    modelOptions.find((option) => option.value === effectiveSelectedModel)
      ?.label ?? effectiveSelectedModel;
  const selectedModelLocation =
    modelProviders[effectiveSelectedModel] === "ollama" ? "Local" : "Cloud";
  const [executionMode, setExecutionMode] = useState<"read_only" | "approval">(
    "read_only",
  );
  const localModels = sortModelOptions(
    modelOptions.filter((option) => modelProviders[option.value] === "ollama"),
  );
  const cloudModels = sortModelOptions(
    modelOptions.filter((option) => modelProviders[option.value] !== "ollama"),
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

  const { startRecording, stopRecording, isRecording, isProcessing } = useSTT();

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

      const toolMessages = ensureToolCallsHaveResponses(
        streamActions.getMessages(),
      );

      onStartSubmit();
      streamActions.submit(
        {
          messages: [...toolMessages, newHumanMessage],
          context: undefined,
          target_agent: selectedAgent,
          workspace: selectedWorkspace || undefined,
          model: effectiveSelectedModel || undefined,
          execution_mode: executionMode,
        },
        {
          streamMode: ["messages"],
          streamSubgraphs: true,
          streamResumable: true,
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
            workspace: selectedWorkspace || undefined,
            model: effectiveSelectedModel || undefined,
            execution_mode: executionMode,
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
    },
    [
      input,
      contentBlocks,
      isLoading,
      selectedAgent,
      selectedWorkspace,
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
    <div className="bg-background flex shrink-0 flex-col items-center px-4 pt-2">
      {!chatStarted && null}

      <div
        ref={dropRef}
        className={cn(
          "bg-muted relative z-10 mx-auto mb-4 w-full max-w-3xl rounded-2xl shadow-xs transition-all",
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
            className="field-sizing-content max-h-40 resize-none overflow-y-auto border-none bg-transparent p-3.5 pb-0 shadow-none ring-0 outline-none focus:ring-0 focus:outline-none"
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
              <button
                type="button"
                aria-label="Select repository folder"
                disabled={isPickingWorkspace}
                onClick={async () => {
                  setIsPickingWorkspace(true);
                  try {
                    const res = await fetch(
                      "http://127.0.0.1:8000/api/fs/pick-folder",
                    );
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    const data = await res.json();
                    if (!data.cancelled && data.path) {
                      setSelectedWorkspace(data.path);
                    }
                  } catch (error) {
                    console.error("[Repo picker] failed:", error);
                    toast.error("Could not open folder picker", {
                      description:
                        "Check that the sidecar is running and macOS allows Finder access.",
                    });
                  } finally {
                    setIsPickingWorkspace(false);
                  }
                }}
                className="flex cursor-pointer items-center gap-1.5 disabled:cursor-wait disabled:opacity-60"
              >
                {isPickingWorkspace ? (
                  <LoaderCircle className="size-4 animate-spin text-gray-600" />
                ) : (
                  <Folder className="size-4 text-gray-600" />
                )}
                <span className="text-xs text-gray-600">
                  {isPickingWorkspace
                    ? "Opening…"
                    : selectedWorkspace
                      ? selectedWorkspace
                          .replace(/\/+$/, "")
                          .split("/")
                          .pop() || selectedWorkspace
                      : "Repo selector"}
                </span>
              </button>
            </div>
            <div className="flex flex-col items-end gap-1.5">
              <div className="flex items-center gap-1">
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
              <div className="flex items-center gap-1">
                <span className="text-xs text-gray-600">Access</span>
                <Select
                  value={executionMode}
                  onValueChange={(value) =>
                    setExecutionMode(value as "read_only" | "approval")
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
                    <SelectItem value="approval">Ask to edit</SelectItem>
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
                          value={effectiveSelectedModel}
                          onValueChange={(value) =>
                            setModelSelection({ source: targetModel, value })
                          }
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
                          <SelectContent>
                            {localModels.length > 0 && (
                              <SelectGroup>
                                <SelectLabel>Local</SelectLabel>
                                {localModels.map((opt) => (
                                  <SelectItem
                                    key={opt.value}
                                    value={opt.value}
                                  >
                                    {opt.label}
                                  </SelectItem>
                                ))}
                              </SelectGroup>
                            )}
                            {cloudModels.length > 0 && (
                              <>
                                <SelectSeparator />
                                <SelectGroup>
                                  <SelectLabel>Cloud</SelectLabel>
                                  {cloudModels.map((opt) => (
                                    <SelectItem
                                      key={opt.value}
                                      value={opt.value}
                                    >
                                      {opt.label}
                                    </SelectItem>
                                  ))}
                                </SelectGroup>
                              </>
                            )}
                          </SelectContent>
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
              <div className="flex items-center gap-1">
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
                  title={
                    isRecording
                      ? "Recording... release to transcribe"
                      : "Hold to record"
                  }
                >
                  {isProcessing ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <Mic className="size-4" />
                  )}
                  <span className="text-xs">
                    {isRecording
                      ? "Recording..."
                      : isProcessing
                        ? "Transcribing..."
                        : "Voice"}
                  </span>
                </button>
                {isLoading ? (
                  <Button
                    key="stop"
                    onClick={streamActions.stop}
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
                      isLoading || (!input.trim() && contentBlocks.length === 0)
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
  );
}

export const ChatInput = memo(ChatInputImpl);
