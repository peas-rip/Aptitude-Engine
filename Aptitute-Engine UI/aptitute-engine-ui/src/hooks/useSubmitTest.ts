import { useState } from "react";
import { qme } from "../lib/qme-client";
import type { SubmitRequest, TestResult } from "../types/qme";
import type { ApiError } from "../lib/qme-client";

export function useSubmitTest() {
  const [data, setData] = useState<TestResult | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const submitTest = async (body: SubmitRequest) => {
    setLoading(true);
    setError(null);
    try {
      const res = await qme.post<TestResult>("/tests/submit", body);
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

  return { submitTest, data, error, loading };
}