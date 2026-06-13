"use client";

import { useRef, useState } from "react";
import { motion } from "framer-motion";
import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiBaseUrl } from "@/lib/api";
import { TOKEN_LS_KEY } from "@/lib/constants";

export default function CareerPage() {
  const { t } = useLanguage();
  const [goal, setGoal] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const sessionRef = useRef<string | null>(null);

  async function ask() {
    if (!goal.trim() || loading) return;
    const token = localStorage.getItem(TOKEN_LS_KEY);
    if (!token) {
      setErr("Please sign in.");
      return;
    }
    setErr(null);
    setAnswer("");
    setLoading(true);
    try {
      const res = await fetch(`${apiBaseUrl()}/chat/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          message: `Career guidance: ${goal}. Recommend elective sequencing, skills to build each semester, and projects that match this path using my program and CGPA.`,
          session_id: sessionRef.current,
        }),
      });
      if (!res.ok || !res.body) throw new Error(`Chat failed (${res.status})`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let acc = "";
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
            if (evt === "session") sessionRef.current = payload.session_id;
            else if (evt === "token") {
              acc += payload.t || "";
              setAnswer(acc);
            }
          } catch {
            /* ignore */
          }
        }
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  const suggestions = [
    "Data Scientist",
    "Machine Learning Engineer",
    "Full-stack Web Developer",
    "Cybersecurity Analyst",
    "Product Manager",
  ];

  return (
    <AppLayout activePath="/career" userName="Career">
      <main className="px-4 md:px-8 lg:px-16 py-8 space-y-6">
        <motion.header initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-3xl font-bold">{t("car.title")}</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Describe your career goal — we&apos;ll map it to electives, skills, and project ideas.
          </p>
        </motion.header>

        <section className="flex flex-wrap gap-2">
          {suggestions.map((s, i) => (
            <motion.button
              key={s}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.08 }}
              whileHover={{ scale: 1.08, y: -2 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setGoal(s)}
              className="text-xs px-3 py-1.5 rounded-full border border-zinc-300 dark:border-zinc-600 hover:bg-zinc-100 dark:bg-zinc-800 hover:border-[#B8001F] hover:text-[#B8001F] dark:border-zinc-700 dark:hover:bg-zinc-800 transition-colors"
              type="button"
            >
              {s}
            </motion.button>
          ))}
        </section>

        <section className="flex gap-2">
          <Input
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder={t("car.egGoal")}
            className="flex-1"
          />
          <Button onClick={ask} disabled={loading || !goal.trim()}>
            {loading ? "Thinking…" : "Get Plan"}
          </Button>
        </section>

        {err && <div className="rounded-lg bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 px-3 py-2 text-sm">{err}</div>}

        {answer && (
          <motion.article
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", stiffness: 200, damping: 20 }}
            className="rounded-xl border border-zinc-200 dark:border-zinc-700 dark:border-zinc-800 p-5 whitespace-pre-wrap text-sm leading-7 shadow-sm"
          >
            {answer}
          </motion.article>
        )}
      </main>
    </AppLayout>
  );
}
