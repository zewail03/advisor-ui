"use client";

import { useEffect, useState } from "react";
import { useTheme } from "@/hooks/useTheme";
import { useAuth } from "@/hooks/useAuth";
import { getMe } from "@/lib/api";
import { AVATAR_LS_KEY } from "@/lib/constants";
import { AppLayoutContext } from "./AppLayoutContext";
import TopBar from "./TopBar";
import Footer from "./Footer";
import ChatPanel from "./ChatPanel";
import ErrorBoundary from "@/components/ErrorBoundary";

type AppLayoutProps = {
  children: React.ReactNode;
  activePath: string;
  userName?: string | null;
  hideChatbot?: boolean;
};

export default function AppLayout({ children, activePath, userName, hideChatbot }: AppLayoutProps) {
  const { isDark, toggleTheme } = useTheme();
  const { token, signOut } = useAuth();
  const [avatarDataUrl, setAvatarDataUrl] = useState<string | null>(null);
  const [resolvedName, setResolvedName] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const saved = localStorage.getItem(AVATAR_LS_KEY);
      if (saved) setAvatarDataUrl(saved);
    } catch {
      // ignore
    }
  }, []);

  // Always show the signed-in student's real name in the top bar, regardless
  // of any placeholder a page passes for userName.
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    getMe(token)
      .then((me) => {
        if (!cancelled && me?.full_name) setResolvedName(me.full_name);
      })
      .catch(() => {
        /* fall back to the passed userName */
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <AppLayoutContext.Provider value={{ isDark, token, signOut }}>
      <div className={`min-h-screen flex flex-col overflow-x-hidden ${isDark ? "dark bg-zinc-950" : "bg-[#f6f7fb]"}`}>
        <TopBar
          isDark={isDark}
          toggleTheme={toggleTheme}
          signOut={signOut}
          activePath={activePath}
          userName={resolvedName ?? userName}
          avatarDataUrl={avatarDataUrl}
        />
        <ErrorBoundary><div className="flex-1">{children}</div></ErrorBoundary>
        <Footer />
        <ChatPanel isDark={isDark} hidden={hideChatbot} />
      </div>
    </AppLayoutContext.Provider>
  );
}
