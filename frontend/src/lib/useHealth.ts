import { useEffect, useState } from "react";

import { fetchHealth } from "./api";
import type { HealthResponse } from "../types/health";

type ConnectionState = "checking" | "connected" | "degraded" | "unreachable";

interface UseHealthResult {
  state: ConnectionState;
  data: HealthResponse | null;
  error: string | null;
  refresh: () => void;
}

export function useHealth(pollIntervalMs = 15_000): UseHealthResult {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [state, setState] = useState<ConnectionState>("checking");
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const result = await fetchHealth();
        if (cancelled) return;
        setData(result);
        setError(null);
        setState(result.status === "ok" ? "connected" : "degraded");
      } catch (err) {
        if (cancelled) return;
        setData(null);
        setError(err instanceof Error ? err.message : "Unknown error");
        setState("unreachable");
      }
    }

    check();
    const interval = setInterval(() => setTick((t) => t + 1), pollIntervalMs);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollIntervalMs, tick]);

  return { state, data, error, refresh: () => setTick((t) => t + 1) };
}
