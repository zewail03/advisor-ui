"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { motion, AnimatePresence, useMotionValue, useSpring } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiBaseUrl } from "@/lib/api";
import { CHAT_LS_KEY, TOKEN_LS_KEY } from "@/lib/constants";
import { useLanguage } from "@/hooks/useLanguage";

type ChatPanelProps = {
  isDark: boolean;
  hidden?: boolean;
};

type ChatMsg = { role: "user" | "bot"; text: string; sources?: string[] };
type ChatSessionInfo = { id: string; title: string; created_at: string; last_message_at: string };

function relativeTime(iso: string): string {
  const then = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z").getTime();
  const diff = Date.now() - then;
  if (Number.isNaN(diff)) return "";
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return d < 7 ? `${d}d ago` : new Date(then).toLocaleDateString();
}

const GREETING: ChatMsg = {
  role: "bot",
  text: "Hi! I'm your AI Academic Advisor. How can I help you today?",
};

// Drop a trailing empty bot bubble (e.g. if the user navigated mid-stream) so
// the rehydrated transcript never shows a frozen "typing" placeholder.
function sanitize(msgs: ChatMsg[]): ChatMsg[] {
  const out = [...msgs];
  while (out.length && out[out.length - 1].role === "bot" && !out[out.length - 1].text.trim()) {
    out.pop();
  }
  return out.length ? out : [GREETING];
}

