"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CHAT_LS_KEY, REFRESH_LS_KEY, TOKEN_LS_KEY } from "@/lib/constants";
import { login as apiLogin, verifyTwoFactor as apiVerifyTwoFactor, type TokenPair } from "@/lib/api";

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

  const store = useCallback((pair: TokenPair) => {
    localStorage.setItem(TOKEN_LS_KEY, pair.access_token);
    localStorage.setItem(REFRESH_LS_KEY, pair.refresh_token);
    // Fresh login → drop any chat transcript left over from a previous student.
    localStorage.removeItem(CHAT_LS_KEY);
    setToken(pair.access_token);
  }, []);

  const signIn = useCallback(
    async (student_number: string, password: string) => {
      const r = await apiLogin(student_number, password);
      if ("twofa_required" in r) {
        // Password OK but 2FA is on — caller must collect the delivered code next.
        return { twofaRequired: true as const, challengeToken: r.challenge_token, demoCode: r.demo_code };
      }
      store(r);
      return { twofaRequired: false as const };
    },
    [store],
  );

  // Second login step: verify the authenticator code, then store the tokens.
  const completeTwoFactor = useCallback(
    async (challengeToken: string, code: string) => {
      const pair = await apiVerifyTwoFactor(challengeToken, code);
      store(pair);
    },
    [store],
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

  return { token, signIn, completeTwoFactor, signOut };
}
