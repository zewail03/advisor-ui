"use client";

import { useEffect, useState } from "react";
import { Loader2, ScrollText, RefreshCw } from "lucide-react";
import AdminShell from "@/components/AdminShell";
import { getAudit, type AuditEvent } from "@/lib/api";

function actionColor(action: string) {
  if (action.includes("reset_password")) return "bg-orange-50 text-orange-700";
  if (action.includes("update") || action.includes("decide")) return "bg-amber-50 text-amber-700";
  if (action.includes("login")) return "bg-blue-50 text-blue-700";
  if (action.includes("delete")) return "bg-red-50 text-red-700";
  return "bg-zinc-100 text-zinc-600";
}

function fmt(ts: string) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function diff(before: string | null, after: string | null): string {
  const b = before ? safe(before) : null;
  const a = after ? safe(after) : null;
  if (!a) return "—";
  if (!b) return Object.entries(a).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(", ");
  return Object.keys(a)
    .map((k) => `${k}: ${JSON.stringify(b[k])} → ${JSON.stringify(a[k])}`)
    .join(", ");
}
function safe(s: string): Record<string, unknown> {
  try {
    return JSON.parse(s);
  } catch {
    return {};
  }
}

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  function load() {
    setLoading(true);
    getAudit({ limit: 100 })
      .then((r) => setEvents(r.events))
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  return (
    <AdminShell>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-900">Audit Trail</h1>
          <p className="text-sm text-zinc-500">Every administrative action, recorded immutably.</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 rounded-lg border border-zinc-300 px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50"
        >
          <RefreshCw size={15} /> Refresh
        </button>
      </div>

      {err && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}

      <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-100 text-left text-xs uppercase tracking-wide text-zinc-400">
              <th className="px-6 py-3 font-medium">When</th>
              <th className="px-6 py-3 font-medium">Action</th>
              <th className="px-6 py-3 font-medium">Target</th>
              <th className="px-6 py-3 font-medium">Actor</th>
              <th className="px-6 py-3 font-medium">Change</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center">
                  <Loader2 className="mx-auto animate-spin text-zinc-400" size={18} />
                </td>
              </tr>
            ) : events.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-10 text-center text-sm text-zinc-500">
                  <ScrollText className="mx-auto mb-2 text-zinc-300" size={28} />
                  No audit events yet. Actions you take in the portal will appear here.
                </td>
              </tr>
            ) : (
              events.map((e) => (
                <tr key={e.id} className="border-b border-zinc-50 align-top hover:bg-zinc-50">
                  <td className="whitespace-nowrap px-6 py-3 text-zinc-500">{fmt(e.occurred_at)}</td>
                  <td className="px-6 py-3">
                    <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${actionColor(e.action)}`}>
                      {e.action}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-zinc-600">
                    {e.entity_type}
                    {e.entity_id ? ` #${e.entity_id}` : ""}
                  </td>
                  <td className="px-6 py-3 text-zinc-600">
                    <span className="capitalize">{(e.actor_role ?? "—").replace("_", " ")}</span>
                    {e.actor_id ? <span className="text-zinc-400"> #{e.actor_id}</span> : null}
                  </td>
                  <td className="max-w-xs px-6 py-3 text-xs text-zinc-500">{diff(e.before, e.after)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </AdminShell>
  );
}
