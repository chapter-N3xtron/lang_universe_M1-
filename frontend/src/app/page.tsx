"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import {
  Send,
  Sparkles,
  Volume2,
  Mic,
  Square,
  Plus,
  PanelLeftClose,
  PanelLeft,
  Pencil,
  Check,
  X,
  FolderKanban,
  Bot,
  Microchip,
  Telescope,
  FolderSearch,
  HelpCircle,
  ChevronRight,
  Folder,
  FolderOpen,
  Cpu,
} from "lucide-react";
import { v4 as uuidv4 } from "uuid";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputActions,
  PromptInputAction,
} from "@/components/prompt-kit/prompt-input";
import {
  Message,
  MessageAvatar,
  MessageContent,
} from "@/components/prompt-kit/message";
import {
  AgentChatHistory,
  ChatSession,
  ChatThread,
  ChatMessage,
  AgentType,
  ThreadMode,
} from "@/components/agents-ui/agent-chat-history";
import {
  ChatArtifact,
  extractArtifacts,
  ArtifactBlock,
} from "@/components/chat/ArtifactMessage";
import { AgentInquiry, Inquiry } from "@/components/agents-ui/agent-inquiry";
import {
  sendChatMessage,
  synthesizeSpeech,
  transcribeAudio,
  getHomeDirectory,
  listDirectory,
  FSEntry,
  pickFolder,
  getAvailableModels,
  ModelInfo,
  createAgentJob,
  getAgentJob,
  listVoices,
  VoiceInfo,
} from "@/lib/api";
import { synthesizeSpeechStream } from "@/lib/tts-stream";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

const DEFAULT_WORKSPACE =
  "/Users/chaptercaptaingeneral/LangGraph_AgentChat_ui_Opencode_CLI";
const STORAGE_KEY = "langgraph-agent-chat-sessions";
const RECENT_WORKSPACES_KEY = "langgraph-recent-workspaces";

function loadRecentWorkspaces(): string[] {
  if (typeof window === "undefined") return [DEFAULT_WORKSPACE];
  try {
    const raw = localStorage.getItem(RECENT_WORKSPACES_KEY);
    const parsed = raw ? (JSON.parse(raw) as string[]) : [];
    return parsed.includes(DEFAULT_WORKSPACE)
      ? parsed
      : [DEFAULT_WORKSPACE, ...parsed];
  } catch {
    return [DEFAULT_WORKSPACE];
  }
}

function saveRecentWorkspace(path: string) {
  if (typeof window === "undefined") return;
  const current = loadRecentWorkspaces();
  const next = [path, ...current.filter((p) => p !== path)].slice(0, 10);
  localStorage.setItem(RECENT_WORKSPACES_KEY, JSON.stringify(next));
}

function repoName(path: string): string {
  return path.split("/").filter(Boolean).pop() || path;
}