export default function ChatPanel({ isDark, hidden }: ChatPanelProps) {
  const { t, lang } = useLanguage();
  const [chatOpen, setChatOpen] = useState(false);
  const [maximized, setMaximized] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([GREETING]);
  const [inputMsg, setInputMsg] = useState("");
  const [sending, setSending] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [sessions, setSessions] = useState<ChatSessionInfo[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const x = useMotionValue(0);
  const y = useMotionValue(0);

  // Chat button hover-tilt (mouse-follow 3D)
  const btnRef = useRef<HTMLButtonElement>(null);
  const btnTiltXRaw = useMotionValue(0);
  const btnTiltYRaw = useMotionValue(0);
  const btnTiltX = useSpring(btnTiltXRaw, { stiffness: 180, damping: 20 });
  const btnTiltY = useSpring(btnTiltYRaw, { stiffness: 180, damping: 20 });

  const handleBtnMove = (e: React.MouseEvent) => {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    const xn = (e.clientX - rect.left) / rect.width - 0.5;
    const yn = (e.clientY - rect.top) / rect.height - 0.5;
    btnTiltYRaw.set(xn * 35);
    btnTiltXRaw.set(-yn * 22);
  };
  const handleBtnLeave = () => {
    btnTiltYRaw.set(0);
    btnTiltXRaw.set(0);
  };

  // Orbiting particles config (radii kept within ~55px so they stay near/around the 90x90 coin)
  const orbitParticles = [
    { size: 8, r: 52, dur: 6, color: "#ff3355", glow: "#ff3355", startAngle: 0 },
    { size: 6, r: 58, dur: 9, color: "#fbbf24", glow: "#fbbf24", startAngle: 90 },
    { size: 7, r: 46, dur: 7.5, color: "#B8001F", glow: "#ff4d6d", startAngle: 180 },
    { size: 5, r: 62, dur: 11, color: "#ffffff", glow: "#ff3355", startAngle: 270 },
  ];

  const [dragConstraints, setDragConstraints] = useState<
    { left: number; right: number; top: number; bottom: number } | undefined
  >(undefined);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const update = () => {
      setDragConstraints({
        left: -window.innerWidth + 150,
        right: 0,
        top: -window.innerHeight + 150,
        bottom: 0,
      });
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  useEffect(() => {
    if (chatOpen) messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatOpen]);

  // Rehydrate transcript + session id once on mount. Because every page mounts
  // its own AppLayout (and therefore its own ChatPanel), this is what keeps the
  // conversation alive across navigation — and keeps the SAME session_id so the
  // backend's stored chat memory continues instead of starting a new thread.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = localStorage.getItem(CHAT_LS_KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        if (Array.isArray(saved.messages) && saved.messages.length) {
          setMessages(sanitize(saved.messages));
        }
        if (typeof saved.sessionId === "string") setSessionId(saved.sessionId);
        if (typeof saved.chatOpen === "boolean") setChatOpen(saved.chatOpen);
        if (typeof saved.maximized === "boolean") setMaximized(saved.maximized);
      }
    } catch {
      /* ignore corrupt state */
    }
    setHydrated(true);
  }, []);

  // Persist whenever the conversation changes (skip while still streaming, and
  // only after the initial rehydrate so we never clobber saved state with the
  // default greeting).
  useEffect(() => {
    if (!hydrated || sending) return;
    try {
      localStorage.setItem(
        CHAT_LS_KEY,
        JSON.stringify({ messages: sanitize(messages), sessionId, chatOpen, maximized }),
      );
    } catch {
      /* storage full / unavailable — non-fatal */
    }
  }, [hydrated, sending, messages, sessionId, chatOpen, maximized]);

  function resetChat() {
    setMessages([GREETING]);
    setSessionId(null);
    setInputMsg("");
    setShowHistory(false);
    try {
      localStorage.removeItem(CHAT_LS_KEY);
    } catch {
      /* ignore */
    }
  }

  async function loadSessions() {
    const token = typeof window !== "undefined" ? localStorage.getItem(TOKEN_LS_KEY) : null;
    if (!token) return;
    setLoadingHistory(true);
    try {
      const res = await fetch(`${apiBaseUrl()}/chat/sessions`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setSessions(await res.json());
    } catch {
      /* offline — leave list as-is */
    } finally {
      setLoadingHistory(false);
    }
  }

  function toggleHistory() {
    setShowHistory((open) => {
      if (!open) loadSessions();
      return !open;
    });
  }

  async function deleteSession(id: string) {
    const token = typeof window !== "undefined" ? localStorage.getItem(TOKEN_LS_KEY) : null;
    if (!token) return;
    if (!window.confirm(t("chat.deleteConfirm"))) return;
    try {
      const res = await fetch(`${apiBaseUrl()}/chat/sessions/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      setSessions((prev) => prev.filter((x) => x.id !== id));
      if (id === sessionId) {
        // the open conversation was deleted — start fresh, keep the drawer open
        setMessages([GREETING]);
        setSessionId(null);
        try {
          localStorage.removeItem(CHAT_LS_KEY);
        } catch {
          /* ignore */
        }
      }
    } catch {
      /* offline — leave list as-is */
    }
  }

  async function openSession(id: string) {
    const token = typeof window !== "undefined" ? localStorage.getItem(TOKEN_LS_KEY) : null;
    if (!token) return;
    setSending(true);
    try {
      const res = await fetch(`${apiBaseUrl()}/chat/sessions/${id}/messages`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("load failed");
      const data = await res.json();
      const restored: ChatMsg[] = (data.messages || []).map(
        (m: { role: string; content: string }) => ({
          role: m.role === "user" ? "user" : "bot",
          text: m.content,
        }),
      );
      setMessages(restored.length ? restored : [GREETING]);
      setSessionId(id);
      setShowHistory(false);
    } catch {
      /* ignore — keep current conversation */
    } finally {
      setSending(false);
    }
  }

  async function sendMessage() {
    const text = inputMsg.trim();
    if (!text || sending) return;
    const token = typeof window !== "undefined" ? localStorage.getItem(TOKEN_LS_KEY) : null;
    if (!token) {
      setMessages((prev) => [...prev, { role: "bot", text: "Please sign in first." }]);
      return;
    }

    setMessages((prev) => [...prev, { role: "user", text }, { role: "bot", text: "" }]);
    setInputMsg("");
    setSending(true);

    try {
      const res = await fetch(`${apiBaseUrl()}/chat/message`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: text, session_id: sessionId, language: lang }),
      });
      if (!res.ok || !res.body) {
        throw new Error(`Chat failed (${res.status})`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let assistant = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const block of events) {
          const lines = block.split("\n");
          const evt = lines.find((l) => l.startsWith("event:"))?.slice(6).trim();
          const data = lines.find((l) => l.startsWith("data:"))?.slice(5).trim();
          if (!data) continue;
          try {
            const payload = JSON.parse(data);
            if (evt === "session") {
              setSessionId(payload.session_id);
            } else if (evt === "citations") {
              // Backend emits the RAG source docs the answer is grounded on.
              const srcs = Array.isArray(payload)
                ? Array.from(new Set(payload.filter(Boolean).map(String)))
                : [];
              if (srcs.length) {
                setMessages((prev) => {
                  const next = [...prev];
                  const last = next[next.length - 1];
                  if (last && last.role === "bot") {
                    next[next.length - 1] = { ...last, sources: srcs };
                  }
                  return next;
                });
              }
            } else if (evt === "token") {
              assistant += payload.t || "";
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                next[next.length - 1] = { ...last, role: "bot", text: assistant };
                return next;
              });
            }
          } catch {
            /* ignore */
          }
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Chat error";
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = { role: "bot", text: `(${msg})` };
        return next;
      });
    } finally {
      setSending(false);
    }
  }

  if (hidden) return null;

  const panelWidth = maximized ? "w-[700px]" : "w-[400px]";
  const panelHeight = maximized ? "h-[600px]" : "h-[420px]";

  return (
    <motion.div
      drag={!maximized}
      dragMomentum={false}
      dragConstraints={dragConstraints}
      style={{ x, y }}
      className="fixed bottom-8 right-8 z-[999]"
      whileDrag={{ scale: 1.05 }}
    >
      <AnimatePresence>
        {!chatOpen && (
          <motion.button
            ref={btnRef}
            onClick={() => setChatOpen(true)}
            onMouseMove={handleBtnMove}
            onMouseLeave={handleBtnLeave}
            className="relative"
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{ type: "spring", stiffness: 260, damping: 20 }}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            style={{ perspective: "1000px" }}
            type="button"
          >
            {/* Orbiting particles — outer rotates, static wrapper translates, inner scales (separate transform chains) */}
            {orbitParticles.map((p, i) => (
              <motion.div
                key={i}
                className="absolute top-1/2 left-1/2 pointer-events-none z-20"
                style={{ width: 0, height: 0 }}
                initial={{ rotate: p.startAngle }}
                animate={{ rotate: p.startAngle + 360 }}
                transition={{ duration: p.dur, repeat: Infinity, ease: "linear" }}
              >
                <div style={{ transform: `translateX(${p.r}px)` }}>
                  <motion.div
                    className="rounded-full"
                    style={{
                      width: p.size,
                      height: p.size,
                      marginLeft: -p.size / 2,
                      marginTop: -p.size / 2,
                      background: p.color,
                      boxShadow: `0 0 ${p.size * 3}px ${p.glow}, 0 0 ${p.size * 1.5}px ${p.glow}`,
                    }}
                    animate={{ scale: [1, 1.5, 1], opacity: [0.8, 1, 0.8] }}
                    transition={{ duration: 2 + i * 0.6, repeat: Infinity, ease: "easeInOut" }}
                  />
                </div>
              </motion.div>
            ))}
            <motion.div
              className="absolute -inset-4 rounded-full"
              animate={{ opacity: [0.3, 0.6, 0.3], scale: [1, 1.1, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
              style={{ boxShadow: "0 0 30px rgba(184,0,31,0.5)", filter: "blur(10px)" }}
            />
            <motion.div
              className="absolute -inset-6 rounded-full"
              animate={{ opacity: [0.2, 0.4, 0.2], scale: [1, 1.15, 1] }}
              transition={{ duration: 2.5, repeat: Infinity }}
              style={{ boxShadow: "0 0 50px rgba(184,0,31,0.4)", filter: "blur(15px)" }}
            />
            <motion.div
              className="absolute -inset-8 rounded-full"
              animate={{ opacity: [0.1, 0.3, 0.1], scale: [1, 1.2, 1] }}
              transition={{ duration: 3, repeat: Infinity }}
              style={{ boxShadow: "0 0 70px rgba(184,0,31,0.3)", filter: "blur(20px)" }}
            />

            <motion.div
              className="relative h-[90px] w-[90px]"
              style={{ transformStyle: "preserve-3d", rotateX: btnTiltX, rotateY: btnTiltY }}
            >
              <motion.div
                className="relative h-[90px] w-[90px]"
                animate={{ y: [0, -5, 0], rotateY: [0, 360] }}
                transition={{
                  y: { duration: 3, repeat: Infinity, ease: "easeInOut" },
                  rotateY: { duration: 8, repeat: Infinity, ease: "linear" },
                }}
                style={{ transformStyle: "preserve-3d", transform: "translateZ(0)" }}
              >
                <div className="absolute inset-0">
                  <Image src="/brain.svg" alt="AI advisor" fill className="object-contain drop-shadow-lg" />
                </div>
                <div className="absolute inset-[15px]">
                  <Image src="/aiuchat.svg" alt="chat ring" fill className="object-contain" />
                </div>
                <motion.div
                  className="absolute bottom-0 right-0 h-[22px] w-[22px] z-10"
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  <Image src="/greencircle.svg" alt="online" fill className="object-contain drop-shadow-md" />
                  <motion.div
                    className="absolute inset-0 rounded-full bg-green-400"
                    animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  />
                </motion.div>
              </motion.div>
            </motion.div>
          </motion.button>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {chatOpen && (
          <motion.div
            initial={{ opacity: 0, y: 30, scale: 0.8 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 30, scale: 0.8 }}
            transition={{ type: "spring", stiffness: 300, damping: 25 }}
            layout
            className={`absolute bottom-0 right-0 ${panelWidth} rounded-2xl border-2 shadow-2xl overflow-hidden transition-all duration-300 ${
              isDark ? "bg-zinc-900 border-zinc-800" : "bg-white border-zinc-200"
            }`}
          >
            {/* Header */}
            <motion.div className="relative flex items-center justify-between bg-gradient-to-r from-[#B8001F] to-[#A0001A] px-5 py-4 text-white rounded-t-2xl overflow-hidden">
              <motion.div
                className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
                animate={{ x: ["-100%", "200%"] }}
                transition={{ duration: 3, repeat: Infinity }}
              />
              <div className="relative z-10 flex items-center gap-3">
                <motion.div
                  className="relative h-8 w-8"
                  animate={{ rotate: [0, 10, -10, 0] }}
                  transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                >
                  <div className="absolute inset-0">
                    <Image src="/brain.svg" alt="AI" fill className="object-contain" />
                  </div>
                  <div className="absolute inset-[4px]">
                    <Image src="/aiuchat.svg" alt="ring" fill className="object-contain" />
                  </div>
                </motion.div>
                <div>
                  <div className="text-sm font-bold">{t("chat.title")}</div>
                  <div className="flex items-center gap-1.5 text-xs opacity-90">
                    <motion.span
                      className="h-2 w-2 rounded-full bg-green-400"
                      animate={{ scale: [1, 1.3, 1] }}
                      transition={{ duration: 1.5, repeat: Infinity }}
                    />
                    {t("chat.online")}
                  </div>
                </div>
              </div>
              <div className="relative z-10 flex items-center gap-1">
                <motion.button
                  whileHover={{ scale: 1.2 }}
                  whileTap={{ scale: 0.9 }}
                  onClick={toggleHistory}
                  className={`grid h-8 w-8 place-items-center rounded-full hover:bg-white/20 ${
                    showHistory ? "bg-white/20" : ""
                  }`}
                  type="button"
                  title={t("chat.history")}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 3v5h5" />
                    <path d="M3.05 13A9 9 0 1 0 6 5.3L3 8" />
                    <path d="M12 7v5l4 2" />
                  </svg>
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.2, rotate: -30 }}
                  whileTap={{ scale: 0.9 }}
                  onClick={resetChat}
                  className="grid h-8 w-8 place-items-center rounded-full hover:bg-white/20"
                  type="button"
                  title={t("chat.new")}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 12a9 9 0 1 1-2.64-6.36" />
                    <path d="M21 3v6h-6" />
                  </svg>
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.2 }}
                  whileTap={{ scale: 0.9 }}
                  onClick={() => setMaximized((p) => !p)}
                  className="grid h-8 w-8 place-items-center rounded-full hover:bg-white/20 text-sm font-bold"
                  type="button"
                  title={maximized ? "Minimize" : "Maximize"}
                >
                  {maximized ? (
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M5 1v4H1M11 1v4h4M5 15v-4H1M11 15v-4h4" />
                    </svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M1 5V1h4M15 5V1h-4M1 11v4h4M15 11v4h-4" />
                    </svg>
                  )}
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.2, rotate: 90 }}
                  whileTap={{ scale: 0.9 }}
                  onClick={() => { setChatOpen(false); setMaximized(false); }}
                  className="grid h-8 w-8 place-items-center rounded-full hover:bg-white/20 text-xl font-bold"
                  type="button"
                >
                  &times;
                </motion.button>
              </div>
            </motion.div>

            {/* Messages */}
            <div
              className={`relative ${panelHeight} overflow-y-auto p-5 scroll-smooth ${
                isDark ? "bg-zinc-900" : "bg-gradient-to-b from-zinc-50 to-white"
              }`}
            >
              {/* Conversation history drawer */}
              <AnimatePresence>
                {showHistory && (
                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ duration: 0.2 }}
                    className={`absolute inset-0 z-20 flex flex-col ${
                      isDark ? "bg-zinc-900" : "bg-white"
                    }`}
                  >
                    <div
                      className={`flex items-center justify-between border-b px-4 py-3 ${
                        isDark ? "border-zinc-800" : "border-zinc-100"
                      }`}
                    >
                      <span className={`text-sm font-bold ${isDark ? "text-white" : "text-zinc-900"}`}>
                        {t("chat.yourConversations")}
                      </span>
                      <button
                        onClick={resetChat}
                        className="rounded-lg bg-[#B8001F] px-2.5 py-1 text-xs font-semibold text-white transition hover:bg-[#A0001A]"
                        type="button"
                      >
                        + New
                      </button>
                    </div>
                    <div className="flex-1 overflow-y-auto p-2">
                      {loadingHistory ? (
                        <div className="grid h-full place-items-center text-sm text-zinc-400">Loading…</div>
                      ) : sessions.length === 0 ? (
                        <div className="grid h-full place-items-center px-6 text-center text-sm text-zinc-400">
                          {t("chat.noConversations")}
                        </div>
                      ) : (
                        sessions.map((s) => {
                          const active = s.id === sessionId;
                          return (
                            <div
                              key={s.id}
                              onClick={() => openSession(s.id)}
                              role="button"
                              tabIndex={0}
                              onKeyDown={(e) => e.key === "Enter" && openSession(s.id)}
                              className={`group mb-1 flex w-full cursor-pointer items-center gap-2 rounded-xl px-3 py-2.5 text-left transition ${
                                active
                                  ? "bg-[#B8001F]/10 ring-1 ring-[#B8001F]/30"
                                  : isDark
                                  ? "hover:bg-zinc-800"
                                  : "hover:bg-zinc-100"
                              }`}
                            >
                              <div className="flex min-w-0 flex-1 flex-col items-start gap-0.5">
                                <span
                                  className={`line-clamp-1 text-sm font-medium ${
                                    isDark ? "text-zinc-100" : "text-zinc-800"
                                  }`}
                                >
                                  {s.title || "Conversation"}
                                </span>
                                <span className="text-[11px] text-zinc-400">
                                  {relativeTime(s.last_message_at)}
                                  {active ? " · current" : ""}
                                </span>
                              </div>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  deleteSession(s.id);
                                }}
                                className="shrink-0 rounded-lg p-1.5 text-zinc-400 opacity-60 transition hover:bg-red-50 hover:text-red-600 group-hover:opacity-100 dark:hover:bg-red-950/40 dark:hover:text-red-400"
                                title={t("chat.deleteConversation")}
                              >
                                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                  <path d="M3 6h18" />
                                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                                  <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                                  <line x1="10" y1="11" x2="10" y2="17" />
                                  <line x1="14" y1="11" x2="14" y2="17" />
                                </svg>
                              </button>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {messages.map((msg, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 20, scale: 0.8 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ delay: Math.min(idx * 0.05, 0.3), type: "spring", stiffness: 200 }}
                  className={`mb-3 flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  {msg.role === "bot" && (
                    <motion.div
                      className="mr-2 mt-1 flex-shrink-0 h-6 w-6 relative"
                      animate={{ rotate: sending && idx === messages.length - 1 ? [0, 360] : 0 }}
                      transition={{ duration: 2, repeat: sending && idx === messages.length - 1 ? Infinity : 0, ease: "linear" }}
                    >
                      <Image src="/brain.svg" alt="AI" fill className="object-contain" />
                    </motion.div>
                  )}
                  <motion.div
                    whileHover={{ scale: 1.02, y: -1 }}
                    className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-md ${
                      msg.role === "user"
                        ? "bg-gradient-to-br from-[#B8001F] to-[#A0001A] text-white"
                        : isDark
                        ? "bg-zinc-800 text-white border border-zinc-700"
                        : "bg-white border-2 border-zinc-200 text-zinc-900"
                    }`}
                  >
                    {msg.text ? (
                      msg.role === "bot" ? (
                        <div className="prose prose-sm dark:prose-invert max-w-none [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0.5 [&_p]:my-1 [&_h3]:text-sm [&_h3]:font-bold [&_h3]:mt-2 [&_h3]:mb-1 [&_strong]:font-semibold [&_hr]:my-2 [&_table]:text-xs [&_table]:my-2 [&_table]:w-full [&_table]:border-collapse [&_th]:px-2 [&_th]:py-1 [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_td]:border [&_th]:border-zinc-300 [&_td]:border-zinc-200 dark:[&_th]:border-zinc-600 dark:[&_td]:border-zinc-700 [&_th]:bg-zinc-100 dark:[&_th]:bg-zinc-700/60 [&_th]:text-left">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text === GREETING.text ? t("chat.greeting") : msg.text}</ReactMarkdown>
                        </div>
                      ) : (
                        msg.text
                      )
                    ) : (
                      <motion.span
                        className="inline-flex gap-1"
                        animate={{ opacity: [0.3, 1, 0.3] }}
                        transition={{ duration: 1.2, repeat: Infinity }}
                      >
                        <span className="h-2 w-2 rounded-full bg-current inline-block" />
                        <span className="h-2 w-2 rounded-full bg-current inline-block" />
                        <span className="h-2 w-2 rounded-full bg-current inline-block" />
                      </motion.span>
                    )}

                    {msg.role === "bot" && msg.sources && msg.sources.length > 0 && (
                      <div
                        className={`mt-2 border-t pt-2 ${
                          isDark ? "border-zinc-700" : "border-zinc-200"
                        }`}
                      >
                        <div className="mb-1 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                          </svg>
                          {t("chat.sources")}
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {msg.sources.map((s, i) => (
                            <span
                              key={i}
                              className={`rounded-md px-2 py-0.5 text-[11px] font-medium ${
                                isDark
                                  ? "bg-zinc-700/60 text-zinc-200"
                                  : "bg-[#B8001F]/8 text-[#B8001F]"
                              }`}
                              title={s}
                            >
                              {s}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </motion.div>
                </motion.div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div
              className={`border-t-2 p-4 ${
                isDark ? "border-zinc-800 bg-zinc-900" : "border-zinc-100 bg-white"
              }`}
            >
              <div className="flex gap-2">
                <Input
                  value={inputMsg}
                  onChange={(e) => setInputMsg(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                  placeholder={t("chat.placeholder")}
                  disabled={sending}
                  className={`h-11 flex-1 rounded-xl border-2 transition-all ${
                    isDark
                      ? "bg-zinc-800 border-zinc-700 text-white focus:border-[#B8001F]"
                      : "bg-zinc-50 focus:border-[#B8001F]"
                  }`}
                />
                <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                  <Button
                    onClick={sendMessage}
                    disabled={sending}
                    className="h-11 rounded-xl bg-gradient-to-r from-[#B8001F] to-[#A0001A] hover:from-[#A0001A] hover:to-[#800016] shadow-lg"
                    type="button"
                  >
                    {sending ? (
                      <motion.span
                        animate={{ rotate: 360 }}
                        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                        className="inline-block"
                      >
                        &#9696;
                      </motion.span>
                    ) : (
                      "Send"
                    )}
                  </Button>
                </motion.div>
              </div>
              <motion.div
                className="mt-2 text-center text-[11px] font-medium text-zinc-500"
                animate={{ opacity: [0.5, 1, 0.5] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                Drag the chat bubble anywhere!
              </motion.div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
