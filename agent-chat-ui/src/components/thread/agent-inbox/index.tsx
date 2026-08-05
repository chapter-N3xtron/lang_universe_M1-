import { useEffect, useMemo, useState } from "react";
import { Interrupt } from "@langchain/langgraph-sdk";
import { cn } from "@/lib/utils";
import { useStreamContext } from "@/providers/Stream";
import { HITLRequest } from "./types";
import { StateView } from "./components/state-view";
import { ThreadActionsView } from "./components/thread-actions-view";

interface ThreadViewProps {
  interrupt: Interrupt<HITLRequest> | Interrupt<HITLRequest>[];
}

export function ThreadView({ interrupt }: ThreadViewProps) {
  const thread = useStreamContext();
  const interrupts = useMemo(
    () =>
      (Array.isArray(interrupt) ? interrupt : [interrupt]).filter(
        (item): item is Interrupt<HITLRequest> => !!item,
      ),
    [interrupt],
  );
  const [activeInterruptIndex, setActiveInterruptIndex] = useState(0);
  const [showDescription, setShowDescription] = useState(false);
  const [showState, setShowState] = useState(false);
  const showSidePanel = showDescription || showState;

  useEffect(() => {
    setActiveInterruptIndex(0);
  }, [interrupts.length]);

  const activeInterrupt = interrupts[activeInterruptIndex];
  const activeDescription =
    activeInterrupt?.value?.action_requests?.[0]?.description ?? "";
  const activeInterruptKey = activeInterrupt
    ? `${activeInterrupt.id ?? "interrupt"}:${JSON.stringify(activeInterrupt.value)}`
    : "interrupt";

  const handleShowSidePanel = (
    showStateFlag: boolean,
    showDescriptionFlag: boolean,
  ) => {
    if (showStateFlag && showDescriptionFlag) {
      console.error("Cannot show both state and description");
      return;
    }
    if (showStateFlag) {
      setShowDescription(false);
      setShowState(true);
    } else if (showDescriptionFlag) {
      setShowState(false);
      setShowDescription(true);
    } else {
      setShowState(false);
      setShowDescription(false);
    }
  };

  if (!activeInterrupt) {
    return null;
  }

  return (
    <div
      className="bg-card text-card-foreground mx-auto flex w-full max-w-3xl flex-col rounded-xl border p-4 shadow-sm sm:p-5"
      data-agent-inbox-card
    >
      {showSidePanel ? (
        <StateView
          handleShowSidePanel={handleShowSidePanel}
          description={activeDescription}
          values={thread.values}
          view={showState ? "state" : "description"}
        />
      ) : (
        <div className="flex w-full flex-col gap-3">
          {interrupts.length > 1 && (
            <div className="flex flex-wrap items-center gap-2">
              {interrupts.map((it, idx) => {
                const title =
                  it.value?.action_requests?.[0]?.name ??
                  `Interrupt ${idx + 1}`;
                return (
                  <button
                    key={it.id ?? idx}
                    type="button"
                    onClick={() => setActiveInterruptIndex(idx)}
                    className={cn(
                      "rounded-full border px-3 py-1 text-sm transition-colors",
                      idx === activeInterruptIndex
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border bg-background text-muted-foreground hover:border-primary hover:text-primary",
                    )}
                  >
                    {title}
                  </button>
                );
              })}
            </div>
          )}
          <ThreadActionsView
            key={activeInterruptKey}
            interrupt={activeInterrupt}
            handleShowSidePanel={handleShowSidePanel}
            showState={showState}
            showDescription={showDescription}
          />
        </div>
      )}
    </div>
  );
}
