import { useState } from "react";
import { qme } from "../lib/qme-client";
import type { GeneratedTest } from "../types/qme";
import type { TestRequest } from "../types/qme";
import type { ApiError } from "../lib/qme-client";

export function useCreateTest() {
  const [data, setData] = useState<GeneratedTest | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const createTest = async (body: TestRequest) => {
    setLoading(true);
    setError(null);
    try {
      const res = await qme.post<GeneratedTest>("/tests", body);
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

  return { createTest, data, error, loading };
}