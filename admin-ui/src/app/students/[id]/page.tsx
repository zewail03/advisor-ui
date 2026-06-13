"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2, Save, KeyRound, Lock, GraduationCap, Wallet } from "lucide-react";
import AdminShell, { canWrite } from "@/components/AdminShell";
import {
  getStudent,
  updateStudent,
  resetStudentPassword,
  getStudentGrades,
  updateGrade,
  GRADE_LETTERS,
  type StudentRow,
  type GradeRow,
} from "@/lib/api";

const STATUSES = ["Active", "Probation", "Suspended", "Dismissed", "Graduated"];

export default function StudentDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const router = useRouter();

  const [student, setStudent] = useState<StudentRow | null>(null);
  const [form, setForm] = useState<Partial<StudentRow>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [grades, setGrades] = useState<GradeRow[]>([]);
  const [cgpa, setCgpa] = useState<number | null>(null);
  const [savingGrade, setSavingGrade] = useState<number | null>(null);
  const writable = canWrite();

  useEffect(() => {
    Promise.all([getStudent(id), getStudentGrades(id)])
      .then(([s, g]) => {
        setStudent(s);
        setForm({ full_name: s.full_name, email: s.email, phone: s.phone, status: s.status, level: s.level });
        setGrades(g.grades);
        setCgpa(g.student.cgpa);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [id]);

  async function changeGrade(g: GradeRow, letter: string) {
    if (letter === g.grade_letter) return;
    setSavingGrade(g.grade_id);
    setErr(null);
    setMsg(null);
    try {
      const r = await updateGrade(g.grade_id, letter);
      setGrades((gs) => gs.map((x) => (x.grade_id === g.grade_id ? { ...x, grade_letter: letter } : x)));
      setCgpa(r.new_cgpa);
      const delta = r.new_cgpa - r.old_cgpa;
      setMsg(
        `${g.course_code}: ${r.old_letter} → ${r.new_letter}. CGPA ${r.old_cgpa} → ${r.new_cgpa}` +
          (delta !== 0 ? ` (${delta > 0 ? "+" : ""}${delta.toFixed(3)})` : ""),
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Grade update failed");
    } finally {
      setSavingGrade(null);
    }
  }

  async function save() {
    setSaving(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await updateStudent(id, form);
      setStudent(r.student);
      setMsg(r.updated ? `Saved: ${r.changed?.join(", ")}` : "No changes to save");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function resetPw() {
    if (!confirm("Reset this student's password to the temporary default?")) return;
    setErr(null);
    setMsg(null);
    try {
      const r = await resetStudentPassword(id);
      setMsg(`Password reset. Temporary password: ${r.temporary_password}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Reset failed");
    }
  }

  return (
    <AdminShell>
      <button
        onClick={() => router.push("/students")}
        className="mb-4 flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800"
      >
        <ArrowLeft size={15} /> Back to students
      </button>

      {loading ? (
        <div className="flex items-center gap-2 text-zinc-500">
          <Loader2 className="animate-spin" size={18} /> Loading…
        </div>
      ) : !student ? (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err || "Not found"}</div>
      ) : (
        <div className="max-w-3xl">
          <div className="mb-6 flex items-center justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold text-zinc-900">{student.full_name}</h1>
              <p className="font-mono text-sm text-zinc-500">
                {student.student_code} · {student.program_name ?? "—"} · CGPA{" "}
                <span className="font-semibold text-zinc-700">{cgpa?.toFixed(3) ?? "—"}</span>
              </p>
            </div>
            <button
              onClick={() => router.push(`/students/${id}/financial`)}
              className="flex items-center gap-2 rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
            >
              <Wallet size={16} /> Financial
            </button>
          </div>

          {!writable && (
            <div className="mb-4 flex items-center gap-2 rounded-lg bg-zinc-100 px-4 py-2 text-sm text-zinc-600">
              <Lock size={14} /> Read-only role — editing disabled.
            </div>
          )}
          {err && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}
          {msg && <div className="mb-4 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{msg}</div>}

          <div className="grid grid-cols-1 gap-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm sm:grid-cols-2">
            <Field label="Full name">
              <input
                disabled={!writable}
                value={form.full_name ?? ""}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                className="input"
              />
            </Field>
            <Field label="Email">
              <input
                disabled={!writable}
                value={form.email ?? ""}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="input"
              />
            </Field>
            <Field label="Phone">
              <input
                disabled={!writable}
                value={form.phone ?? ""}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                className="input"
              />
            </Field>
            <Field label="Academic level">
              <input
                type="number"
                disabled={!writable}
                value={form.level ?? 1}
                onChange={(e) => setForm({ ...form, level: Number(e.target.value) })}
                className="input"
              />
            </Field>
            <Field label="Status">
              <select
                disabled={!writable}
                value={form.status ?? "Active"}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
                className="input"
              >
                {STATUSES.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </Field>
          </div>

          {writable && (
            <div className="mt-5 flex flex-wrap gap-3">
              <button
                onClick={save}
                disabled={saving}
                className="flex items-center gap-2 rounded-lg bg-[#b8001f] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#9b0019] disabled:opacity-50"
              >
                {saving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
                Save changes
              </button>
              <button
                onClick={resetPw}
                className="flex items-center gap-2 rounded-lg border border-zinc-300 px-5 py-2.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
              >
                <KeyRound size={16} /> Reset password
              </button>
            </div>
          )}

          {/* Grades */}
          <div className="mt-8 overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
            <div className="flex items-center gap-2 border-b border-zinc-100 px-6 py-4">
              <GraduationCap size={18} className="text-[#b8001f]" />
              <h2 className="font-semibold text-zinc-900">Grades</h2>
              <span className="ml-auto text-xs text-zinc-400">
                {grades.length} courses · editing recomputes CGPA
              </span>
            </div>
            {grades.length === 0 ? (
              <div className="px-6 py-8 text-center text-sm text-zinc-500">No graded courses.</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-100 text-left text-xs uppercase tracking-wide text-zinc-400">
                    <th className="px-6 py-3 font-medium">Course</th>
                    <th className="px-6 py-3 font-medium">Semester</th>
                    <th className="px-6 py-3 font-medium">Cr</th>
                    <th className="px-6 py-3 font-medium">Pts</th>
                    <th className="px-6 py-3 font-medium">Grade</th>
                  </tr>
                </thead>
                <tbody>
                  {grades.map((g) => (
                    <tr key={g.grade_id} className="border-b border-zinc-50 hover:bg-zinc-50">
                      <td className="px-6 py-3">
                        <div className="font-medium text-zinc-800">{g.course_code}</div>
                        <div className="text-xs text-zinc-400">{g.course_title}</div>
                      </td>
                      <td className="px-6 py-3 text-zinc-500">{g.semester}</td>
                      <td className="px-6 py-3 text-zinc-600">{g.credits}</td>
                      <td className="px-6 py-3 text-zinc-600">{g.grade_points ?? "—"}</td>
                      <td className="px-6 py-3">
                        <div className="flex items-center gap-2">
                          <select
                            disabled={!writable || savingGrade === g.grade_id}
                            value={g.grade_letter ?? ""}
                            onChange={(e) => changeGrade(g, e.target.value)}
                            className="rounded-lg border border-zinc-300 px-2 py-1 text-sm font-semibold outline-none focus:border-[#b8001f] disabled:bg-zinc-50 disabled:text-zinc-500"
                          >
                            {GRADE_LETTERS.map((l) => (
                              <option key={l} value={l}>
                                {l}
                              </option>
                            ))}
                          </select>
                          {savingGrade === g.grade_id && (
                            <Loader2 size={14} className="animate-spin text-zinc-400" />
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      <style>{`.input{width:100%;border:1px solid #d4d4d8;border-radius:0.5rem;padding:0.5rem 0.75rem;font-size:0.875rem;outline:none}.input:focus{border-color:#b8001f}.input:disabled{background:#f4f4f5;color:#71717a}`}</style>
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
