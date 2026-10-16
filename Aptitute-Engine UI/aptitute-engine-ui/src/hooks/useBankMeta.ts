import { useCallback, useEffect, useState } from "react";
import { qme } from "../lib/qme-client";
import type { BankMeta } from "../types/qme";

/** The bank only changes when its files change (hot-reloads server-side), so
 *  `/bank/meta` is fetched once per session and kept for 10 minutes
 *  (API_INTEGRATION.md §3.2, spec §11.1). */
const TTL_MS = 10 * 60 * 1000;

let cached: { at: number; meta: BankMeta } | null = null;
let inflight: Promise<BankMeta> | null = null;

function fetchMeta(): Promise<BankMeta> {
  if (cached && Date.now() - cached.at < TTL_MS) return Promise.resolve(cached.meta);
  if (!inflight) {
    inflight = qme
      .get<BankMeta>("/bank/meta")
      .then((meta) => {
        cached = { at: Date.now(), meta };
        inflight = null;
        return meta;
      })
      .catch((err) => {
        inflight = null;
        throw err;
      });
  }
  return inflight;
}

/** Force the next reader to refetch (error Retry buttons). */
export function resetBankMetaCache() {
  cached = null;
}

export function useBankMeta() {
  const [data, setData] = useState<BankMeta | null>(cached?.meta ?? null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(cached === null);
  const [reloadKey, setReloadKey] = useState(0);

  const refetch = useCallback(() => {
    resetBankMetaCache();
    setLoading(true);
    setError(null);
    setReloadKey((k) => k + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchMeta()
      .then((meta) => {
        if (!cancelled) {
          setData(meta);
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

  return { meta: data, loading, error, refetch };
}
