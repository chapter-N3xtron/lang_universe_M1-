"use client";

import { useState, useEffect, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
const POLL_INTERVAL = 10_000;

export function useBackendHealth() {
  const [online, setOnline] = useState(true);
  const [checking, setChecking] = useState(true);

  const check = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`, {
        cache: "no-store",
        signal: AbortSignal.timeout(5000),
      });
      setOnline(res.ok);
    } catch {
      setOnline(false);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    check();
    const id = setInterval(check, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [check]);

  return { online, checking };
}
