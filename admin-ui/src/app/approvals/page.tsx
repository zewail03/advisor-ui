"use client";

import { useEffect, useState } from "react";
import { Loader2, Check, X, Inbox, FileText, UserCog, Lock } from "lucide-react";
import AdminShell, { canWrite } from "@/components/AdminShell";
import {
  getPetitions,
  decidePetition,
  getAdvisorApprovals,
  decideAdvisorApproval,
  type Petition,
  type AdvisorApprovalItem,
} from "@/lib/api";

function prettyType(t: string) {
  return t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function ApprovalsPage() {
  const [petitions, setPetitions] = useState<Petition[]>([]);
  const [approvals, setApprovals] = useState<AdvisorApprovalItem[]>([]);
  const [comments, setComments] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const writable = canWrite();

  function load() {
    setLoading(true);
    Promise.all([getPetitions("submitted"), getAdvisorApprovals("pending")])
      .then(([p, a]) => {
        setPetitions(p.petitions);
        setApprovals(a.approvals);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  function flash(m: string) {
    setToast(m);
    setTimeout(() => setToast(null), 2500);
  }

  async function decideP(p: Petition, approve: boolean) {
    setBusy(p.id);
    setErr(null);
    try {
      await decidePetition(p.id, approve, comments[p.id]);
      setPetitions((xs) => xs.filter((x) => x.id !== p.id));
      flash(`Petition ${approve ? "approved" : "rejected"} — ${p.student_name}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  }

  async function decideA(a: AdvisorApprovalItem, approve: boolean) {
    setBusy(a.id);
    setErr(null);
    try {
      await decideAdvisorApproval(a.id, approve, comments[a.id]);
      setApprovals((xs) => xs.filter((x) => x.id !== a.id));
      flash(`Approval ${approve ? "approved" : "rejected"} — ${a.student_name}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <AdminShell>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-zinc-900">
            <Inbox size={22} className="text-[#b8001f]" /> Approvals
          </h1>
          <p className="mt-1 text-sm text-zinc-500">Review student petitions and advisor-approval requests.</p>
        </div>
        {toast && (
          <div className="rounded-lg bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700">{toast}</div>
        )}
      </div>

      {!writable && (
        <div className="mb-5 flex items-center gap-2 rounded-lg bg-zinc-100 px-4 py-2 text-sm text-zinc-600">
          <Lock size={14} /> Read-only role — you can view queues but not decide.
        </div>
      )}
      {err && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}

      {loading ? (
        <div className="flex items-center gap-2 text-zinc-500">
          <Loader2 className="animate-spin" size={18} /> Loading…
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Petitions */}
          <section>
            <h2 className="mb-3 flex items-center gap-2 font-semibold text-zinc-800">
              <FileText size={18} className="text-zinc-500" /> Petitions
              <span className="rounded-full bg-[#b8001f]/10 px-2 py-0.5 text-xs font-bold text-[#b8001f]">
                {petitions.length}
              </span>
            </h2>
            <div className="space-y-3">
              {petitions.length === 0 ? (
                <Empty label="No pending petitions." />
              ) : (
                petitions.map((p) => (
                  <Card
                    key={p.id}
                    badge={prettyType(p.type)}
                    title={p.subject}
                    who={`${p.student_name} · ${p.student_code}`}
                    detail={
                      p.type === "grade_appeal" && p.current_grade
                        ? `Grade: ${p.current_grade} → ${p.requested_grade}`
                        : p.semester_code
                        ? `Semester: ${p.semester_code}`
                        : p.body || ""
                    }
                    comment={comments[p.id] || ""}
                    onComment={(v) => setComments({ ...comments, [p.id]: v })}
                    busy={busy === p.id}
                    writable={writable}
                    onApprove={() => decideP(p, true)}
                    onReject={() => decideP(p, false)}
                  />
                ))
              )}
            </div>
          </section>

          {/* Advisor approvals */}
          <section>
            <h2 className="mb-3 flex items-center gap-2 font-semibold text-zinc-800">
              <UserCog size={18} className="text-zinc-500" /> Advisor Approvals
              <span className="rounded-full bg-[#b8001f]/10 px-2 py-0.5 text-xs font-bold text-[#b8001f]">
                {approvals.length}
              </span>
            </h2>
            <div className="space-y-3">
              {approvals.length === 0 ? (
                <Empty label="No pending advisor approvals." />
              ) : (
                approvals.map((a) => (
                  <Card
                    key={a.id}
                    badge={prettyType(a.type)}
                    title={a.justification || prettyType(a.type)}
                    who={`${a.student_name} · ${a.student_code}`}
                    detail={a.semester_code ? `Semester: ${a.semester_code}` : ""}
                    comment={comments[a.id] || ""}
                    onComment={(v) => setComments({ ...comments, [a.id]: v })}
                    busy={busy === a.id}
                    writable={writable}
                    onApprove={() => decideA(a, true)}
                    onReject={() => decideA(a, false)}
                  />
                ))
              )}
            </div>
          </section>
        </div>
      )}
    </AdminShell>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-zinc-200 bg-white px-6 py-8 text-center text-sm text-zinc-400">
      {label}
    </div>
  );
}

function Card(props: {
  badge: string;
  title: string;
  who: string;
  detail: string;
  comment: string;
  onComment: (v: string) => void;
  busy: boolean;
  writable: boolean;
  onApprove: () => void;
  onReject: () => void;
}) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-start justify-between gap-2">
        <span className="rounded-md bg-zinc-100 px-2 py-0.5 text-xs font-semibold text-zinc-600">
          {props.badge}
        </span>
        <span className="text-xs text-zinc-400">{props.who}</span>
      </div>
      <div className="font-medium text-zinc-800">{props.title}</div>
      {props.detail && <div className="mt-0.5 text-sm text-zinc-500">{props.detail}</div>}
      {props.writable && (
        <div className="mt-3 flex items-center gap-2">
          <input
            value={props.comment}
            onChange={(e) => props.onComment(e.target.value)}
            placeholder="Decision note (optional)"
            className="flex-1 rounded-lg border border-zinc-300 px-3 py-1.5 text-sm outline-none focus:border-[#b8001f]"
          />
          <button
            onClick={props.onApprove}
            disabled={props.busy}
            className="flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {props.busy ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} Approve
          </button>
          <button
            onClick={props.onReject}
            disabled={props.busy}
            className="flex items-center gap-1 rounded-lg border border-red-200 px-3 py-1.5 text-sm font-semibold text-red-600 hover:bg-red-50 disabled:opacity-50"
          >
            <X size={14} /> Reject
          </button>
        </div>
      )}
    </div>
  );
}
