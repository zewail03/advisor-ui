"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2, Save, Lock, Plus, BookOpen } from "lucide-react";
import AdminShell, { canWrite } from "@/components/AdminShell";
import {
  getCourse,
  updateCourse,
  updateSection,
  createSection,
  getSemesters,
  type CourseDetail,
  type SectionRow,
} from "@/lib/api";

const SECTION_STATUS = ["Open", "Closed", "Cancelled"];

export default function CourseDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const router = useRouter();

  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [form, setForm] = useState<Partial<CourseDetail>>({});
  const [sections, setSections] = useState<SectionRow[]>([]);
  const [secEdits, setSecEdits] = useState<Record<number, Partial<SectionRow>>>({});
  const [semesters, setSemesters] = useState<{ semester_id: number; code: string }[]>([]);
  const [newSec, setNewSec] = useState({ semester_id: 0, section_number: "", instructor_name: "", capacity: 30 });
  const [loading, setLoading] = useState(true);
  const [savingCourse, setSavingCourse] = useState(false);
  const [savingSec, setSavingSec] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const writable = canWrite();

  function reload() {
    return getCourse(id).then((c) => {
      setCourse(c);
      setForm({ name: c.name, credits: c.credits, major_code: c.major_code, description: c.description });
      setSections(c.sections);
      setSecEdits({});
    });
  }

  useEffect(() => {
    Promise.all([reload(), getSemesters().then((s) => setSemesters(s.semesters))])
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [id]);

  async function saveCourse() {
    setSavingCourse(true);
    setErr(null);
    setMsg(null);
    try {
      const r = await updateCourse(id, form);
      setMsg(r.updated ? `Course saved: ${r.changed?.join(", ")}` : "No changes");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSavingCourse(false);
    }
  }

  async function saveSection(s: SectionRow) {
    const patch = secEdits[s.section_id];
    if (!patch || Object.keys(patch).length === 0) return;
    setSavingSec(s.section_id);
    setErr(null);
    setMsg(null);
    try {
      await updateSection(s.section_id, patch);
      setSections((xs) => xs.map((x) => (x.section_id === s.section_id ? { ...x, ...patch } : x)));
      setSecEdits((e) => {
        const n = { ...e };
        delete n[s.section_id];
        return n;
      });
      setMsg(`Section ${s.section_number} updated`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Section save failed");
    } finally {
      setSavingSec(null);
    }
  }

  async function addSection() {
    if (!newSec.semester_id || !newSec.section_number.trim()) {
      setErr("Pick a semester and enter a section number");
      return;
    }
    setAdding(true);
    setErr(null);
    setMsg(null);
    try {
      await createSection(id, { ...newSec, instructor_name: newSec.instructor_name || undefined });
      setNewSec({ semester_id: 0, section_number: "", instructor_name: "", capacity: 30 });
      await reload();
      setMsg("Section created");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Create failed");
    } finally {
      setAdding(false);
    }
  }

  function secVal<K extends keyof SectionRow>(s: SectionRow, key: K): SectionRow[K] {
    const e = secEdits[s.section_id];
    return e && key in e ? (e[key] as SectionRow[K]) : s[key];
  }
  function editSec(id: number, patch: Partial<SectionRow>) {
    setSecEdits((e) => ({ ...e, [id]: { ...e[id], ...patch } }));
  }

  return (
    <AdminShell>
      <button onClick={() => router.push("/courses")} className="mb-4 flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800">
        <ArrowLeft size={15} /> Back to courses
      </button>

      {loading ? (
        <div className="flex items-center gap-2 text-zinc-500">
          <Loader2 className="animate-spin" size={18} /> Loading…
        </div>
      ) : !course ? (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err || "Not found"}</div>
      ) : (
        <div className="max-w-4xl">
          <h1 className="flex items-center gap-2 text-2xl font-bold text-zinc-900">
            <span className="font-mono">{course.code}</span> {course.name}
          </h1>
          <p className="mb-5 text-sm text-zinc-500">{course.credits} credits · {course.sections.length} sections</p>

          {!writable && (
            <div className="mb-4 flex items-center gap-2 rounded-lg bg-zinc-100 px-4 py-2 text-sm text-zinc-600">
              <Lock size={14} /> Read-only role — editing disabled.
            </div>
          )}
          {err && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}
          {msg && <div className="mb-4 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{msg}</div>}

          {/* course fields */}
          <div className="grid grid-cols-1 gap-4 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm sm:grid-cols-2">
            <Field label="Title">
              <input disabled={!writable} value={form.name ?? ""} onChange={(e) => setForm({ ...form, name: e.target.value })} className="ci" />
            </Field>
            <Field label="Credits">
              <input type="number" disabled={!writable} value={form.credits ?? 0} onChange={(e) => setForm({ ...form, credits: Number(e.target.value) })} className="ci" />
            </Field>
            <Field label="Major code">
              <input disabled={!writable} value={form.major_code ?? ""} onChange={(e) => setForm({ ...form, major_code: e.target.value })} className="ci" />
            </Field>
            <Field label="Description">
              <input disabled={!writable} value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} className="ci" />
            </Field>
          </div>
          {writable && (
            <button onClick={saveCourse} disabled={savingCourse} className="mt-4 flex items-center gap-2 rounded-lg bg-[#b8001f] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#9b0019] disabled:opacity-50">
              {savingCourse ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />} Save course
            </button>
          )}

          {/* sections */}
          <div className="mt-8 overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
            <div className="flex items-center gap-2 border-b border-zinc-100 px-6 py-4">
              <BookOpen size={18} className="text-[#b8001f]" />
              <h2 className="font-semibold text-zinc-900">Sections</h2>
              <span className="ml-auto text-xs text-zinc-400">{sections.length} offerings</span>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-100 text-left text-xs uppercase tracking-wide text-zinc-400">
                  <th className="px-4 py-3 font-medium">Sec</th>
                  <th className="px-4 py-3 font-medium">Semester</th>
                  <th className="px-4 py-3 font-medium">Instructor</th>
                  <th className="px-4 py-3 font-medium">Enr/Cap</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  {writable && <th className="px-4 py-3" />}
                </tr>
              </thead>
              <tbody>
                {sections.map((s) => {
                  const dirty = !!secEdits[s.section_id] && Object.keys(secEdits[s.section_id]).length > 0;
                  return (
                    <tr key={s.section_id} className="border-b border-zinc-50">
                      <td className="px-4 py-2 font-mono text-zinc-600">{s.section_number}</td>
                      <td className="px-4 py-2 text-zinc-500">{s.semester}</td>
                      <td className="px-4 py-2">
                        <input disabled={!writable} value={secVal(s, "instructor_name") ?? ""} onChange={(e) => editSec(s.section_id, { instructor_name: e.target.value })} className="ci !py-1 w-44" />
                      </td>
                      <td className="px-4 py-2">
                        <span className={s.enrolled > s.capacity ? "font-semibold text-red-600" : "text-zinc-600"}>{s.enrolled}</span>
                        <span className="text-zinc-400"> / </span>
                        <input type="number" disabled={!writable} value={secVal(s, "capacity") ?? 0} onChange={(e) => editSec(s.section_id, { capacity: Number(e.target.value) })} className="ci !py-1 w-16" />
                      </td>
                      <td className="px-4 py-2">
                        <select disabled={!writable} value={secVal(s, "status") ?? "Open"} onChange={(e) => editSec(s.section_id, { status: e.target.value })} className="ci !py-1">
                          {SECTION_STATUS.map((st) => <option key={st}>{st}</option>)}
                        </select>
                      </td>
                      {writable && (
                        <td className="px-4 py-2">
                          <button onClick={() => saveSection(s)} disabled={!dirty || savingSec === s.section_id} className="rounded-lg bg-[#b8001f] px-3 py-1 text-xs font-semibold text-white disabled:bg-zinc-200 disabled:text-zinc-400">
                            {savingSec === s.section_id ? "…" : "Save"}
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {writable && (
              <div className="flex flex-wrap items-end gap-2 border-t border-zinc-100 bg-zinc-50/60 px-4 py-3">
                <select value={newSec.semester_id} onChange={(e) => setNewSec({ ...newSec, semester_id: Number(e.target.value) })} className="ci !py-1.5">
                  <option value={0}>Semester…</option>
                  {semesters.map((s) => <option key={s.semester_id} value={s.semester_id}>{s.code}</option>)}
                </select>
                <input placeholder="Section #" value={newSec.section_number} onChange={(e) => setNewSec({ ...newSec, section_number: e.target.value })} className="ci !py-1.5 w-28" />
                <input placeholder="Instructor" value={newSec.instructor_name} onChange={(e) => setNewSec({ ...newSec, instructor_name: e.target.value })} className="ci !py-1.5 w-40" />
                <input type="number" placeholder="Cap" value={newSec.capacity} onChange={(e) => setNewSec({ ...newSec, capacity: Number(e.target.value) })} className="ci !py-1.5 w-20" />
                <button onClick={addSection} disabled={adding} className="flex items-center gap-1 rounded-lg border border-[#b8001f] px-3 py-1.5 text-sm font-semibold text-[#b8001f] hover:bg-[#b8001f]/5 disabled:opacity-50">
                  {adding ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />} Add section
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      <style>{`.ci{width:100%;border:1px solid #d4d4d8;border-radius:0.5rem;padding:0.5rem 0.75rem;font-size:0.875rem;outline:none}.ci:focus{border-color:#b8001f}.ci:disabled{background:#f4f4f5;color:#71717a}`}</style>
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
