"use client";

import { useEffect, useState } from "react";
import {
  Users,
  UserCheck,
  AlertTriangle,
  BookOpen,
  Wallet,
  Inbox,
  type LucideIcon,
} from "lucide-react";
import { motion } from "framer-motion";
import AdminShell from "@/components/AdminShell";
import { CountUp, staggerContainer, fadeUpItem } from "@/components/Motion";
import {
  getOverview,
  getAtRisk,
  type Overview,
  type AtRiskStudent,
} from "@/lib/api";

type StatCard = {
  label: string;
  icon: LucideIcon;
  color: string;
  value?: number;
  format?: (n: number) => string;
  node?: React.ReactNode;
};

export default function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [atRisk, setAtRisk] = useState<AtRiskStudent[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getOverview(), getAtRisk()])
      .then(([ov, ar]) => {
        setOverview(ov);
        setAtRisk(ar.students);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  const cards: StatCard[] = overview
    ? [
        { label: "Total Students", value: overview.students.total, icon: Users, color: "bg-blue-50 text-blue-600" },
        { label: "Active", value: overview.students.active, icon: UserCheck, color: "bg-emerald-50 text-emerald-600" },
        { label: "At Risk (CGPA < 2.0)", value: overview.students.at_risk, icon: AlertTriangle, color: "bg-amber-50 text-amber-600" },
        { label: "Open Sections", value: overview.sections.open, icon: BookOpen, color: "bg-violet-50 text-violet-600" },
        {
          label: "Outstanding Balance",
          value: overview.financial.total_outstanding,
          icon: Wallet,
          color: "bg-rose-50 text-rose-600",
          format: (n: number) => `${n.toLocaleString()} ${overview.financial.currency}`,
        },
        {
          label: "Pending Petitions / Approvals",
          node: (
            <>
              <CountUp value={overview.queues.pending_petitions} /> /{" "}
              <CountUp value={overview.queues.pending_advisor_approvals} />
            </>
          ),
          icon: Inbox,
          color: "bg-zinc-100 text-zinc-600",
        },
      ]
    : [];

  return (
    <AdminShell>
      <h1 className="mb-1 text-2xl font-bold text-zinc-900">Overview</h1>
      <p className="mb-6 text-sm text-zinc-500">Live snapshot of the student system.</p>

      {err && <div className="mb-6 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="shimmer h-24 rounded-2xl border border-zinc-200 bg-white" />
          ))}
        </div>
      ) : (
        <>
          <motion.div
            variants={staggerContainer}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
          >
            {cards.map((c) => {
              const Icon = c.icon;
              return (
                <motion.div
                  key={c.label}
                  variants={fadeUpItem}
                  className="card-hover flex items-center gap-4 rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm"
                >
                  <motion.div
                    whileHover={{ rotate: -8, scale: 1.08 }}
                    transition={{ type: "spring", stiffness: 300, damping: 15 }}
                    className={`grid h-12 w-12 place-items-center rounded-xl ${c.color}`}
                  >
                    <Icon size={22} />
                  </motion.div>
                  <div>
                    <div className="text-2xl font-bold text-zinc-900">
                      {c.node ?? <CountUp value={c.value ?? 0} format={c.format} />}
                    </div>
                    <div className="text-xs font-medium text-zinc-500">{c.label}</div>
                  </div>
                </motion.div>
              );
            })}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            className="mt-8 overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm"
          >
            <div className="flex items-center gap-2 border-b border-zinc-100 px-6 py-4">
              <AlertTriangle size={18} className="text-amber-500" />
              <h2 className="font-semibold text-zinc-900">Intervention queue — lowest CGPA</h2>
              <span className="ml-auto text-xs text-zinc-400">{atRisk.length} shown</span>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-100 text-left text-xs uppercase tracking-wide text-zinc-400">
                  <th className="px-6 py-3 font-medium">Code</th>
                  <th className="px-6 py-3 font-medium">Name</th>
                  <th className="px-6 py-3 font-medium">CGPA</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {atRisk.map((s, i) => (
                  <motion.tr
                    key={s.student_id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.4 + Math.min(i * 0.03, 0.5), duration: 0.25 }}
                    className="border-b border-zinc-50 transition-colors hover:bg-zinc-50"
                  >
                    <td className="px-6 py-3 font-mono text-zinc-600">{s.student_code}</td>
                    <td className="px-6 py-3 font-medium text-zinc-800">{s.full_name}</td>
                    <td className="px-6 py-3">
                      <span className="rounded-md bg-red-50 px-2 py-0.5 font-semibold text-red-600">
                        {s.cgpa?.toFixed(2) ?? "—"}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-zinc-500">{s.status}</td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </motion.div>
        </>
      )}
    </AdminShell>
  );
}
