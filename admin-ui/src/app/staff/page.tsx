"use client";

import { useEffect, useState } from "react";
import { UserCog, Loader2, UserPlus, KeyRound, ShieldAlert, Check, X } from "lucide-react";
import AdminShell from "@/components/AdminShell";
import {
  listStaff,
  createStaff,
  updateStaff,
  resetStaffPassword,
  getRole,
  type StaffMember,
} from "@/lib/api";

function pretty(role: string) {
  return role.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function when(iso: string | null) {
  if (!iso) return "never";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString();
}

export default function StaffPage() {
  const [staff, setStaff] = useState<StaffMember[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  const [me, setMe] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  // create form
  const [nf, setNf] = useState({ username: "", full_name: "", email: "", role: "readonly", password: "" });
  const [creating, setCreating] = useState(false);

  const isSuperAdmin = getRole() === "super_admin";

  async function load() {
    setLoading(true);
    setErr(null);
    try {
      const d = await listStaff();
      setStaff(d.staff);
      setRoles(d.roles);
      setMe(d.me);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (isSuperAdmin) load();
    else setLoading(false);
  }, [isSuperAdmin]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (creating) return;
    setCreating(true);
    setErr(null);
    setNotice(null);
    try {
      const res = await createStaff({
        username: nf.username,
        full_name: nf.full_name,
        email: nf.email,
        role: nf.role,
        password: nf.password || undefined,
      });
      setNotice(
        res.temporary_password
          ? `Created ${res.staff.username}. Temporary password: ${res.temporary_password}`
          : `Created ${res.staff.username}.`,
      );
      setNf({ username: "", full_name: "", email: "", role: "readonly", password: "" });
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Create failed");
    } finally {
      setCreating(false);
    }
  }

  async function patch(id: number, body: { role?: string; is_active?: boolean }) {
    setBusyId(id);
    setErr(null);
    setNotice(null);
    try {
      await updateStaff(id, body);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Update failed");
    } finally {
      setBusyId(null);
    }
  }

  async function resetPw(id: number, username: string) {
    if (!confirm(`Reset password for ${username} to a temporary one?`)) return;
    setBusyId(id);
    setErr(null);
    setNotice(null);
    try {
      const res = await resetStaffPassword(id);
      setNotice(`Password for ${res.username} reset. Temporary password: ${res.temporary_password}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Reset failed");
    } finally {
      setBusyId(null);
    }
  }

  if (!isSuperAdmin) {
    return (
      <AdminShell>
        <div className="mx-auto mt-20 max-w-md rounded-2xl border border-amber-200 bg-amber-50 p-8 text-center">
          <ShieldAlert className="mx-auto mb-3 text-amber-500" size={32} />
          <h1 className="text-lg font-bold text-zinc-900">Super-admin only</h1>
          <p className="mt-1 text-sm text-zinc-600">
            Staff management is restricted to super-admin accounts.
          </p>
        </div>
      </AdminShell>
    );
  }

  return (
    <AdminShell>
      <div className="mb-1 flex items-center gap-2">
        <UserCog size={22} className="text-[#b8001f]" />
        <h1 className="text-2xl font-bold text-zinc-900">Staff management</h1>
      </div>
      <p className="mb-6 text-sm text-zinc-500">
        Create admin accounts, change roles, deactivate access, and reset passwords. Every change is audited.
      </p>

      {err && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}
      {notice && (
        <div className="mb-4 flex items-start justify-between gap-3 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <span className="font-mono">{notice}</span>
          <button onClick={() => setNotice(null)} className="text-emerald-600 hover:text-emerald-800" type="button">
            <X size={16} />
          </button>
        </div>
      )}

      {/* Create form */}
      <form onSubmit={onCreate} className="mb-8 rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-800">
          <UserPlus size={16} className="text-[#b8001f]" /> Add an admin
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <input
            value={nf.username}
            onChange={(e) => setNf({ ...nf, username: e.target.value })}
            placeholder="username"
            required
            className="h-10 rounded-lg border border-zinc-200 bg-zinc-50 px-3 text-sm outline-none focus:border-[#b8001f]"
          />
          <input
            value={nf.full_name}
            onChange={(e) => setNf({ ...nf, full_name: e.target.value })}
            placeholder="Full name"
            required
            className="h-10 rounded-lg border border-zinc-200 bg-zinc-50 px-3 text-sm outline-none focus:border-[#b8001f]"
          />
          <input
            value={nf.email}
            onChange={(e) => setNf({ ...nf, email: e.target.value })}
            placeholder="email@aiu.edu.eg"
            type="email"
            required
            className="h-10 rounded-lg border border-zinc-200 bg-zinc-50 px-3 text-sm outline-none focus:border-[#b8001f]"
          />
          <select
            value={nf.role}
            onChange={(e) => setNf({ ...nf, role: e.target.value })}
            className="h-10 rounded-lg border border-zinc-200 bg-zinc-50 px-3 text-sm outline-none focus:border-[#b8001f]"
          >
            {roles.map((r) => (
              <option key={r} value={r}>{pretty(r)}</option>
            ))}
          </select>
          <input
            value={nf.password}
            onChange={(e) => setNf({ ...nf, password: e.target.value })}
            placeholder="password (optional)"
            className="h-10 rounded-lg border border-zinc-200 bg-zinc-50 px-3 text-sm outline-none focus:border-[#b8001f]"
          />
        </div>
        <div className="mt-3 flex items-center gap-3">
          <button
            type="submit"
            disabled={creating}
            className="flex h-10 items-center gap-2 rounded-lg bg-[#b8001f] px-4 text-sm font-semibold text-white transition hover:bg-[#a0001a] disabled:opacity-60"
          >
            {creating ? <Loader2 size={15} className="animate-spin" /> : <UserPlus size={15} />}
            Create
          </button>
          <span className="text-xs text-zinc-400">Leave password blank to assign the default temporary password.</span>
        </div>
      </form>

      {/* Staff table */}
      {loading ? (
        <div className="flex items-center gap-2 text-zinc-500">
          <Loader2 className="animate-spin" size={18} /> Loading…
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-100 text-left text-xs uppercase tracking-wide text-zinc-400">
                <th className="px-4 py-3 font-medium">Username</th>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Last login</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {staff.map((s) => {
                const self = s.id === me;
                const busy = busyId === s.id;
                return (
                  <tr key={s.id} className="border-b border-zinc-50 last:border-0 hover:bg-zinc-50">
                    <td className="px-4 py-3 font-mono text-zinc-700">
                      {s.username}
                      {self && <span className="ml-1 text-[10px] font-semibold text-[#b8001f]">(you)</span>}
                    </td>
                    <td className="px-4 py-3 font-medium text-zinc-800">{s.full_name}</td>
                    <td className="px-4 py-3 text-zinc-500">{s.email}</td>
                    <td className="px-4 py-3">
                      <select
                        value={s.role}
                        disabled={self || busy}
                        onChange={(e) => patch(s.id, { role: e.target.value })}
                        className="rounded-md border border-zinc-200 bg-white px-2 py-1 text-xs disabled:opacity-50"
                        title={self ? "You cannot change your own role" : undefined}
                      >
                        {roles.map((r) => (
                          <option key={r} value={r}>{pretty(r)}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      {s.is_active ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                          <Check size={11} /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-semibold text-zinc-500">
                          <X size={11} /> Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-zinc-500">{when(s.last_login_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => patch(s.id, { is_active: !s.is_active })}
                          disabled={busy || (self && s.is_active)}
                          title={self && s.is_active ? "You cannot deactivate yourself" : undefined}
                          className={`rounded-md px-2.5 py-1 text-xs font-medium transition disabled:opacity-40 ${
                            s.is_active
                              ? "bg-red-50 text-red-600 hover:bg-red-100"
                              : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                          }`}
                          type="button"
                        >
                          {s.is_active ? "Deactivate" : "Activate"}
                        </button>
                        <button
                          onClick={() => resetPw(s.id, s.username)}
                          disabled={busy}
                          className="flex items-center gap-1 rounded-md bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-600 transition hover:bg-zinc-200 disabled:opacity-40"
                          type="button"
                        >
                          <KeyRound size={12} /> Reset
                        </button>
                        {busy && <Loader2 size={14} className="animate-spin text-zinc-400" />}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </AdminShell>
  );
}
