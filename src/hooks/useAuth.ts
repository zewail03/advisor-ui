"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CHAT_LS_KEY, REFRESH_LS_KEY, TOKEN_LS_KEY } from "@/lib/constants";
import { login as apiLogin } from "@/lib/api";

export function useAuth() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = localStorage.getItem(TOKEN_LS_KEY);
    if (!saved) {
      router.push("/");
      return;
    }
    setToken(saved);
  }, [router]);

  const signIn = useCallback(
    async (student_number: string, password: string) => {
      const pair = await apiLogin(student_number, password);
      localStorage.setItem(TOKEN_LS_KEY, pair.access_token);
      localStorage.setItem(REFRESH_LS_KEY, pair.refresh_token);
      // Fresh login → drop any chat transcript left over from a previous student.
      localStorage.removeItem(CHAT_LS_KEY);
      setToken(pair.access_token);
      return pair;
    },
    [],
  );

  const signOut = useCallback(() => {
    if (typeof window !== "undefined") {
      try {
        localStorage.removeItem(TOKEN_LS_KEY);
        localStorage.removeItem(REFRESH_LS_KEY);
        localStorage.removeItem(CHAT_LS_KEY);
      } catch {
        // ignore
      }
    }
    setToken(null);
    router.push("/");
  }, [router]);

  return { token, signIn, signOut };
}
