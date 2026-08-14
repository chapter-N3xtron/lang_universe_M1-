"use client";
import { useEffect, useRef } from "react";
import type { PropsWithChildren, RefObject } from "react";

/** Adapted MessageScroller-style primitive; not copied from an installable package. */
export function MessageScrollerAdapted({
  children,
  viewportRef,
  onHumanControl,
}: PropsWithChildren<{
  viewportRef: RefObject<HTMLDivElement | null>;
  onHumanControl?: () => void;
}>) {
  const contentRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const viewport = viewportRef.current;
    const content = contentRef.current;
    if (!viewport || !content) return;
    const cancel = () => onHumanControl?.();
    const resize = new ResizeObserver(() => {
      if (viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 24)
        viewport.scrollTop = viewport.scrollHeight;
    });
    resize.observe(content);
    ["wheel", "touchstart", "pointerdown", "selectstart"].forEach((event) =>
      viewport.addEventListener(event, cancel, { passive: true }),
    );
    return () => {
      resize.disconnect();
      ["wheel", "touchstart", "pointerdown", "selectstart"].forEach((event) =>
        viewport.removeEventListener(event, cancel),
      );
    };
  }, [onHumanControl, viewportRef]);
  return <div ref={contentRef}>{children}</div>;
}
