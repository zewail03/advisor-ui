"use client";

import { useEffect, useState } from "react";
import {
  Sparkles,
  Send,
  Loader2,
  Database,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
} from "lucide-react";
import AdminShell from "@/components/AdminShell";
import {
  askAssistant,
  getAssistantSuggestions,
  getAnomalies,
  type AssistantAnswer,
  type AnomalyReport,
  type Anomaly,
} from "@/lib/api";

// Minimal **bold** + line-break renderer (admin-ui has no markdown dep).
function renderInline(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? (
      <strong key={i} className="font-semibold text-zinc-900">{p.slice(2, -2)}</strong>
    ) : (
      <span key={i}>{p}</span>
    ),
  );
}

function Md({ text }: { text: string }) {
  return (
    <div className="space-y-1.5">
      {text.split("\n").filter((l) => l.trim() !== "").map((line, i) => (
        <p key={i} className="text-sm leading-relaxed text-zinc-700">{renderInline(line)}</p>
      ))}
    </div>
  );
}

const SEV: Record<Anomaly["severity"], { ring: string; chip: string; label: string }> = {
  high: { ring: "border-red-200 bg-red-50", chip: "bg-red-100 text-red-700", label: "High" },
  medium: { ring: "border-amber-200 bg-amber-50", chip: "bg-amber-100 text-amber-700", label: "Medium" },
  low: { ring: "border-blue-200 bg-blue-50", chip: "bg-blue-100 text-blue-700", label: "Low" },
  ok: { ring: "border-emerald-200 bg-emerald-50", chip: "bg-emerald-100 text-emerald-700", label: "Clear" },
};

