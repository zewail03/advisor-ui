"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2, Lock, Wallet, CreditCard, AlertTriangle, Award, Trash2, RefreshCw } from "lucide-react";
import AdminShell, { canWrite } from "@/components/AdminShell";
import {
  getFinancial,
  postPayment,
  addFine,
  grantScholarship,
  rebillFromPolicy,
  revokeScholarship,
  type FinancialAccount,
  type FinTxn,
  type ScholarshipRow,
} from "@/lib/api";

export default function FinancialPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const router = useRouter();

  const [name, setName] = useState("");
  const [account, setAccount] = useState<FinancialAccount | null>(null);
  const [txns, setTxns] = useState<FinTxn[]>([]);
  const [schols, setSchols] = useState<ScholarshipRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const writable = canWrite();

  // form fields
  const [pay, setPay] = useState({ amount: "", method: "Card" });
  const [fine, setFine] = useState({ amount: "", description: "" });
  const [sch, setSch] = useState({ type: "", amount: "", notes: "" });

  function load() {
    return getFinancial(id).then((d) => {
      setName(d.student.full_name);
      setAccount(d.account);
      setTxns(d.transactions);
      setSchols(d.scholarships);
    });
  }
  useEffect(() => {
    load().catch((e) => setErr(e instanceof Error ? e.message : "Failed")).finally(() => setLoading(false));
  }, [id]);

  async function run(fn: () => Promise<unknown>, success: string) {
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      await fn();
      await load();
      setMsg(success);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  const money = (n: number) => `${n.toLocaleString()} ${account?.currency ?? "EGP"}`;

  return (
    <AdminShell>
      <button onClick={() => router.push(`/students/${id}`)} className="mb-4 flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800">
        <ArrowLeft size={15} /> Back to student
      </button>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-zinc-900">
            <Wallet size={22} className="text-[#b8001f]" /> Financial — {name}
          </h1>
          <p className="mb-5 text-sm text-zinc-500">{account?.semester ?? "—"}</p>
        </div>
        {writable && account && (
          <button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setErr(null);
              setMsg(null);
              try {
                const r = await rebillFromPolicy(id);
                await load();
                setMsg(
                  `Rebilled: ${r.term_credits} credits × ${r.tuition_per_credit.toLocaleString()} — new balance ${r.new_balance.toLocaleString()}`,
                );
              } catch (e) {
                setErr(e instanceof Error ? e.message : "Rebill failed");
              } finally {
                setBusy(false);
              }
            }}
            className="inline-flex items-center gap-2 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 shadow-sm hover:bg-zinc-50 disabled:opacity-50"
            title="Recompute tuition & transport from enrolled credits × the live Business Rules"
          >
            <RefreshCw size={15} /> Rebill from rules
          </button>
        )}
      </div>

      {!writable && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-zinc-100 px-4 py-2 text-sm text-zinc-600">
          <Lock size={14} /> Read-only role — actions disabled.
        </div>
      )}
      {err && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}
      {msg && <div className="mb-4 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{msg}</div>}

      {loading ? (
        <div className="flex items-center gap-2 text-zinc-500"><Loader2 className="animate-spin" size={18} /> Loading…</div>
      ) : !account ? (
        <div className="rounded-lg bg-zinc-100 px-4 py-3 text-sm text-zinc-600">No financial account for this student.</div>
      ) : (
        <>
          {/* summary */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            <Stat label="Current Balance" value={money(account.current_balance)} accent={account.current_balance > 0 ? "text-red-600" : "text-emerald-600"} />
            <Stat label="Total Charges" value={money(account.total_charges)} />
            <Stat label="Scholarships" value={money(account.scholarship_credit)} />
            <Stat label="Payments Made" value={money(account.payments_made)} />
            <Stat label="Status" value={account.payment_status} accent={account.payment_status === "Paid" ? "text-emerald-600" : "text-amber-600"} />
          </div>

          {/* actions */}
          {writable && (
            <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
              <ActionCard icon={CreditCard} title="Post Payment" color="text-emerald-600">
                <input type="number" placeholder="Amount" value={pay.amount} onChange={(e) => setPay({ ...pay, amount: e.target.value })} className="fi" />
                <select value={pay.method} onChange={(e) => setPay({ ...pay, method: e.target.value })} className="fi">
                  <option>Card</option><option>Cash</option><option>Bank Transfer</option>
                </select>
                <button disabled={busy || !pay.amount} onClick={() => run(() => postPayment(id, Number(pay.amount), pay.method), "Payment posted").then(() => setPay({ amount: "", method: "Card" }))} className="fbtn bg-emerald-600 hover:bg-emerald-700">Post payment</button>
              </ActionCard>

              <ActionCard icon={AlertTriangle} title="Add Fine / Adjustment" color="text-amber-600">
                <input type="number" placeholder="Amount (− to waive)" value={fine.amount} onChange={(e) => setFine({ ...fine, amount: e.target.value })} className="fi" />
                <input placeholder="Description" value={fine.description} onChange={(e) => setFine({ ...fine, description: e.target.value })} className="fi" />
                <button disabled={busy || !fine.amount} onClick={() => run(() => addFine(id, Number(fine.amount), fine.description || "Manual adjustment"), "Adjustment posted").then(() => setFine({ amount: "", description: "" }))} className="fbtn bg-amber-600 hover:bg-amber-700">Apply</button>
              </ActionCard>

              <ActionCard icon={Award} title="Grant Scholarship" color="text-violet-600">
                <input placeholder="Type (e.g. Need-based)" value={sch.type} onChange={(e) => setSch({ ...sch, type: e.target.value })} className="fi" />
                <input type="number" placeholder="Amount" value={sch.amount} onChange={(e) => setSch({ ...sch, amount: e.target.value })} className="fi" />
                <button disabled={busy || !sch.type || !sch.amount} onClick={() => run(() => grantScholarship(id, sch.type, Number(sch.amount), sch.notes), "Scholarship granted").then(() => setSch({ type: "", amount: "", notes: "" }))} className="fbtn bg-violet-600 hover:bg-violet-700">Grant</button>
              </ActionCard>
            </div>
          )}

          {/* scholarships */}
          {schols.length > 0 && (
            <div className="mt-8 overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
              <div className="border-b border-zinc-100 px-6 py-4"><h2 className="font-semibold text-zinc-900">Scholarships</h2></div>
              <table className="w-full text-sm">
                <tbody>
                  {schols.map((s) => (
                    <tr key={s.id} className="border-b border-zinc-50">
                      <td className="px-6 py-3 font-medium text-zinc-800">{s.type}</td>
                      <td className="px-6 py-3 text-zinc-600">{money(s.amount)}</td>
                      <td className="px-6 py-3">
                        <span className={`rounded px-2 py-0.5 text-xs font-medium ${s.status === "Active" ? "bg-emerald-50 text-emerald-700" : "bg-zinc-100 text-zinc-500"}`}>{s.status}</span>
                      </td>
                      <td className="px-6 py-3 text-right">
                        {writable && s.status === "Active" && (
                          <button onClick={() => run(() => revokeScholarship(s.id), "Scholarship revoked")} className="inline-flex items-center gap-1 text-xs text-red-600 hover:underline">
                            <Trash2 size={13} /> Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* transactions */}
          <div className="mt-8 overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
            <div className="border-b border-zinc-100 px-6 py-4"><h2 className="font-semibold text-zinc-900">Transactions</h2></div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-100 text-left text-xs uppercase tracking-wide text-zinc-400">
                  <th className="px-6 py-3 font-medium">Date</th>
                  <th className="px-6 py-3 font-medium">Description</th>
                  <th className="px-6 py-3 font-medium">Category</th>
                  <th className="px-6 py-3 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody>
                {txns.map((t) => {
                  const debit = t.type === "charge" || t.type === "fine";
                  return (
                    <tr key={t.id} className="border-b border-zinc-50">
                      <td className="px-6 py-3 text-zinc-500">{t.date}</td>
                      <td className="px-6 py-3 text-zinc-800">{t.description}</td>
                      <td className="px-6 py-3 text-zinc-500">{t.category}</td>
                      <td className={`px-6 py-3 text-right font-semibold ${debit ? "text-red-600" : "text-emerald-600"}`}>
                        {debit ? "−" : "+"}{money(t.amount)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      <style>{`.fi{width:100%;border:1px solid #d4d4d8;border-radius:0.5rem;padding:0.5rem 0.75rem;font-size:0.875rem;outline:none}.fi:focus{border-color:#b8001f}.fbtn{width:100%;border-radius:0.5rem;padding:0.5rem;font-size:0.875rem;font-weight:600;color:white}.fbtn:disabled{opacity:0.5}`}</style>
    </AdminShell>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
      <div className={`text-xl font-bold ${accent ?? "text-zinc-900"}`}>{value}</div>
      <div className="text-xs font-medium text-zinc-500">{label}</div>
    </div>
  );
}

function ActionCard({ icon: Icon, title, color, children }: { icon: React.ComponentType<{ size?: number; className?: string }>; title: string; color: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2 rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
      <div className={`mb-1 flex items-center gap-2 font-semibold ${color}`}>
        <Icon size={18} /> {title}
      </div>
      {children}
    </div>
  );
}
