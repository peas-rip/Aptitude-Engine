import { useState } from "react";
import { qme } from "../lib/qme-client";
import type { ChapterKnowledge } from "../types/qme";
import type { ApiError } from "../lib/qme-client";

export function useKnowledge(chapterKey: string, topic?: string) {
  const [data, setData] = useState<ChapterKnowledge | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const fetchKnowledge = async () => {
    if (!chapterKey) {
      setData(null);
      setError(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await qme.get<ChapterKnowledge>(
        `/chapters/${encodeURIComponent(chapterKey)}/knowledge`,
        topic ? { topic } : undefined
      );
      setData(res);
      setError(null);
    } catch (e) {
      const apiError = e as ApiError;
      setError(apiError);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  // We could use useEffect to refetch when chapterKey or topic changes,
  // but we expose a function for manual control (e.g., on demand).
  return { fetchKnowledge, data, error, loading };
}