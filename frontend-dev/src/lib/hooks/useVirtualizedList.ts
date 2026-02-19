import { useMemo } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

export function useVirtualizedList(
  count: number,
  options: {
    estimateSize: number | ((index: number) => number);
    getScrollElement: () => HTMLElement | null;
    overscan?: number;
  }
) {
  const estimateSize = options.estimateSize;
  return useVirtualizer({
    count,
    getScrollElement: options.getScrollElement,
    estimateSize: typeof estimateSize === "number" ? () => estimateSize : estimateSize,
    overscan: options.overscan ?? 6,
  });
}
