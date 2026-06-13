"use client";

import { useEffect, useState } from "react";
import { Megaphone, Loader2, Send, Users, User, Lock, CheckCircle2 } from "lucide-react";
import AdminShell, { canWrite } from "@/components/AdminShell";
import { sendNotification, getRecentBroadcasts, type Announcement } from "@/lib/api";

const TYPES = ["Announcement", "Academic", "Registration", "Financial", "Reminder"];

export default function AnnouncementsPage() {
  const [target, setTarget] = useState<"all" | "student">("all");
  const [studentCode, setStudentCode] = useState("");
  const [type, setType] = useState("Announcement");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [recent, setRecent] = useState<Announcement[]>([]);
  const writable = canWrite();

  function loadRecent() {
    getRecentBroadcasts().then((r) => setRecent(r.announcements)).catch(() => {});
  }
  useEffect(loadRecent, []);

  async function send() {
    if (!subject.trim() || !message.trim()) {
      setErr("Subject and message are required");
      return;
    }
    if (target === "student" && !studentCode.trim()) {
      setErr("Enter a student code");
      return;
    }
    if (target === "all" && !confirm("Send this announcement to ALL students?")) return;

    setSending(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await sendNotification({
        subject: subject.trim(),
        message: message.trim(),
        type,
        target,
        student_code: target === "student" ? studentCode.trim() : undefined,
      });
      setMsg(`Sent to ${r.recipients} (${r.sent} recipient${r.sent === 1 ? "" : "s"}).`);
      setSubject("");
      setMessage("");
      setStudentCode("");
      loadRecent();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Send failed");
    } finally {
      setSending(false);
    }
  }

  return (
    <AdminShell>
      <h1 className="flex items-center gap-2 text-2xl font-bold text-zinc-900">
        <Megaphone size={22} className="text-[#b8001f]" /> Announcements
      </h1>
      <p className="mb-6 text-sm text-zinc-500">Send a notification to a single student or the whole student body.</p>

      {!writable && (
        <div className="mb-5 flex items-center gap-2 rounded-lg bg-zinc-100 px-4 py-2 text-sm text-zinc-600">
          <Lock size={14} /> Read-only role — sending disabled.
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Compose */}
        <div className="lg:col-span-2">
          <div className="space-y-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
            {err && <div className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">{err}</div>}
            {msg && (
              <div className="flex items-center gap-2 rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-700">
                <CheckCircle2 size={15} /> {msg}
              </div>
            )}

            {/* target */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-zinc-500">Recipients</label>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={!writable}
                  onClick={() => setTarget("all")}
                  className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium ${
                    target === "all" ? "border-[#b8001f] bg-[#b8001f]/5 text-[#b8001f]" : "border-zinc-300 text-zinc-600"
                  }`}
                >
                  <Users size={16} /> All students
                </button>
                <button
                  type="button"
                  disabled={!writable}
                  onClick={() => setTarget("student")}
                  className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium ${
                    target === "student" ? "border-[#b8001f] bg-[#b8001f]/5 text-[#b8001f]" : "border-zinc-300 text-zinc-600"
                  }`}
                >
                  <User size={16} /> Specific student
                </button>
              </div>
            </div>

            {target === "student" && (
              <Field label="Student code">
                <input disabled={!writable} value={studentCode} onChange={(e) => setStudentCode(e.target.value)} placeholder="e.g. 25100045" className="ai" />
              </Field>
            )}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Field label="Type">
                <select disabled={!writable} value={type} onChange={(e) => setType(e.target.value)} className="ai">
                  {TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
              </Field>
              <div className="sm:col-span-2">
                <Field label="Subject">
                  <input disabled={!writable} value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Short headline" className="ai" />
                </Field>
              </div>
            </div>

            <Field label="Message">
              <textarea disabled={!writable} value={message} onChange={(e) => setMessage(e.target.value)} rows={5} placeholder="Write your announcement…" className="ai resize-none" />
            </Field>

            {writable && (
              <button onClick={send} disabled={sending} className="flex items-center gap-2 rounded-lg bg-[#b8001f] px-6 py-2.5 text-sm font-semibold text-white hover:bg-[#9b0019] disabled:opacity-50">
                {sending ? <Loader2 className="animate-spin" size={16} /> : <Send size={16} />}
                {target === "all" ? "Send to all students" : "Send"}
              </button>
            )}
          </div>
        </div>

        {/* Recent */}
        <div>
          <h2 className="mb-3 text-sm font-semibold text-zinc-700">Recent announcements</h2>
          <div className="space-y-2">
            {recent.length === 0 ? (
              <div className="rounded-xl border border-dashed border-zinc-200 bg-white px-4 py-6 text-center text-sm text-zinc-400">
                Nothing sent yet.
              </div>
            ) : (
              recent.map((a, i) => (
                <div key={i} className="rounded-xl border border-zinc-200 bg-white p-3 shadow-sm">
                  <div className="text-sm font-medium text-zinc-800">{a.subject}</div>
                  <div className="mt-0.5 flex items-center gap-2 text-xs text-zinc-400">
                    <span className="rounded bg-zinc-100 px-1.5 py-0.5 font-medium text-zinc-500">{a.type}</span>
                    {a.recipients.toLocaleString()} recipient{a.recipients === 1 ? "" : "s"}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <style>{`.ai{width:100%;border:1px solid #d4d4d8;border-radius:0.5rem;padding:0.5rem 0.75rem;font-size:0.875rem;outline:none}.ai:focus{border-color:#b8001f}.ai:disabled{background:#f4f4f5;color:#71717a}`}</style>
    </AdminShell>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-zinc-500">{label}</span>
      {children}
    </label>
  );
}
