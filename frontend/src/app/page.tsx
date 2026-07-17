"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Send, Sparkles, Volume2, Mic, Square, Plus, PanelLeftClose, PanelLeft, Pencil, Check, X, FolderKanban } from "lucide-react";
import { v4 as uuidv4 } from "uuid";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
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
  ChatMessage,
} from "@/lib/api";

const WELCOME_MESSAGE: ChatMessage = {
  role: "assistant",
  content:
    "Welcome! I'm your LangGraph assistant. I can help with coding tasks (via OpenCode CLI) or research (via Firecrawl). What would you like to do?",
};

const STORAGE_KEY = "langgraph-agent-chat-sessions";
const DEFAULT_WORKSPACE = "/Users/chaptercaptaingeneral/LangGraph_AgentChat_ui_Opencode_CLI";

function generateTitle(messages: ChatMessage[]): string {
  const firstUser = messages.find((m) => m.role === "user");
  if (!firstUser) return "New chat";
  const text = firstUser.content.slice(0, 40);
  return text.length < firstUser.content.length ? text + "…" : text;
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
      messages: s.messages.map((m) => ({
        ...m,
        timestamp: new Date(m.timestamp),
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

function createSession(messages: ChatMessage[] = [WELCOME_MESSAGE], workspace = DEFAULT_WORKSPACE): ChatSession {
  const now = new Date();
  return {
    id: uuidv4(),
    title: generateTitle(messages),
    workspace,
    messages: messages.map((m) => ({
      id: uuidv4(),
      role: m.role,
      content: m.content,
      timestamp: now,
    })),
    createdAt: now,
    updatedAt: now,
  };
}

export default function Home() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [selectedId, setSelectedId] = useState<string | undefined>();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [speakingIndex, setSpeakingIndex] = useState<number | null>(null);
  const [recording, setRecording] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const [activeInquiry, setActiveInquiry] = useState<Inquiry | null>(null);
  const [inquiryHistory, setInquiryHistory] = useState<{ question: string; answer: string; timestamp: string }[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
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

  const activeSession = sessions.find((s) => s.id === selectedId);

  const updateActiveSession = useCallback(
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

  const addAssistantMessage = useCallback(
    (content: string) => {
      updateActiveSession((session) => ({
        ...session,
        messages: [
          ...session.messages,
          {
            id: uuidv4(),
            role: "assistant",
            content,
            timestamp: new Date(),
          },
        ],
        updatedAt: new Date(),
      }));
    },
    [updateActiveSession]
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
        const optionMatches = trimmed.matchAll(/\n\s*(?:•|-|\d+\.)\s+(.+)/g);
        for (const match of optionMatches) {
          options.push(match[1].trim().replace(/\?$/, ""));
        }
      }

      if (trimmed.toLowerCase().includes("yes or no") || trimmed.toLowerCase().includes("would you like")) {
        setActiveInquiry({
          id: uuidv4(),
          question: trimmed.replace(/\?\s*$/, ""),
          type: "confirmation",
        });
        return;
      }

      if (trimmed.toLowerCase().includes("rate") || trimmed.toLowerCase().includes("how would you rate")) {
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

  const handleSubmitWithText = useCallback(
    async (text: string) => {
      if (!text.trim() || loading || !activeSession) return;
      setInput("");
      setLoading(true);

      const now = new Date();
      const userHistory: ChatMessage[] = activeSession.messages.map((m) => ({
        role: m.role as "user" | "assistant",
        content: m.content,
      }));

      updateActiveSession((session) => ({
        ...session,
        title:
          session.title === "New chat"
            ? generateTitle([{ role: "user", content: text }])
            : session.title,
        messages: [
          ...session.messages,
          { id: uuidv4(), role: "user", content: text, timestamp: now },
        ],
        updatedAt: now,
      }));

      try {
        const response = await sendChatMessage(text, userHistory, activeSession.workspace);
        addAssistantMessage(response);
        detectInquiry(response);
      } catch (err) {
        addAssistantMessage(
          `Error: ${err instanceof Error ? err.message : "Something went wrong"}`
        );
      } finally {
        setLoading(false);
      }
    },
    [activeSession, loading, updateActiveSession, addAssistantMessage, detectInquiry]
  );

  const stopAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setSpeakingIndex(null);
  }, []);

  const playMessage = useCallback(async (content: string, index: number) => {
    stopAudio();
    try {
      const blob = await synthesizeSpeech(content);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      setSpeakingIndex(index);
      audio.onended = () => {
        URL.revokeObjectURL(url);
        setSpeakingIndex(null);
        audioRef.current = null;
      };
      await audio.play();
    } catch (err) {
      console.error("TTS failed", err);
      setSpeakingIndex(null);
    }
  }, [stopAudio]);

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
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
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

  const handleNewChat = useCallback((workspace = DEFAULT_WORKSPACE) => {
    stopAudio();
    const session = createSession(undefined, workspace);
    setSessions((prev) => {
      const next = [session, ...prev];
      saveSessions(next);
      return next;
    });
    setSelectedId(session.id);
    setInput("");
  }, [stopAudio]);

  const handleWorkspaceChange = useCallback((newWorkspace: string) => {
    if (!activeSession) return;
    updateActiveSession((session) => ({
      ...session,
      workspace: newWorkspace,
    }));
  }, [activeSession, updateActiveSession]);

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
    const data = session.messages
      .map((m) => `## ${m.role}\n\n${m.content}`)
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
    if (!activeSession) return;
    setTitleInput(activeSession.title);
    setEditingTitle(true);
  }, [activeSession]);

  const cancelTitleEdit = useCallback(() => {
    setEditingTitle(false);
    setTitleInput("");
  }, []);

  const confirmTitleEdit = useCallback(() => {
    if (!activeSession || !titleInput.trim()) {
      cancelTitleEdit();
      return;
    }
    handleRenameSession(activeSession.id, titleInput.trim());
    setEditingTitle(false);
    setTitleInput("");
  }, [activeSession, titleInput, handleRenameSession]);

  const messages = activeSession?.messages ?? [];

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
          <Button size="sm" variant="ghost" onClick={() => handleNewChat()} className="h-8 gap-1 text-xs">
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
        <header className="flex items-center justify-between border-b border-zinc-800 bg-zinc-900 px-6 py-4">
          <div className="flex items-center gap-3">
            <Button
              size="icon"
              variant="ghost"
              onClick={() => setSidebarOpen((v) => !v)}
              className="h-8 w-8 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
              aria-label={sidebarOpen ? "Collapse sidebar" : "Open sidebar"}
            >
              {sidebarOpen ? <PanelLeftClose className="h-5 w-5" /> : <PanelLeft className="h-5 w-5" />}
            </Button>
            <div className="flex items-center gap-2">
              {editingTitle ? (
                <>
                  <input
                    value={titleInput}
                    onChange={(e) => setTitleInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") confirmTitleEdit();
                      if (e.key === "Escape") cancelTitleEdit();
                    }}
                    autoFocus
                    className="h-7 rounded bg-zinc-800 px-2 text-sm text-zinc-100 outline-none ring-1 ring-zinc-700 focus:ring-blue-500"
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
                  <h1 className="font-heading text-lg tracking-wide text-zinc-100">{activeSession?.title ?? "LangGraph Agent Chat"}</h1>
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
              <p className="text-xs text-zinc-400">OpenCode CLI · Research Agent</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 rounded-lg bg-zinc-800/50 px-3 py-1.5 border border-zinc-700">
              <FolderKanban className="h-4 w-4 text-zinc-400" />
              <input
                value={activeSession?.workspace ?? DEFAULT_WORKSPACE}
                onChange={(e) => handleWorkspaceChange(e.target.value)}
                className="bg-transparent text-xs text-zinc-200 w-64 outline-none font-mono"
                title="Workspace path for OpenCode CLI"
              />
            </div>
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
        <main className="flex-1 overflow-y-auto px-4 py-6">
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
                  fallback={msg.role === "user" ? "U" : "A"}
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
                          {artifacts.map((artifact: ArtifactBlock, aidx: number) => (
                            <div key={aidx} className="mt-2">
                              <ChatArtifact
                                content={artifact.content}
                                language={artifact.language}
                              />
                            </div>
                          ))}
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
                                speakingIndex === idx ? "Stop speaking" : "Read aloud"
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
                  agentName="OpenCode CLI"
                  taskContext={activeSession?.title ?? "Clarification"}
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
            <PromptInput
              value={input}
              onValueChange={setInput}
              isLoading={loading}
              onSubmit={handleSubmit}
              className="bg-zinc-950 border-zinc-800"
            >
              <PromptInputTextarea
                placeholder="Type your message…"
                className="text-zinc-100 placeholder:text-zinc-500 font-mono"
                disabled={loading}
              />
              <PromptInputActions className="justify-between">
                <div className="flex items-center gap-2">
                  <PromptInputAction tooltip={recording ? "Stop recording" : "Voice input"}>
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
                      {recording ? <Square className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
                    </Button>
                  </PromptInputAction>
                  {recording && (
                    <span className="text-xs text-red-400 animate-pulse">Listening…</span>
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
              <p className="mt-2 text-center text-xs text-red-400">
                {micError}
              </p>
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
