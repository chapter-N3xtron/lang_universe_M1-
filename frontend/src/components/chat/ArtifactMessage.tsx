"use client";

import * as React from "react";
import { AgentArtifact } from "@/components/agents-ui/agent-artifact";
import { AgentInquiry } from "@/components/agents-ui/agent-inquiry";

export type ArtifactBlock = {
  type: "code" | "document";
  language?: string;
  content: string;
};

export function extractArtifacts(content: string): {
  text: string;
  artifacts: ArtifactBlock[];
} {
  const artifacts: ArtifactBlock[] = [];
  const pattern = /```([\w+]*)?\n([\s\S]*?)```/g;
  let match;
  let lastIndex = 0;
  let text = "";

  while ((match = pattern.exec(content)) !== null) {
    text += content.slice(lastIndex, match.index);
    const language = match[1]?.trim() || "text";
    const code = match[2].trim();
    if (code) {
      artifacts.push({
        type: language === "markdown" || language === "txt" ? "document" : "code",
        language,
        content: code,
      });
    }
    lastIndex = match.index + match[0].length;
  }
  text += content.slice(lastIndex);
  return { text: text.trim(), artifacts };
}

export function ChatArtifact({
  content,
  language = "typescript",
}: {
  content: string;
  language?: string;
}) {
  return (
    <AgentArtifact
      title="Generated artifact"
      artifactType={language === "markdown" || language === "text" ? "document" : "code"}
      content={content}
      language={language}
      versions={[
        {
          id: "v1",
          label: "v1",
          timestamp: "now",
          content,
        },
      ]}
      currentVersion="v1"
    />
  );
}

export { AgentInquiry };
