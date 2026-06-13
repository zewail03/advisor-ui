"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Loader2, ChevronLeft, ChevronRight } from "lucide-react";
import AdminShell from "@/components/AdminShell";
import { listCourses, type CourseRow } from "@/lib/api";

const PAGE = 25;

export default function CoursesPage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<CourseRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    listCourses({ q, limit: PAGE, offset })
      .then((r) => {
        setRows(r.courses);
        setTotal(r.total);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [q, offset]);

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [load]);

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE, total);

  return (
    <AdminShell>
      <h1 className="mb-1 text-2xl font-bold text-zinc-900">Courses</h1>
      <p className="mb-6 text-sm text-zinc-500">Catalog and section offerings.</p>

      <div className="relative mb-4 max-w-md">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOffset(0);
          }}
          placeholder="Search by code or title…"
          className="w-full rounded-lg border border-zinc-300 py-2 pl-9 pr-3 text-sm outline-none focus:border-[#b8001f]"
        />
      </div>

      {err && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}

      <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-100 text-left text-xs uppercase tracking-wide text-zinc-400">
              <th className="px-6 py-3 font-medium">Code</th>
              <th className="px-6 py-3 font-medium">Title</th>
              <th className="px-6 py-3 font-medium">Credits</th>
              <th className="px-6 py-3 font-medium">Major</th>
              <th className="px-6 py-3 font-medium">Sections</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center">
                  <Loader2 className="mx-auto animate-spin text-zinc-400" size={18} />
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-sm text-zinc-500">
                  No courses match.
                </td>
              </tr>
            ) : (
              rows.map((c) => (
                <tr
                  key={c.course_id}
                  onClick={() => router.push(`/courses/${c.course_id}`)}
                  className="cursor-pointer border-b border-zinc-50 hover:bg-zinc-50"
                >
                  <td className="px-6 py-3 font-mono font-semibold text-zinc-700">{c.code}</td>
                  <td className="px-6 py-3 text-zinc-800">{c.name}</td>
                  <td className="px-6 py-3 text-zinc-600">{c.credits}</td>
                  <td className="px-6 py-3 text-zinc-500">{c.major_code ?? "—"}</td>
                  <td className="px-6 py-3 text-zinc-600">{c.sections}</td>
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
