"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Loader2, ChevronLeft, ChevronRight } from "lucide-react";
import AdminShell from "@/components/AdminShell";
import { listStudents, type StudentRow } from "@/lib/api";

const STATUSES = ["", "Active", "Probation", "Suspended", "Dismissed", "Graduated"];
const PAGE = 25;

function statusBadge(status: string) {
  const map: Record<string, string> = {
    Active: "bg-emerald-50 text-emerald-700",
    Probation: "bg-amber-50 text-amber-700",
    Suspended: "bg-orange-50 text-orange-700",
    Dismissed: "bg-red-50 text-red-700",
    Graduated: "bg-blue-50 text-blue-700",
  };
  return map[status] || "bg-zinc-100 text-zinc-600";
}

export default function StudentsPage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<StudentRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    listStudents({ q, status, limit: PAGE, offset })
      .then((r) => {
        setRows(r.students);
        setTotal(r.total);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [q, status, offset]);

  useEffect(() => {
    const t = setTimeout(load, 250); // debounce search
    return () => clearTimeout(t);
  }, [load]);

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE, total);

  return (
    <AdminShell>
      <h1 className="mb-1 text-2xl font-bold text-zinc-900">Students</h1>
      <p className="mb-6 text-sm text-zinc-500">Search, view, and manage student records.</p>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
            placeholder="Search by code or name…"
            className="w-full rounded-lg border border-zinc-300 py-2 pl-9 pr-3 text-sm outline-none focus:border-[#b8001f]"
          />
        </div>
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setOffset(0);
          }}
          className="rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-[#b8001f]"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s || "All statuses"}
            </option>
          ))}
        </select>
      </div>

      {err && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}

      <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-100 text-left text-xs uppercase tracking-wide text-zinc-400">
              <th className="px-6 py-3 font-medium">Code</th>
              <th className="px-6 py-3 font-medium">Name</th>
              <th className="px-6 py-3 font-medium">CGPA</th>
              <th className="px-6 py-3 font-medium">Level</th>
              <th className="px-6 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-zinc-500">
                  <Loader2 className="mx-auto animate-spin" size={18} />
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-sm text-zinc-500">
                  No students match.
                </td>
              </tr>
            ) : (
              rows.map((s) => (
                <tr
                  key={s.student_id}
                  onClick={() => router.push(`/students/${s.student_id}`)}
                  className="cursor-pointer border-b border-zinc-50 hover:bg-zinc-50"
                >
                  <td className="px-6 py-3 font-mono text-zinc-600">{s.student_code}</td>
                  <td className="px-6 py-3 font-medium text-zinc-800">{s.full_name}</td>
                  <td className="px-6 py-3 text-zinc-600">{s.cgpa?.toFixed(2) ?? "—"}</td>
                  <td className="px-6 py-3 text-zinc-600">{s.level}</td>
                  <td className="px-6 py-3">
                    <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${statusBadge(s.status)}`}>
                      {s.status}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        <div className="flex items-center justify-between border-t border-zinc-100 px-6 py-3 text-sm text-zinc-500">
          <span>
            {from}–{to} of {total.toLocaleString()}
          </span>
          <div className="flex gap-1">
            <button
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE))}
              className="grid h-8 w-8 place-items-center rounded-lg border border-zinc-300 disabled:opacity-40"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              disabled={to >= total}
              onClick={() => setOffset(offset + PAGE)}
              className="grid h-8 w-8 place-items-center rounded-lg border border-zinc-300 disabled:opacity-40"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </AdminShell>
  );
}
