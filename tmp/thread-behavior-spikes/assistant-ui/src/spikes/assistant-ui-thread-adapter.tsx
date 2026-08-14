"use client";
import type { PropsWithChildren } from "react";
import { Thread } from "@assistant-ui/react";

/** Isolated shell: lifecycle/message identity still belongs to the host adapter. */
export function AssistantUiThreadAdapter({ children }: PropsWithChildren) {
  return <Thread>{children}</Thread>;
}
