"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiBaseUrl } from "@/lib/api";
import { TOKEN_LS_KEY } from "@/lib/constants";

type Source = { title: string; url: string };

export default function CareerPage() {
  const { t } = useLanguage();
  const [goal, setGoal] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function ask() {
    if (!goal.trim() || loading) return;
    const token = localStorage.getItem(TOKEN_LS_KEY);
    if (!token) {
      setErr("Please sign in.");
      return;
    }
    setErr(null);
    setAnswer("");
    setSources([]);
    setLoading(true);
    setSearching(true);
    try {
      const res = await fetch(`${apiBaseUrl()}/career/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ goal }),
      });
      if (!res.ok || !res.body) throw new Error(`Failed (${res.status})`);
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
            if (evt === "sources") {
              setSearching(false);
              if (Array.isArray(payload)) setSources(payload.filter((s) => s && s.url));
            } else if (evt === "token") {
              setSearching(false);
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
      setSearching(false);
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
            Describe your career goal — we&apos;ll pull <strong>real requirements from live job postings</strong> (LinkedIn,
            Indeed &amp; more) and map them to your AIU courses.
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
            onKeyDown={(e) => e.key === "Enter" && ask()}
            placeholder={t("car.egGoal")}
            className="flex-1"
          />
          <Button onClick={ask} disabled={loading || !goal.trim()}>
            {searching ? "Searching jobs…" : loading ? "Building plan…" : "Get Plan"}
          </Button>
        </section>

        {err && (
          <div className="rounded-lg bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 px-3 py-2 text-sm">
            {err}
          </div>
        )}

        {searching && !answer && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2 text-sm text-zinc-500"
          >
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-zinc-300 border-t-[#B8001F]" />
            Searching LinkedIn, Indeed &amp; job platforms for real {goal || "role"} requirements…
          </motion.div>
        )}

        {answer && (
          <motion.article
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", stiffness: 200, damping: 20 }}
            className="rounded-xl border border-zinc-200 dark:border-zinc-700 dark:border-zinc-800 p-5 shadow-sm prose prose-sm dark:prose-invert max-w-none [&_table]:w-full [&_table]:border-collapse [&_th]:border [&_td]:border [&_th]:border-zinc-300 [&_td]:border-zinc-200 dark:[&_th]:border-zinc-600 dark:[&_td]:border-zinc-700 [&_th]:px-2 [&_th]:py-1 [&_td]:px-2 [&_td]:py-1 [&_th]:bg-zinc-100 dark:[&_th]:bg-zinc-700/60"
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>
          </motion.article>
        )}

        {sources.length > 0 && (
          <motion.section
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-4"
          >
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-400">
              Sources — {sources.length} live job-market result{sources.length === 1 ? "" : "s"}
            </div>
            <ol className="space-y-1.5">
              {sources.map((s, i) => (
                <li key={i} className="flex gap-2 text-sm">
                  <span className="text-zinc-400">[{i + 1}]</span>
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#B8001F] hover:underline dark:text-[#ff5a78] line-clamp-1"
                    title={s.url}
                  >
                    {s.title || s.url}
                  </a>
                </li>
              ))}
            </ol>
          </motion.section>
        )}
      </main>
    </AppLayout>
  );
}
