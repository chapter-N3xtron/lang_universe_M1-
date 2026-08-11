"use client";

import { useEffect } from "react";
import { installManualScrollObservation } from "@/lib/manual-scroll-observation";

/**
 * Deliberately requires a developer URL flag. This keeps the capture API out
 * of ordinary development and all production bundles are a no-op.
 */
export function ManualScrollObservationActivation() {
  useEffect(() => {
    if (
      process.env.NODE_ENV !== "production" &&
      new URLSearchParams(window.location.search).get("manualScrollCapture") ===
        "1"
    ) {
      installManualScrollObservation();
    }
  }, []);

  return null;
}
