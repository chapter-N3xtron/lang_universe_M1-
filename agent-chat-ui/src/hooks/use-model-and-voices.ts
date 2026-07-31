"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";

interface ModelOption {
  value: string;
  label: string;
}

export function useModelAndVoices() {
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([]);
  const [modelProviders, setModelProviders] = useState<Record<string, string>>(
    {},
  );
  const [defaultModel, setDefaultModel] = useState<string>("");
  const [modelsLoadError, setModelsLoadError] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string>("");

  const [voiceOptions, setVoiceOptions] = useState<
    { id: string; name: string }[]
  >([]);
  const [voicesLoadError, setVoicesLoadError] = useState(false);
  const [selectedVoice, setSelectedVoice] = useState<string>("");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/api/models")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(
        (data: {
          default: string;
          models: { id: string; name: string; provider: string }[];
        }) => {
          setDefaultModel(data.default);
          const providers: Record<string, string> = {};
          const options: ModelOption[] = [];
          for (const m of data.models) {
            options.push({ value: m.id, label: m.name });
            providers[m.id] = m.provider;
          }
          setModelOptions(options);
          setModelProviders(providers);
        },
      )
      .catch((err) => {
        setModelsLoadError(true);
        toast.error("Could not load models", {
          description:
            "Model sidecar at http://127.0.0.1:8000 may not be running.",
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
          name: v
            .replace(/_/g, " ")
            .replace(/\b\w/g, (l: string) => l.toUpperCase()),
        }));
        setVoiceOptions(options);
      })
      .catch((err) => {
        setVoicesLoadError(true);
        toast.error("Could not load voices", {
          description:
            "TTS sidecar at http://127.0.0.1:8000 may not be running.",
        });
        console.error("[Voices] failed to load:", err);
      });
  }, []);

  return {
    modelOptions,
    modelProviders,
    defaultModel,
    modelsLoadError,
    selectedModel,
    setSelectedModel,
    voiceOptions,
    voicesLoadError,
    selectedVoice,
    setSelectedVoice,
  };
}
