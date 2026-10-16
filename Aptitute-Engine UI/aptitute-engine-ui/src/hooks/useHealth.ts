import { useCallback, useEffect, useState } from "react";
import { qme } from "../lib/qme-client";

export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  openai_configured: boolean;
}

/**
 * `/health` is a liveness probe, but the header indicator and the Overview
 * banner both need it — cache at module scope so the session issues one
 * request and in-flight duplicates are shared.
 */
let cached: HealthResponse | null = null;
let inflight: Promise<HealthResponse> | null = null;

function fetchHealth(): Promise<HealthResponse> {
  if (cached) return Promise.resolve(cached);
  if (!inflight) {
    inflight = qme
      .get<HealthResponse>("/health")
      .then((res) => {
        cached = res;
        inflight = null;
        return res;
      })
      .catch((err) => {
        inflight = null;
        throw err;
      });
  }
  return inflight;
}

/** Drop the cached probe so the next call re-hits the server (Retry buttons). */
export function resetHealthCache() {
  cached = null;
}

export function useHealth() {
  const [data, setData] = useState<HealthResponse | null>(cached);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(cached === null);
  const [reloadKey, setReloadKey] = useState(0);

  const refetch = useCallback(() => {
    resetHealthCache();
    setLoading(true);
    setError(null);
    setReloadKey((k) => k + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e as Error);
          setData(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  return { data, error, loading, refetch };
}
