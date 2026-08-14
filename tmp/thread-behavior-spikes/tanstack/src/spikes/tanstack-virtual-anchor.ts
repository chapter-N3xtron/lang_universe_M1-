import { useVirtualizer } from "@tanstack/react-virtual";
import type { RefObject } from "react";

/** Isolated adapter only. It deliberately does not make lifecycle decisions. */
export function useTanStackAnchor<T>(
  parentRef: RefObject<HTMLDivElement | null>,
  items: T[],
) {
  return useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 96,
    getItemKey: (index) => index,
    measureElement: (element) => element.getBoundingClientRect().height,
    overscan: 8,
  });
}