function WorkspacePickerDialog({
  open,
  onOpenChange,
  current,
  onSelect,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  current: string;
  onSelect: (path: string) => void;
}) {
  const [entries, setEntries] = useState<FSEntry[]>([]);
  const [path, setPath] = useState(current);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (target: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await listDirectory(target);
      setPath(data.path);
      setEntries(data.entries.filter((e) => e.type === "dir"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load directory");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    load(current);
  }, [open, current, load]);

  const parent = useCallback(() => {
    const parts = path.split("/").filter(Boolean);
    if (parts.length <= 1) return;
    parts.pop();
    load("/" + parts.join("/"));
  }, [path, load]);

  const home = useCallback(async () => {
    const h = await getHomeDirectory();
    load(h);
  }, [load]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md bg-zinc-900 border-zinc-700 text-zinc-100">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-wide">
            Select repo
          </DialogTitle>
          <DialogDescription className="text-zinc-400">
            Navigate and click a folder to select it.
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2 text-xs font-mono text-zinc-300 mb-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={home}
            className="h-6 text-xs px-2 text-zinc-400 hover:bg-zinc-800"
          >
            Home
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={parent}
            disabled={path === "/"}
            className="h-6 text-xs px-2 text-zinc-400 hover:bg-zinc-800 disabled:opacity-30"
          >
            Up
          </Button>
          <span className="truncate flex-1">{path}</span>
        </div>

        {error && (
          <p className="text-xs text-red-400 mb-2">{error}</p>
        )}

        <div className="h-64 overflow-y-auto rounded-lg border border-zinc-700 bg-zinc-950">
          {loading ? (
            <div className="p-4 text-xs text-zinc-500">Loading…</div>
          ) : entries.length === 0 ? (
            <div className="p-4 text-xs text-zinc-500">No folders here</div>
          ) : (
            <div className="divide-y divide-zinc-800">
              {entries.map((entry) => (
                <button
                  key={entry.path}
                  onClick={() => load(entry.path)}
                  className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-zinc-300 hover:bg-zinc-800 transition-colors"
                >
                  <FolderOpen className="h-4 w-4 text-blue-400 shrink-0" />
                  <span className="truncate">{entry.name}</span>
                  <ChevronRight className="h-4 w-4 text-zinc-600 ml-auto shrink-0" />
                </button>
              ))}
            </div>
          )}
        </div>

        <DialogFooter className="flex flex-col-reverse sm:flex-row gap-2 sm:justify-end mt-2">
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            className="text-zinc-400 hover:bg-zinc-800"
          >
            Cancel
          </Button>
          <Button
            onClick={() => {
              onSelect(path);
              onOpenChange(false);
            }}
            className="bg-blue-600 hover:bg-blue-500 text-white"
          >
            Set repo
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const AGENT_OPTIONS: { value: AgentType; label: string; icon: React.ReactNode }[] =
  [
    { value: "jasper", label: "Jasper", icon: <Bot className="h-4 w-4" /> },
    {
      value: "opencode",
      label: "OpenCode",
      icon: <Microchip className="h-4 w-4" />,
    },
    {
      value: "uncensored-coder",
      label: "Uncensored Coder",
      icon: <Cpu className="h-4 w-4" />,
    },
    {
      value: "research",
      label: "Research",
      icon: <Telescope className="h-4 w-4" />,
    },
  ];

function makeWelcomeMessage(agent: AgentType): ChatMessage {
  const content =
    agent === "opencode"
      ? "Hi, I'm OpenCode. Point me at a workspace and ask me to edit, build, or explain code."
      : agent === "uncensored-coder"
        ? "Hi, I'm Uncensored Coder. I'll work on any coding, config, or creative automation task without filters."
        : agent === "research"
          ? "Hi, I'm Research. Ask me to gather sources, summarize topics, or dig into web data."
          : "Welcome! I'm Jasper, your general LangGraph assistant. What would you like to do?";

  return {
    id: uuidv4(),
    role: "assistant",
    content,
    agent,
    timestamp: new Date(),
  };
}

function generateTitle(messages: ChatMessage[]): string {
  const firstUser = messages.find((m) => m.role === "user");
  if (!firstUser) return "New chat";
  const text = firstUser.content.slice(0, 40);
  return text.length < firstUser.content.length ? text + "…" : text;
}

function createThread(
  agent: AgentType,
  opts: { workspace?: string; mode?: ThreadMode; model?: string } = {}
): ChatThread {
  const now = new Date();
  return {
    id: uuidv4(),
    threadId: uuidv4(),
    agent,
    workspace: opts.workspace,
    mode: opts.mode,
    model: opts.model,
    title: "New chat",
    messages: [makeWelcomeMessage(agent)],
    createdAt: now,
    updatedAt: now,
  };
}

function createSession(
  opts: {
    title?: string;
    activeThread?: ChatThread;
  } = {}
): ChatSession {
  const now = new Date();
  const thread = opts.activeThread ?? createThread("jasper");
  return {
    id: uuidv4(),
    title: opts.title ?? thread.title,
    activeThreadId: thread.id,
    threads: [thread],
    createdAt: now,
    updatedAt: now,
  };
}

function loadSessions(): ChatSession[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ChatSession[];
    return parsed.map((s) => ({
      ...s,
      createdAt: new Date(s.createdAt),
      updatedAt: new Date(s.updatedAt),
      threads: s.threads.map((t) => ({
        ...t,
        createdAt: new Date(t.createdAt),
        updatedAt: new Date(t.updatedAt),
        messages: t.messages.map((m) => ({
          ...m,
          timestamp: new Date(m.timestamp),
        })),
      })),
    }));
  } catch {
    return [];
  }
}

function saveSessions(sessions: ChatSession[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
}

export default function Home() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [selectedId, setSelectedId] = useState<string | undefined>();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [speakingIndex, setSpeakingIndex] = useState<number | null>(null);
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<string>("alba");
  const [recording, setRecording] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const [activeInquiry, setActiveInquiry] = useState<Inquiry | null>(null);
  const [inquiryHistory, setInquiryHistory] = useState<
    { question: string; answer: string; timestamp: string }[]
  >([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState("");
  const [pickingWorkspace, setPickingWorkspace] = useState(false);
  const [pendingJobs, setPendingJobs] = useState<
    { jobId: string; placeholderId: string }[]
  >([]);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chatContainerRef = useRef<HTMLDivElement | null>(null);
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    const loaded = loadSessions();
    if (loaded.length > 0) {
      setSessions(loaded);
      setSelectedId(loaded[0].id);
    } else {
      const first = createSession();
      setSessions([first]);
      setSelectedId(first.id);
      saveSessions([first]);
    }
  }, []);

  const scrollToBottom = useCallback(() => {
    const el = chatContainerRef.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, []);

  const activeSession = sessions.find((s) => s.id === selectedId);
  const activeThread = activeSession?.threads.find(
    (t) => t.id === activeSession.activeThreadId
  );

  const messages = activeThread?.messages ?? [];

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, activeInquiry, scrollToBottom]);

  const updateSession = useCallback(
    (updater: (session: ChatSession) => ChatSession) => {
      setSessions((prev) => {
        const next = prev.map((s) =>
          s.id === selectedId ? updater({ ...s }) : s
        );
        saveSessions(next);
        return next;
      });
    },
    [selectedId]
  );

  const updateActiveThread = useCallback(
    (updater: (thread: ChatThread) => ChatThread) => {
      updateSession((session) => {
        const now = new Date();
        const threads = session.threads.map((t) =>
          t.id === session.activeThreadId
            ? { ...updater({ ...t }), updatedAt: now }
            : t
        );
        return { ...session, threads, updatedAt: now };
      });
    },
    [updateSession]
  );

  const setActiveThreadId = useCallback(
    (threadId: string) => {
      updateSession((session) => ({
        ...session,
        activeThreadId: threadId,
        updatedAt: new Date(),
      }));
    },
    [updateSession]
  );

  const addAssistantMessage = useCallback(
    (content: string, agent: AgentType) => {
      updateActiveThread((thread) => ({
        ...thread,
        messages: [
          ...thread.messages,
          {
            id: uuidv4(),
            role: "assistant",
            content,
            agent,
            timestamp: new Date(),
          },
        ],
      }));
    },
    [updateActiveThread]
  );

  const detectInquiry = useCallback((response: string) => {
    const trimmed = response.trim();
    const isQuestion = /\?\s*$/.test(trimmed);
    const hasCode = /```/.test(trimmed);
    const hasOptions = /\n\s*(•|-|\d+\.)\s+/.test(trimmed);

    if (isQuestion && !hasCode) {
      let inquiryType: Inquiry["type"] = hasOptions ? "multipleChoice" : "text";
      const options: string[] = [];

      if (inquiryType === "multipleChoice") {
        const optionMatches = trimmed.matchAll(
          /\n\s*(?:•|-|\d+\.)\s+(.+)/g
        );
        for (const match of optionMatches) {
          options.push(match[1].trim().replace(/\?$/, ""));
        }
      }

      if (
        trimmed.toLowerCase().includes("yes or no") ||
        trimmed.toLowerCase().includes("would you like")
      ) {
        setActiveInquiry({
          id: uuidv4(),
          question: trimmed.replace(/\?\s*$/, ""),
          type: "confirmation",
        });
        return;
      }

      if (
        trimmed.toLowerCase().includes("rate") ||
        trimmed.toLowerCase().includes("how would you rate")
      ) {
        setActiveInquiry({
          id: uuidv4(),
          question: trimmed.replace(/\?\s*$/, ""),
          type: "scale",
        });
        return;
      }

      setActiveInquiry({
        id: uuidv4(),
        question: trimmed.replace(/\?\s*$/, ""),
        type: inquiryType,
        options: options.length > 0 ? options : undefined,
      });
    } else {
      setActiveInquiry(null);
    }
  }, []);

  const handleInquirySubmit = useCallback(
    (inquiryId: string, answer: string) => {
      setActiveInquiry(null);
      setInquiryHistory((prev) => [
        ...prev,
        {
          question: activeInquiry?.question ?? "",
          answer,
          timestamp: "now",
        },
      ]);
      setInput(answer);
      setTimeout(() => handleSubmitWithText(answer), 0);
    },
    [activeInquiry]
  );

  const handleInquirySkip = useCallback(() => {
    setActiveInquiry(null);
  }, []);

  const pollJobs = useCallback(async () => {
    if (pendingJobs.length === 0) return;
    for (const { jobId, placeholderId } of [...pendingJobs]) {
      try {
        const job = await getAgentJob(jobId);
        if (job.status === "completed" || job.status === "failed") {
          const content =
            job.status === "completed"
              ? job.result ?? "(no result)"
              : `Error: ${job.error ?? "Unknown error"}`;
          updateActiveThread((thread) => ({
            ...thread,
            messages: thread.messages.map((m) =>
              m.id === placeholderId
                ? { ...m, content, role: "assistant" as const }
                : m
            ),
          }));
          setPendingJobs((prev) => prev.filter((j) => j.jobId !== jobId));
        }
      } catch (err) {
        console.error("Job poll failed", err);
      }
    }
  }, [pendingJobs, updateActiveThread]);

  useEffect(() => {
    if (pendingJobs.length === 0) {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      return;
    }
    if (pollIntervalRef.current) return;
    pollIntervalRef.current = setInterval(pollJobs, 2000);
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [pendingJobs, pollJobs]);

  const handleSubmitWithText = useCallback(
    async (text: string) => {
      if (!text.trim() || loading || !activeSession || !activeThread) return;
      setInput("");
      setLoading(true);

      const now = new Date();
      const agent = activeThread.agent;

      // Ensure every thread has a durable backend thread id. The backend
      // checkpointer accumulates messages per thread_id, so we only need to
      // send the new user message; prior turns are loaded from server state.
      const threadId = activeThread.threadId || uuidv4();
      if (!activeThread.threadId) {
        updateActiveThread((thread) => ({ ...thread, threadId }));
      }

      updateActiveThread((thread) => {
        const messages = [
          ...thread.messages,
          {
            id: uuidv4(),
            role: "user" as const,
            content: text,
            agent,
            timestamp: now,
          },
        ];
        const title =
          thread.title === "New chat"
            ? generateTitle(messages)
            : thread.title;
        return { ...thread, title, messages };
      });

      try {
        const isAsync = activeThread.mode === "async";
        if (isAsync) {
          const { job_id } = await createAgentJob(
            text,
            [],
            activeThread.agent,
            activeThread.workspace,
            activeThread.model,
            threadId
          );
          const placeholderId = uuidv4();
          addAssistantMessage(
            `Async job started: ${job_id}\nPolling for results…`,
            agent
          );
          setPendingJobs((prev) => [
            ...prev,
            { jobId: job_id, placeholderId: prev.length > 0 ? prev[prev.length - 1].placeholderId : placeholderId },
          ]);
        } else {
          const response = await sendChatMessage(
            text,
            [],
            activeThread.agent,
            activeThread.workspace,
            activeThread.mode,
            activeThread.model,
            threadId
          );
          addAssistantMessage(response, agent);
          detectInquiry(response);
        }
      } catch (err) {
        addAssistantMessage(
          `Error: ${err instanceof Error ? err.message : "Something went wrong"}`,
          agent
        );
      } finally {
        setLoading(false);
      }
    },
    [activeSession, activeThread, loading, updateActiveThread, addAssistantMessage, detectInquiry]
  );

  const stopAudio = useCallback(() => {
    if (audioCtxRef.current) {
      audioCtxRef.current.close();
      audioCtxRef.current = null;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setSpeakingIndex(null);
  }, []);

  const playMessage = useCallback(
    async (content: string, index: number) => {
      stopAudio();
      setSpeakingIndex(index);
      try {
        const ctx = new AudioContext({ sampleRate: 24000 });
        audioCtxRef.current = ctx;
        let nextTime = ctx.currentTime;
        let lastEndTime = ctx.currentTime;

        for await (const chunk of synthesizeSpeechStream(content, selectedVoice)) {
          const bufLen = chunk.length;
          const buffer = ctx.createBuffer(1, bufLen, 24000);
          buffer.getChannelData(0).set(chunk);
          const source = ctx.createBufferSource();
          source.buffer = buffer;
          source.connect(ctx.destination);
          const startTime = Math.max(ctx.currentTime, nextTime);
          source.start(startTime);
          lastEndTime = startTime + bufLen / 24000;
          nextTime = lastEndTime;
        }

        await new Promise<void>((resolve) => {
          const check = () => {
            if (ctx.currentTime >= lastEndTime) {
              ctx.close();
              audioCtxRef.current = null;
              setSpeakingIndex(null);
              resolve();
            } else {
              setTimeout(check, 100);
            }
          };
          check();
        });
      } catch (err) {
        console.error("TTS failed", err);
        setSpeakingIndex(null);
      }
    },
    [stopAudio, selectedVoice]
  );

  const stopRecording = useCallback(() => {
    try {
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.stop();
      }
    } catch {
      // ignore
    }
    recorderRef.current = null;
    setRecording(false);
  }, []);

  const startRecording = useCallback(async () => {
    setMicError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm",
      });
      const chunks: Blob[] = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(chunks, { type: "audio/webm" });
        try {
          const transcript = await transcribeAudio(blob);
          setInput((prev) => (prev ? prev + " " + transcript : transcript));
        } catch (err) {
          console.error("STT failed", err);
          setMicError("Voice transcription failed. Try again.");
        } finally {
          setRecording(false);
        }
      };

      mediaRecorder.onerror = (e) => {
        console.error("MediaRecorder error", e);
        setMicError("Microphone recording failed. Check permissions.");
        stream.getTracks().forEach((track) => track.stop());
        setRecording(false);
      };

      mediaRecorder.start();
      recorderRef.current = mediaRecorder;
      setRecording(true);
    } catch (err) {
      console.error("Microphone access denied", err);
      setMicError("Microphone access denied. Check browser permissions.");
      setRecording(false);
    }
  }, []);

  const handleNewChat = useCallback(() => {
    stopAudio();
    const session = createSession();
    setSessions((prev) => {
      const next = [session, ...prev];
      saveSessions(next);
      return next;
    });
    setSelectedId(session.id);
    setInput("");
  }, [stopAudio]);

  const handleAgentChange = useCallback(
    (agent: AgentType) => {
      if (!activeSession || !activeThread) return;
      stopAudio();

      updateSession((session) => {
        const now = new Date();
        const existing = session.threads.find((t) => t.agent === agent);
        if (existing) {
          return {
            ...session,
            activeThreadId: existing.id,
            updatedAt: now,
          };
        }
        const workspace =
          agent === "opencode" || agent === "uncensored-coder"
            ? DEFAULT_WORKSPACE
            : undefined;
        const mode: ThreadMode | undefined =
          agent === "opencode" ? "live" : agent === "uncensored-coder" ? "async" : undefined;
        const model = activeThread?.model;
        const newThread = createThread(agent, { workspace, mode, model });
        return {
          ...session,
          activeThreadId: newThread.id,
          threads: [...session.threads, newThread],
          updatedAt: now,
        };
      });
    },
    [activeSession, activeThread, updateSession, stopAudio]
  );

  const handleNewThread = useCallback(() => {
    if (!activeSession || !activeThread) return;
    stopAudio();
    const agent = activeThread.agent;
    updateSession((session) => {
      const now = new Date();
      const newThread = createThread(agent, {
        workspace: activeThread.workspace,
        mode: activeThread.mode,
        model: activeThread.model,
      });
      return {
        ...session,
        activeThreadId: newThread.id,
        threads: [...session.threads, newThread],
        updatedAt: now,
      };
    });
  }, [activeSession, activeThread, updateSession, stopAudio]);

  const handleWorkspaceChange = useCallback(
    (newWorkspace: string) => {
      if (!activeThread) return;
      updateActiveThread((thread) => ({
        ...thread,
        workspace: newWorkspace,
      }));
      saveRecentWorkspace(newWorkspace);
    },
    [activeThread, updateActiveThread]
  );

  const handlePickWorkspace = useCallback(async () => {
    if (!activeThread) return;
    try {
      const result = await pickFolder(activeThread.workspace ?? DEFAULT_WORKSPACE);
      if (!result.cancelled && result.path) {
        handleWorkspaceChange(result.path);
      }
    } catch (err) {
      console.error("Folder picker failed", err);
      setPickingWorkspace(true);
    }
  }, [activeThread, handleWorkspaceChange]);

  const handleModeChange = useCallback(
    (mode: ThreadMode) => {
      if (!activeThread) return;
      updateActiveThread((thread) => ({ ...thread, mode }));
    },
    [activeThread, updateActiveThread]
  );

  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [defaultModel, setDefaultModel] = useState<string>("");

  const refreshModels = useCallback(() => {
    getAvailableModels()
      .then((data) => {
        setAvailableModels(data.models);
        setDefaultModel(data.default);
      })
      .catch((err) => console.error("Failed to load models", err));
  }, []);

  useEffect(() => {
    refreshModels();
  }, [refreshModels]);

  useEffect(() => {
    listVoices()
      .then(setVoices)
      .catch((err) => console.error("Failed to load voices", err));
  }, []);

  // Refetch available models when the user opens the model selector
  const handleModelSelectOpen = useCallback(() => {
    refreshModels();
  }, [refreshModels]);

  const handleModelChange = useCallback(
    (modelId: string) => {
      if (!activeThread) return;
      updateActiveThread((thread) => ({ ...thread, model: modelId }));
    },
    [activeThread, updateActiveThread]
  );

  const activeModel = activeThread?.model ?? defaultModel;

  const handleThreadTitleChange = useCallback(
    (newTitle: string) => {
      if (!activeThread) return;
      updateActiveThread((thread) => ({ ...thread, title: newTitle }));
    },
    [activeThread, updateActiveThread]
  );

  const handleSubmit = async () => {
    await handleSubmitWithText(input);
  };

  const handleDeleteSession = useCallback((id: string) => {
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id);
      saveSessions(next);
      if (selectedId === id) {
        setSelectedId(next[0]?.id);
      }
      return next;
    });
  }, [selectedId]);

  const handleStarSession = useCallback((id: string) => {
    setSessions((prev) => {
      const next = prev.map((s) =>
        s.id === id ? { ...s, starred: !s.starred } : s
      );
      saveSessions(next);
      return next;
    });
  }, []);

  const handleArchiveSession = useCallback((id: string) => {
    setSessions((prev) => {
      const next = prev.map((s) =>
        s.id === id ? { ...s, archived: !s.archived } : s
      );
      saveSessions(next);
      return next;
    });
  }, []);

  const handleExportSession = useCallback((id: string) => {
    const session = sessions.find((s) => s.id === id);
    if (!session) return;
    const data = session.threads
      .flatMap((t) => t.messages)
      .map((m) => `## ${m.role} (${m.agent})\n\n${m.content}`)
      .join("\n\n---\n\n");
    const blob = new Blob([data], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${session.title.replace(/[^a-z0-9]/gi, "_").toLowerCase()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [sessions]);

  const handleRenameSession = useCallback((id: string, newTitle: string) => {
    setSessions((prev) => {
      const next = prev.map((s) =>
        s.id === id ? { ...s, title: newTitle } : s
      );
      saveSessions(next);
      return next;
    });
  }, []);

  const startTitleEdit = useCallback(() => {
    if (!activeThread) return;
    setTitleInput(activeThread.title);
    setEditingTitle(true);
  }, [activeThread]);

  const cancelTitleEdit = useCallback(() => {
    setEditingTitle(false);
    setTitleInput("");
  }, []);

  const confirmTitleEdit = useCallback(() => {
    if (!activeThread || !titleInput.trim()) {
      cancelTitleEdit();
      return;
    }
    handleThreadTitleChange(titleInput.trim());
    setEditingTitle(false);
    setTitleInput("");
  }, [activeThread, titleInput, handleThreadTitleChange]);

  const agentLabel =
    AGENT_OPTIONS.find((a) => a.value === activeThread?.agent)?.label ??
    "Agent";

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100 font-mono">
      {/* Sidebar */}
      <aside
        className={cn(
          "flex flex-col border-r border-zinc-800 bg-zinc-900 transition-all duration-300 ease-in-out overflow-hidden",
          sidebarOpen ? "w-80" : "w-0"
        )}
      >
        <div className="flex min-w-[20rem] items-center justify-between border-b border-zinc-800 px-4 py-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-blue-500" />
            <span className="font-heading text-sm">Chat History</span>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => handleNewChat()}
            className="h-8 gap-1 text-xs"
          >
            <Plus className="h-4 w-4" /> New
          </Button>
        </div>
        <div className="min-w-[20rem] flex-1 overflow-hidden">
          <AgentChatHistory
            sessions={sessions}
            selectedSessionId={selectedId}
            showPreview={false}
            onSelectSession={(session) => {
              stopAudio();
              setSelectedId(session.id);
            }}
            onDeleteSession={handleDeleteSession}
            onStarSession={handleStarSession}
            onArchiveSession={handleArchiveSession}
            onExportSession={handleExportSession}
            onRenameSession={handleRenameSession}
          />
        </div>
      </aside>

      {/* Main chat */}
      <div className="flex flex-1 flex-col">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-zinc-800 bg-zinc-900 px-6 py-4 gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <Button
              size="icon"
              variant="ghost"
              onClick={() => setSidebarOpen((v) => !v)}
              className="h-8 w-8 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
              aria-label={sidebarOpen ? "Collapse sidebar" : "Open sidebar"}
            >
              {sidebarOpen ? (
                <PanelLeftClose className="h-5 w-5" />
              ) : (
                <PanelLeft className="h-5 w-5" />
              )}
            </Button>

            <div className="flex items-center gap-2 min-w-0">
              {editingTitle ? (
                <>
                  <Input
                    value={titleInput}
                    onChange={(e) => setTitleInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") confirmTitleEdit();
                      if (e.key === "Escape") cancelTitleEdit();
                    }}
                    autoFocus
                    className="h-7 rounded bg-zinc-800 px-2 text-sm text-zinc-100 outline-none ring-1 ring-zinc-700 focus:ring-blue-500 border-none"
                  />
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={confirmTitleEdit}
                    className="h-7 w-7 text-emerald-400 hover:bg-zinc-800"
                  >
                    <Check className="h-4 w-4" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={cancelTitleEdit}
                    className="h-7 w-7 text-red-400 hover:bg-zinc-800"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </>
              ) : (
                <>
                  <h1 className="font-heading text-lg tracking-wide text-zinc-100 truncate">
                    {activeThread?.title ?? activeSession?.title ?? "LangGraph Agent Chat"}
                  </h1>
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={startTitleEdit}
                    className="h-6 w-6 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200"
                  >
                    <Pencil className="h-3 w-3" />
                  </Button>
                </>
              )}
              <p className="text-xs text-zinc-400 whitespace-nowrap">
                {agentLabel}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <Button
              size="sm"
              variant="ghost"
              onClick={handleNewThread}
              className="h-8 gap-1 text-xs text-zinc-300 hover:bg-zinc-800"
            >
              <Plus className="h-4 w-4" /> Thread
            </Button>
            <div className="flex gap-2">
              <span className="rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs text-blue-400">
                OpenCode CLI
              </span>
              <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-400">
                Research
              </span>
            </div>
          </div>
        </header>

        {/* Messages */}
        <main ref={chatContainerRef} className="flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto flex max-w-3xl flex-col gap-6">
            {messages.map((msg, idx) => (
              <Message
                key={msg.id}
                className={cn(
                  "flex gap-3",
                  msg.role === "user" && "flex-row-reverse"
                )}
              >
                <MessageAvatar
                  src=""
                  alt={msg.role}
                  fallback={msg.role === "user" ? "U" : msg.agent[0].toUpperCase()}
                  className={cn(
                    "h-8 w-8",
                    msg.role === "user" ? "bg-emerald-600" : "bg-blue-600"
                  )}
                />
                <div className="flex max-w-[85%] flex-col gap-1 w-full">
                  {msg.role === "assistant" ? (
                    (() => {
                      const { text, artifacts } = extractArtifacts(msg.content);
                      return (
                        <>
                          {text && (
                            <MessageContent
                              markdown
                              className="rounded-2xl px-4 py-3 text-sm bg-zinc-900 text-zinc-100 font-mono"
                            >
                              {text}
                            </MessageContent>
                          )}
                          {artifacts.map(
                            (artifact: ArtifactBlock, aidx: number) => (
                              <div key={aidx} className="mt-2">
                                <ChatArtifact
                                  content={artifact.content}
                                  language={artifact.language}
                                />
                              </div>
                            )
                          )}
                          <div className="flex justify-start">
                            <button
                              onClick={() =>
                                speakingIndex === idx
                                  ? stopAudio()
                                  : playMessage(msg.content, idx)
                              }
                              className={cn(
                                "flex items-center gap-1 rounded-full px-2 py-1 text-xs transition-colors",
                                speakingIndex === idx
                                  ? "bg-blue-600 text-white"
                                  : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                              )}
                              aria-label={
                                speakingIndex === idx
                                  ? "Stop speaking"
                                  : "Read aloud"
                              }
                            >
                              {speakingIndex === idx ? (
                                <>
                                  <Square className="h-3 w-3" /> Stop
                                </>
                              ) : (
                                <>
                                  <Volume2 className="h-3 w-3" /> Read aloud
                                </>
                              )}
                            </button>
                          </div>
                        </>
                      );
                    })()
                  ) : (
                    <MessageContent
                      markdown
                      className={cn(
                        "rounded-2xl px-4 py-3 text-sm font-mono",
                        msg.role === "user"
                          ? "bg-emerald-600 text-white"
                          : "bg-zinc-900 text-zinc-100"
                      )}
                    >
                      {msg.content}
                    </MessageContent>
                  )}
                </div>
              </Message>
            ))}
            {loading && (
              <Message className="flex gap-3">
                <MessageAvatar
                  src=""
                  alt="assistant"
                  fallback="A"
                  className="h-8 w-8 bg-blue-600"
                />
                <MessageContent className="bg-zinc-900 text-zinc-400 text-sm px-4 py-3 rounded-2xl">
                  Agent is thinking…
                </MessageContent>
              </Message>
            )}
            {activeInquiry && !loading && (
              <div className="max-w-3xl">
                <AgentInquiry
                  agentName={agentLabel}
                  taskContext={activeThread?.title ?? "Clarification"}
                  inquiry={activeInquiry}
                  inquiryHistory={inquiryHistory}
                  onSubmit={handleInquirySubmit}
                  onSkip={handleInquirySkip}
                />
              </div>
            )}
          </div>
        </main>

        {/* Input */}
        <footer className="border-t border-zinc-800 bg-zinc-900 px-4 py-4">
          <div className="mx-auto max-w-3xl">
            {/* Two-tier toolbar above input */}
            <div className="flex items-start justify-between gap-3 mb-2">
              {/* Left column: model on top, agent below */}
              <div className="flex flex-col gap-2">
                {availableModels.length > 0 && (
                <Select
                  value={activeModel}
                  onValueChange={(v) => handleModelChange(v ?? defaultModel)}
                  onOpenChange={(open) => open && handleModelSelectOpen()}
                >
                    <SelectTrigger className="w-56 border-zinc-700 bg-zinc-800/50 text-zinc-100 h-8 text-xs">
                      <span className="flex items-center gap-2 overflow-hidden">
                        <Cpu className="h-3.5 w-3.5 text-zinc-400 shrink-0" />
                        <span className="truncate font-mono">{
                          activeModel.replace(/^ollama\//, "").replace(/^ollama-cloud\//, "") || activeModel
                        }</span>
                      </span>
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-900 border-zinc-700 text-zinc-100 max-w-sm">
                      {availableModels.map((m) => (
                        <SelectItem
                          key={m.id}
                          value={m.id}
                          className="focus:bg-zinc-800 focus:text-zinc-100 font-mono"
                          title={m.id}
                        >
                          <span className="flex items-center gap-2 truncate">
                            <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-heading">
                              {m.provider}
                            </span>
                            <span className="truncate">{m.name}</span>
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}

                <Select
                  value={activeThread?.agent ?? "jasper"}
                  onValueChange={(v) => handleAgentChange(v as AgentType)}
                >
                  <SelectTrigger className="w-40 border-zinc-700 bg-zinc-800/50 text-zinc-100 h-8 text-xs">
                    <SelectValue placeholder="Select agent" />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-700 text-zinc-100">
                    {AGENT_OPTIONS.map((opt) => (
                      <SelectItem
                        key={opt.value}
                        value={opt.value}
                        className="focus:bg-zinc-800 focus:text-zinc-100"
                      >
                        <span className="flex items-center gap-2">
                          {opt.icon}
                          {opt.label}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                {voices.length > 0 && (
                <Select
                  value={selectedVoice}
                  onValueChange={(v) => v && setSelectedVoice(v)}
                >
                  <SelectTrigger className="w-40 border-zinc-700 bg-zinc-800/50 text-zinc-100 h-8 text-xs">
                    <span className="flex items-center gap-2 overflow-hidden">
                      <Volume2 className="h-3.5 w-3.5 text-zinc-400 shrink-0" />
                      <span className="truncate">{voices.find(v => v.id === selectedVoice)?.name ?? selectedVoice}</span>
                    </span>
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-900 border-zinc-700 text-zinc-100 max-h-60">
                    {voices.map((v) => (
                      <SelectItem
                        key={v.id}
                        value={v.id}
                        className="focus:bg-zinc-800 focus:text-zinc-100"
                      >
                        <span className="flex items-center gap-2">
                          <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-heading">
                            {v.category}
                          </span>
                          <span>{v.name}</span>
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                )}
              </div>

              {/* Right column: repo picker and live/async switch */}
              {(activeThread?.agent === "opencode" ||
                activeThread?.agent === "uncensored-coder") && (
                <div className="flex flex-col items-end gap-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handlePickWorkspace()}
                    className="h-8 gap-1.5 text-xs text-zinc-300 hover:bg-zinc-800 px-2"
                    title="Choose repo"
                  >
                    <FolderSearch className="h-4 w-4 text-zinc-400" />
                    <span className="max-w-[24rem] truncate font-heading tracking-wide">
                      {repoName(activeThread?.workspace ?? DEFAULT_WORKSPACE)}
                    </span>
                  </Button>

                  <div className="flex items-center gap-2 rounded-lg bg-zinc-800/50 px-2 py-1 border border-zinc-700">
                    <Switch
                      id="mode-switch"
                      checked={activeThread?.mode === "async"}
                      onCheckedChange={(checked) =>
                        handleModeChange(checked ? "async" : "live")
                      }
                      className="data-[state=checked]:bg-blue-600"
                    />
                    <label
                      htmlFor="mode-switch"
                      className="text-xs text-zinc-300 cursor-pointer select-none"
                      title="Live: ask for permission. Async: run in background and report back."
                    >
                      {activeThread?.mode === "async" ? "Async" : "Live"}
                    </label>
                    <span title="Live: ask for permission. Async: run in background and report back.">
                      <HelpCircle className="h-3 w-3 text-zinc-500" />
                    </span>
                  </div>
                </div>
              )}
            </div>

            <WorkspacePickerDialog
              open={pickingWorkspace}
              onOpenChange={setPickingWorkspace}
              current={activeThread?.workspace ?? DEFAULT_WORKSPACE}
              onSelect={handleWorkspaceChange}
            />

            <PromptInput
              value={input}
              onValueChange={setInput}
              isLoading={loading}
              onSubmit={handleSubmit}
              className="bg-zinc-950 border-zinc-800"
            >
              <PromptInputTextarea
                placeholder={`Message ${agentLabel}…`}
                className="text-zinc-100 placeholder:text-zinc-500 font-mono"
                disabled={loading}
              />
              <PromptInputActions className="justify-between">
                <div className="flex items-center gap-2">
                  <PromptInputAction
                    tooltip={recording ? "Stop recording" : "Voice input"}
                  >
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={recording ? stopRecording : startRecording}
                      className={cn(
                        "rounded-full",
                        recording
                          ? "bg-red-600 text-white hover:bg-red-500"
                          : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                      )}
                    >
                      {recording ? (
                        <Square className="h-4 w-4" />
                      ) : (
                        <Mic className="h-4 w-4" />
                      )}
                    </Button>
                  </PromptInputAction>
                  {recording && (
                    <span className="text-xs text-red-400 animate-pulse">
                      Listening…
                    </span>
                  )}
                </div>

                <PromptInputAction tooltip="Send message">
                  <Button
                    size="icon"
                    onClick={handleSubmit}
                    disabled={loading || !input.trim()}
                    className="rounded-full bg-blue-600 hover:bg-blue-500"
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                </PromptInputAction>
              </PromptInputActions>
            </PromptInput>
            {micError && (
              <p className="mt-2 text-center text-xs text-red-400">{micError}</p>
            )}
            <p className="mt-2 text-center text-xs text-zinc-500 font-heading tracking-wider">
              POWERED BY LANGGRAPH · OLLAMA CLOUD · AGENTS-UI-KIT
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
}
