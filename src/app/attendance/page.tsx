"use client";

import { useEffect, useState } from "react";
import AppLayout from "@/components/layout/AppLayout";
import { useLanguage } from "@/hooks/useLanguage";
import { useAuth } from "@/hooks/useAuth";
import { getMyAttendance } from "@/lib/api";

export default function AttendancePage() {
  const { t } = useLanguage();
  const { token } = useAuth();
  const [records, setRecords] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    getMyAttendance(token)
      .then((r) => setRecords(r.records))
      .catch((e) => setErr(e.message));
  }, [token]);

  return (
    <AppLayout activePath="/attendance" userName="Attendance">
      <main className="px-4 md:px-8 lg:px-16 py-8 space-y-6">
        <header>
          <h1 className="text-3xl font-bold">{t("att.title")}</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Warnings fire at 10% / 15% / 25%. Reaching 25% triggers an automatic Force Withdrawal.
          </p>
        </header>

        {err && <div className="rounded-lg bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 px-3 py-2 text-sm">{err}</div>}

        {records.length === 0 ? (
          <div className="text-sm text-zinc-500 dark:text-zinc-400">{t("att.none")}</div>
        ) : (
          <div className="space-y-3">
            {records.map((r) => (
              <AttendanceRow key={r.enrollment_id} r={r} />
            ))}
          </div>
        )}
      </main>
    </AppLayout>
  );
}

function AttendanceRow({ r }: { r: any }) {
  const { t } = useLanguage();
  const pct = Number(r.absence_pct || 0);
  const color =
    pct >= 25 ? "bg-red-500" :
    pct >= 15 ? "bg-amber-500" :
    pct >= 10 ? "bg-yellow-500" :
    "bg-emerald-500";

  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-700 dark:border-zinc-800 p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-medium">{r.course_code} — {r.course_title}</div>
          <div className="text-xs text-zinc-500 dark:text-zinc-400">
            {r.semester_code} · {r.status}
            {r.fw_triggered && <span className="ml-2 text-red-600 dark:text-red-400 font-medium">{t("att.fw")}</span>}
          </div>
        </div>
        <div className="text-right">
          <div className="text-xl font-bold">{pct.toFixed(1)}%</div>
          <div className="text-xs text-zinc-500 dark:text-zinc-400">
            {r.absent_hours}/{r.total_hours} hrs
          </div>
        </div>
      </div>
      <div className="mt-3 h-2 rounded-full bg-zinc-200 dark:bg-zinc-700 dark:bg-zinc-800 overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
    </div>
  );
}