export default function AssistantPage() {
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<AssistantAnswer | null>(null);
  const [askErr, setAskErr] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const [report, setReport] = useState<AnomalyReport | null>(null);
  const [scanning, setScanning] = useState(true);
  const [scanErr, setScanErr] = useState<string | null>(null);

  useEffect(() => {
    getAssistantSuggestions().then((s) => setSuggestions(s.suggestions)).catch(() => {});
    runScan();
  }, []);

  function runScan() {
    setScanning(true);
    setScanErr(null);
    getAnomalies()
      .then(setReport)
      .catch((e) => setScanErr(e instanceof Error ? e.message : "Scan failed"))
      .finally(() => setScanning(false));
  }

  async function ask(q?: string) {
    const text = (q ?? question).trim();
    if (!text || asking) return;
    setQuestion(text);
    setAsking(true);
    setAskErr(null);
    try {
      setAnswer(await askAssistant(text));
    } catch (e) {
      setAskErr(e instanceof Error ? e.message : "Query failed");
    } finally {
      setAsking(false);
    }
  }

  return (
    <AdminShell>
      <div className="mb-1 flex items-center gap-2">
        <Sparkles size={22} className="text-[#b8001f]" />
        <h1 className="text-2xl font-bold text-zinc-900">AI Assistant</h1>
      </div>
      <p className="mb-6 text-sm text-zinc-500">
        Ask in plain English. Every answer is computed from live database queries — no guessing.
      </p>

      {/* Ask panel */}
      <div className="rounded-2xl border border-zinc-200 bg-white shadow-sm">
        <div className="flex items-center gap-2 border-b border-zinc-100 p-3">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()}
            placeholder="e.g. How many students are failing CSE233?"
            className="h-11 flex-1 rounded-xl border border-zinc-200 bg-zinc-50 px-4 text-sm outline-none focus:border-[#b8001f]"
          />
          <button
            onClick={() => ask()}
            disabled={asking}
            className="flex h-11 items-center gap-2 rounded-xl bg-[#b8001f] px-4 text-sm font-semibold text-white transition hover:bg-[#a0001a] disabled:opacity-60"
            type="button"
          >
            {asking ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            Ask
          </button>
        </div>

        {/* Suggestions */}
        <div className="flex flex-wrap gap-2 px-4 py-3">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => ask(s)}
              disabled={asking}
              className="rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 text-xs text-zinc-600 transition hover:border-[#b8001f] hover:text-[#b8001f] disabled:opacity-60"
              type="button"
            >
              {s}
            </button>
          ))}
        </div>

        {/* Answer */}
        {askErr && (
          <div className="mx-4 mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{askErr}</div>
        )}
        {answer && (
          <div className="border-t border-zinc-100 p-5">
            <div className="mb-3 flex items-start gap-3">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-[#b8001f]/10 text-[#b8001f]">
                <Sparkles size={16} />
              </div>
              <Md text={answer.answer} />
            </div>

            {answer.rows.length > 0 && (
              <div className="mt-3 overflow-x-auto rounded-xl border border-zinc-200">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-100 bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-400">
                      {answer.columns.map((c) => (
                        <th key={c} className="px-4 py-2 font-medium">{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {answer.rows.map((row, i) => (
                      <tr key={i} className="border-b border-zinc-50 last:border-0 hover:bg-zinc-50">
                        {row.map((cell, j) => (
                          <td key={j} className="px-4 py-2 text-zinc-700">
                            {cell === null || cell === undefined ? "—" : String(cell)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {answer.source && (
              <div className="mt-3 flex items-center gap-1.5 text-[11px] text-zinc-400">
                <Database size={12} />
                <span className="font-mono">{answer.source}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Anomaly scanner */}
      <div className="mt-8 mb-2 flex items-center gap-2">
        <ShieldAlert size={20} className="text-[#b8001f]" />
        <h2 className="text-lg font-bold text-zinc-900">Anomaly scan</h2>
        {report && (
          <span className="rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-600">
            {report.flagged} of {report.total_checks} checks flagged
          </span>
        )}
        <button
          onClick={runScan}
          disabled={scanning}
          className="ml-auto flex items-center gap-1.5 rounded-lg border border-zinc-300 px-3 py-1.5 text-sm text-zinc-600 transition hover:bg-zinc-50 disabled:opacity-60"
          type="button"
        >
          <RefreshCw size={14} className={scanning ? "animate-spin" : ""} /> Re-scan
        </button>
      </div>
      <p className="mb-4 text-sm text-zinc-500">
        Live integrity &amp; operational checks across enrollment, finance, and grades.
      </p>

      {scanErr && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{scanErr}</div>}

      {scanning && !report ? (
        <div className="flex items-center gap-2 text-zinc-500">
          <Loader2 className="animate-spin" size={18} /> Scanning…
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {report?.checks.map((c) => {
            const sev = SEV[c.severity];
            const clear = c.severity === "ok";
            return (
              <div key={c.key} className={`rounded-2xl border p-4 shadow-sm ${sev.ring}`}>
                <div className="flex items-center gap-2">
                  {clear ? (
                    <CheckCircle2 size={18} className="text-emerald-600" />
                  ) : (
                    <AlertTriangle size={18} className="text-current opacity-70" />
                  )}
                  <span className="font-semibold text-zinc-900">{c.title}</span>
                  <span className={`ml-auto rounded-full px-2 py-0.5 text-xs font-semibold ${sev.chip}`}>
                    {clear ? "Clear" : `${c.count} · ${sev.label}`}
                  </span>
                </div>
                <p className="mt-1.5 text-xs text-zinc-600">{c.detail}</p>
                {!clear && c.sample.length > 0 && (
                  <ul className="mt-2 space-y-0.5">
                    {c.sample.map((s, i) => (
                      <li key={i} className="font-mono text-[11px] text-zinc-500">• {s}</li>
                    ))}
                    {c.count > c.sample.length && (
                      <li className="text-[11px] italic text-zinc-400">
                        …and {c.count - c.sample.length} more
                      </li>
                    )}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      )}
    </AdminShell>
  );
}
