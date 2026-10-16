import { useState } from "react";
import { qme } from "../lib/qme-client";
import type { PracticeRequest, PracticeSet } from "../types/qme";
import type { ApiError } from "../lib/qme-client";

export function usePractice() {
  const [data, setData] = useState<PracticeSet | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const practice = async (body: PracticeRequest) => {
    setLoading(true);
    setError(null);
    try {
      const res = await qme.post<PracticeSet>("/practice", body);
      setData(res);
      setError(null);
      return res;
    } catch (e) {
      const apiError = e as ApiError;
      setError(apiError);
      setData(null);
      throw apiError;
    } finally {
      setLoading(false);
    }
  };

  return { practice, data, error, loading };
}