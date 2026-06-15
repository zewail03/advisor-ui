"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ShieldAlert, ShieldCheck, TrendingDown, Sparkles } from "lucide-react";

import { getRiskForecast, type RiskForecast } from "@/lib/api";

type Props = {
  token: string;
  isDark: boolean;
};

const BAND = {
  high: {
    headline: "Elevated risk of academic difficulty",
    border: "border-red-500",
    bar: "bg-red-500",
    chip: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
    accent: "text-red-600 dark:text-red-400",
    Icon: ShieldAlert,
  },
  moderate: {
    headline: "Some early signs worth watching",
    border: "border-amber-500",
    bar: "bg-amber-500",
    chip: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
    accent: "text-amber-600 dark:text-amber-400",
    Icon: TrendingDown,
  },
  low: {
    headline: "On track — no early-warning signs",
    border: "border-emerald-500",
    bar: "bg-emerald-500",
    chip: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
    accent: "text-emerald-600 dark:text-emerald-400",
    Icon: ShieldCheck,
  },
} as const;

export default function RiskPanel({ token, isDark }: Props) {
  const [data, setData] = useState<RiskForecast | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getRiskForecast(token, controller.signal)
      .then(setData)
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => controller.abort();
  }, [token]);

  if (failed || !data || !data.available || !data.risk_band) return null;

  const theme = BAND[data.risk_band];
  const pct = Math.round((data.risk_score ?? 0) * 100);
  const Icon = theme.Icon;
  const card = isDark ? "bg-zinc-900" : "bg-white";
  const sub = isDark ? "text-zinc-400" : "text-zinc-600";
  const body = isDark ? "text-zinc-300" : "text-zinc-700";

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className={`mb-8 rounded-2xl border-2 ${theme.border} ${card} p-6 shadow-sm`}
    >
      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl ${theme.chip}`}>
            <Icon size={22} />
          </div>
          <div>
            <div className={`text-xs font-semibold uppercase tracking-wide ${theme.accent}`}>
              Academic Early-Warning
            </div>
            <h2 className={`text-lg font-bold ${isDark ? "text-white" : "text-zinc-900"}`}>
              {theme.headline}
            </h2>
            <div className={`mt-0.5 text-xs ${sub}`}>
              {data.horizon === "forecast"
                ? "Forecast from your first-year record — the outcome is still open."
                : "Assessment based on your early academic record."}
            </div>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <div className={`text-3xl font-extrabold leading-none ${theme.accent}`}>{pct}%</div>
          <div className={`text-[10px] font-semibold uppercase tracking-wide ${sub}`}>risk score</div>
        </div>
      </div>

      {/* gauge */}
      <div className={`mb-4 h-2.5 w-full overflow-hidden rounded-full ${isDark ? "bg-zinc-800" : "bg-zinc-100"}`}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: "easeOut", delay: 0.15 }}
          className={`h-full rounded-full ${theme.bar}`}
        />
      </div>

      {data.narrative && (
        <div
          className={`mb-4 rounded-lg border-l-4 ${theme.border} px-4 py-3 text-sm leading-relaxed ${
            isDark ? "bg-zinc-950/40 text-zinc-200" : "bg-zinc-50 text-zinc-800"
          }`}
        >
          <span className="mr-1 inline-flex items-center gap-1 text-xs font-semibold text-[#B8001F]">
            <Sparkles size={12} /> Advisor note
          </span>
          <p className="mt-1">{data.narrative}</p>
        </div>
      )}

      {data.factors && data.factors.length > 0 && (
        <div className="mb-4">
          <div className={`mb-2 text-sm font-semibold ${isDark ? "text-zinc-200" : "text-zinc-800"}`}>
            What the model weighed
          </div>
          <div className="space-y-2">
            {data.factors.map((f) => {
              const share = Math.min(100, Math.round((f.weight / (data.factors![0].weight || 1)) * 100));
              return (
                <div
                  key={f.name}
                  className={`rounded-lg border p-3 ${isDark ? "border-zinc-800 bg-zinc-950/40" : "border-zinc-200 bg-zinc-50"}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-zinc-900"}`}>{f.label}</span>
                    <div className={`h-1.5 w-20 overflow-hidden rounded-full ${isDark ? "bg-zinc-800" : "bg-zinc-200"}`}>
                      <div className={`h-full ${theme.bar}`} style={{ width: `${share}%` }} />
                    </div>
                  </div>
                  <div className={`mt-1 text-xs ${body}`}>{f.detail}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {data.protective && data.protective.length > 0 && (
        <div className="mb-4">
          <div className={`mb-2 text-sm font-semibold ${isDark ? "text-zinc-200" : "text-zinc-800"}`}>
            What&rsquo;s keeping you steady
          </div>
          <div className="flex flex-wrap gap-2">
            {data.protective.map((p) => (
              <span
                key={p.name}
                className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
              >
                {p.label}
              </span>
            ))}
          </div>
        </div>
      )}

      {data.recommended_actions && data.recommended_actions.length > 0 && (
        <div className="mb-3">
          <div className={`mb-2 text-sm font-semibold ${isDark ? "text-zinc-200" : "text-zinc-800"}`}>
            Suggested next steps
          </div>
          <ul className={`list-disc space-y-1 pl-5 text-sm ${body}`}>
            {data.recommended_actions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      <div className={`mt-2 border-t pt-3 text-[11px] ${isDark ? "border-zinc-800 text-zinc-500" : "border-zinc-100 text-zinc-400"}`}>
        Predicted by a logistic-regression model trained on {data.model?.n_train ?? "—"} prior students
        {data.model?.auc ? ` · cross-validated AUC ${data.model.auc.toFixed(2)}` : ""}. The model reads only your
        first-year record; it does not see — and cannot change — your official standing.
      </div>
    </motion.div>
  );
}
