"use client";

import { useEffect, useState, useCallback } from "react";
import { normalizeErrorMessage } from "@/lib/utils";

type UsePageDataOptions<T> = {
  token: string | null;
  signOut: () => void;
  fetcher: (token: string) => Promise<T>;
  fallbackError?: string;
};

export function usePageData<T>({ token, signOut, fetcher, fallbackError = "Failed to load" }: UsePageDataOptions<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(
    async (tkn: string) => {
      setError(null);
      setLoading(true);
      try {
        const result = await fetcher(tkn);
        setData(result);
      } catch (e: unknown) {
        const msg = normalizeErrorMessage(e, fallbackError);
        if (msg.toLowerCase().includes("unauthorized") || msg.toLowerCase().includes("invalid token")) {
          signOut();
          return;
        }
        setError(msg);
      } finally {
        setLoading(false);
      }
    },
    [fetcher, signOut, fallbackError],
  );

  useEffect(() => {
    if (!token) return;
    load(token);
  }, [token, load]);

  const retry = useCallback(() => {
    if (token) load(token);
  }, [token, load]);

  return { data, setData, error, setError, loading, retry };
}
