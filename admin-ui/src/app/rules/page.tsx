"use client";

import { useEffect, useState } from "react";
import { Loader2, SlidersHorizontal, Lock, RotateCcw, Check } from "lucide-react";
import AdminShell from "@/components/AdminShell";
import { getPolicies, updatePolicy, type Policy } from "@/lib/api";

export default function RulesPage() {
  const [categories, setCategories] = useState<{ name: string; policies: Policy[] }[]>([]);
  const [canEdit, setCanEdit] = useState(false);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [savedKey, setSavedKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  function load() {
    setLoading(true);
    getPolicies()
      .then((r) => {
        setCategories(r.categories);
        setCanEdit(r.can_edit);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  async function save(p: Policy) {
    const raw = edits[p.key];
    const value = Number(raw);
    if (raw === undefined || Number.isNaN(value)) return;
    setSavingKey(p.key);
    setErr(null);
    try {
      const r = await updatePolicy(p.key, value);
      // update in place
      setCategories((cats) =>
        cats.map((c) => ({
          ...c,
          policies: c.policies.map((pp) =>
            pp.key === p.key ? { ...pp, value: r.new, is_overridden: true } : pp,
          ),
        })),
      );
      setEdits((e) => {
        const n = { ...e };
        delete n[p.key];
        return n;
      });
      setSavedKey(p.key);
      setTimeout(() => setSavedKey(null), 1800);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSavingKey(null);
    }
  }

  return (
    <AdminShell>
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-zinc-900">
            <SlidersHorizontal size={22} className="text-[#b8001f]" /> Business Rules
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            These thresholds drive eligibility, billing, and standing across the whole system —
            changes take effect immediately.
          </p>
        </div>
      </div>

      {!canEdit && (
        <div className="mb-5 flex items-center gap-2 rounded-lg bg-zinc-100 px-4 py-2 text-sm text-zinc-600">
          <Lock size={14} /> Viewing only — your role can&apos;t change rules. (super-admin required)
        </div>
      )}
      {err && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}

      {loading ? (
        <div className="flex items-center gap-2 text-zinc-500">
          <Loader2 className="animate-spin" size={18} /> Loading…
        </div>
      ) : (
        <div className="space-y-6">
          {categories.map((cat) => (
            <section key={cat.name} className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
              <div className="border-b border-zinc-100 px-6 py-3">
                <h2 className="font-semibold text-zinc-900">{cat.name}</h2>
              </div>
              <div className="divide-y divide-zinc-50">
                {cat.policies.map((p) => {
                  const editing = edits[p.key];
                  const current = editing !== undefined ? editing : String(p.value);
                  const dirty = editing !== undefined && Number(editing) !== p.value;
                  return (
                    <div key={p.key} className="flex flex-wrap items-center gap-4 px-6 py-4">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-zinc-800">{p.label}</span>
                          {p.is_overridden && (
                            <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">
                              MODIFIED
                            </span>
                          )}
                          {p.enforced === false && (
                            <span
                              title="Defined but not consumed by any live rule yet (no data for this feature in the current dataset)"
                              className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] font-semibold text-zinc-500"
                            >
                              NOT YET ENFORCED
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-zinc-500">{p.description}</div>
                        <div className="mt-0.5 font-mono text-[11px] text-zinc-400">
                          {p.key} · default {p.default}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <input
                          type="number"
                          step="any"
                          disabled={!canEdit}
                          value={current}
                          onChange={(e) => setEdits({ ...edits, [p.key]: e.target.value })}
                          className="w-24 rounded-lg border border-zinc-300 px-3 py-1.5 text-right text-sm outline-none focus:border-[#b8001f] disabled:bg-zinc-50 disabled:text-zinc-500"
                        />
                        <span className="w-16 text-xs text-zinc-400">{p.unit}</span>
                        {canEdit && (
                          <button
                            onClick={() => save(p)}
                            disabled={!dirty || savingKey === p.key}
                            className="flex h-8 w-20 items-center justify-center gap-1 rounded-lg bg-[#b8001f] text-xs font-semibold text-white transition hover:bg-[#9b0019] disabled:bg-zinc-200 disabled:text-zinc-400"
                          >
                            {savingKey === p.key ? (
                              <Loader2 size={13} className="animate-spin" />
                            ) : savedKey === p.key ? (
                              <>
                                <Check size={13} /> Saved
                              </>
                            ) : (
                              "Save"
                            )}
                          </button>
                        )}
                        {canEdit && p.is_overridden && p.value !== p.default && (
                          <button
                            title={`Reset to default (${p.default})`}
                            onClick={() => {
                              setEdits({ ...edits, [p.key]: String(p.default) });
                            }}
                            className="grid h-8 w-8 place-items-center rounded-lg border border-zinc-200 text-zinc-400 hover:text-zinc-700"
                          >
                            <RotateCcw size={13} />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
    </AdminShell>
  );
}
