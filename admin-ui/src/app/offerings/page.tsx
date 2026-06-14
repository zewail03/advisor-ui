"use client";

import { useEffect, useState } from "react";
import { CalendarDays, Loader2, Plus, Trash2, X, Lock, BookOpen } from "lucide-react";
import AdminShell, { canWrite } from "@/components/AdminShell";
import {
  getSemesters,
  getCourseOptions,
  getOfferings,
  getRooms,
  createSemester,
  createOffering,
  deleteOffering,
  type Offering,
  type Meeting,
  type Room,
} from "@/lib/api";

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MTYPES = ["Lecture", "Lab", "Tutorial"];
const STATUS = ["Open", "Closed", "Cancelled"];

const blankMeeting = (): Meeting => ({ meeting_type: "Lecture", day_of_week: "Sunday", start_time: "09:00", end_time: "11:00", location: "" });

export default function OfferingsPage() {
  const [semesters, setSemesters] = useState<{ semester_id: number; code: string }[]>([]);
  const [sem, setSem] = useState<number | null>(null);
  const [offerings, setOfferings] = useState<Offering[]>([]);
  const [courses, setCourses] = useState<{ course_id: number; code: string; name: string }[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const writable = canWrite();

  // new semester
  const [newSem, setNewSem] = useState("");
  const [creatingSem, setCreatingSem] = useState(false);

  // add offering form
  const [form, setForm] = useState({ course_id: 0, section_number: "", instructor_name: "", capacity: 30, status: "Open" });
  const [meetings, setMeetings] = useState<Meeting[]>([blankMeeting()]);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    Promise.all([getSemesters(), getCourseOptions(), getRooms()])
      .then(([s, c, r]) => {
        setSemesters(s.semesters);
        setCourses(c.courses);
        setRooms(r.rooms);
        if (s.semesters.length) setSem(s.semesters[0].semester_id);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : "Failed"))
      .finally(() => setLoading(false));
  }, []);

  const labRooms = rooms.filter((r) => r.room_type === "lab");
  const lectureRooms = rooms.filter((r) => r.room_type !== "lab");

  function loadOfferings(id: number) {
    getOfferings(id).then((d) => setOfferings(d.offerings)).catch((e) => setErr(e instanceof Error ? e.message : "Failed"));
  }
  useEffect(() => {
    if (sem) loadOfferings(sem);
  }, [sem]);

  async function makeSemester() {
    if (!newSem.trim()) return;
    setCreatingSem(true);
    setErr(null);
    try {
      const r = await createSemester({ code: newSem.trim() });
      const next = [{ semester_id: r.semester_id, code: r.code }, ...semesters];
      setSemesters(next);
      setSem(r.semester_id);
      setNewSem("");
      setMsg(`Created ${r.code}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setCreatingSem(false);
    }
  }

  async function submit() {
    if (!sem || !form.course_id || !form.section_number.trim()) {
      setErr("Pick a course and enter a section number");
      return;
    }
    setAdding(true);
    setErr(null);
    setMsg(null);
    try {
      await createOffering({
        semester_id: sem,
        course_id: form.course_id,
        section_number: form.section_number.trim(),
        instructor_name: form.instructor_name || undefined,
        capacity: form.capacity,
        status: form.status,
        meetings: meetings.filter((m) => m.day_of_week && m.start_time && m.end_time),
      });
      setForm({ course_id: 0, section_number: "", instructor_name: "", capacity: 30, status: "Open" });
      setMeetings([blankMeeting()]);
      loadOfferings(sem);
      setMsg("Offering added");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setAdding(false);
    }
  }

  async function remove(o: Offering) {
    if (!confirm(`Remove ${o.course_code} section ${o.section_number}?`)) return;
    setErr(null);
    try {
      await deleteOffering(o.section_id);
      if (sem) loadOfferings(sem);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  }

  const upMeeting = (i: number, patch: Partial<Meeting>) =>
    setMeetings((ms) => ms.map((m, j) => (j === i ? { ...m, ...patch } : m)));

  return (
    <AdminShell>
      <h1 className="flex items-center gap-2 text-2xl font-bold text-zinc-900">
        <CalendarDays size={22} className="text-[#b8001f]" /> Course Offerings
      </h1>
      <p className="mb-6 text-sm text-zinc-500">Decide which courses are offered each semester and build their schedules.</p>

      {!writable && (
        <div className="mb-5 flex items-center gap-2 rounded-lg bg-zinc-100 px-4 py-2 text-sm text-zinc-600">
          <Lock size={14} /> Read-only role — editing disabled.
        </div>
      )}
      {err && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{err}</div>}
      {msg && <div className="mb-4 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{msg}</div>}

      {/* semester picker + new term */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <label className="text-sm font-medium text-zinc-600">Semester</label>
        <select value={sem ?? 0} onChange={(e) => setSem(Number(e.target.value))} className="rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-[#b8001f]">
          {semesters.map((s) => <option key={s.semester_id} value={s.semester_id}>{s.code}</option>)}
        </select>
        {writable && (
          <div className="flex items-center gap-2">
            <input value={newSem} onChange={(e) => setNewSem(e.target.value)} placeholder="New term (e.g. Fall 2026)" className="rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-[#b8001f]" />
            <button onClick={makeSemester} disabled={creatingSem || !newSem.trim()} className="flex items-center gap-1 rounded-lg border border-[#b8001f] px-3 py-2 text-sm font-semibold text-[#b8001f] hover:bg-[#b8001f]/5 disabled:opacity-50">
              {creatingSem ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />} New term
            </button>
          </div>
        )}
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-zinc-500"><Loader2 className="animate-spin" size={18} /> Loading…</div>
      ) : (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          {/* offerings list */}
          <div className="xl:col-span-2">
            <h2 className="mb-3 text-sm font-semibold text-zinc-700">{offerings.length} offering{offerings.length === 1 ? "" : "s"} this semester</h2>
            <div className="space-y-3">
              {offerings.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-zinc-200 bg-white px-6 py-10 text-center text-sm text-zinc-400">
                  No courses offered yet for this semester.
                </div>
              ) : (
                offerings.map((o) => (
                  <div key={o.section_id} className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-semibold text-zinc-800">{o.course_code}</span>
                          <span className="text-zinc-500">{o.course_title}</span>
                          <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs text-zinc-500">Sec {o.section_number}</span>
                        </div>
                        <div className="mt-0.5 text-xs text-zinc-400">
                          {o.instructor_name ?? "TBA"} · {o.enrolled}/{o.capacity} · {o.status}
                        </div>
                      </div>
                      {writable && o.enrolled === 0 && (
                        <button onClick={() => remove(o)} className="text-zinc-300 hover:text-red-600" title="Remove offering">
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {o.meetings.length === 0 ? (
                        <span className="text-xs text-zinc-400">No meeting times set</span>
                      ) : (
                        o.meetings.map((m, i) => (
                          <span key={i} className={`rounded-md px-2 py-0.5 text-xs font-medium ${m.meeting_type === "Lab" ? "bg-violet-50 text-violet-700" : m.meeting_type === "Tutorial" ? "bg-amber-50 text-amber-700" : "bg-blue-50 text-blue-700"}`}>
                            {m.meeting_type} · {m.day_of_week} {m.start_time}–{m.end_time}{m.location ? ` · ${m.location}` : ""}
                          </span>
                        ))
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* add offering */}
          {writable && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-zinc-700"><BookOpen size={16} /> Add an offering</h2>
              <div className="space-y-3 rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
                <select value={form.course_id} onChange={(e) => setForm({ ...form, course_id: Number(e.target.value) })} className="oi">
                  <option value={0}>Select course…</option>
                  {courses.map((c) => <option key={c.course_id} value={c.course_id}>{c.code} — {c.name}</option>)}
                </select>
                <div className="grid grid-cols-2 gap-2">
                  <input placeholder="Section #" value={form.section_number} onChange={(e) => setForm({ ...form, section_number: e.target.value })} className="oi" />
                  <input type="number" placeholder="Capacity" value={form.capacity} onChange={(e) => setForm({ ...form, capacity: Number(e.target.value) })} className="oi" />
                </div>
                <input placeholder="Instructor" value={form.instructor_name} onChange={(e) => setForm({ ...form, instructor_name: e.target.value })} className="oi" />

                <div className="border-t border-zinc-100 pt-2">
                  <div className="mb-1.5 flex items-center justify-between">
                    <span className="text-xs font-semibold text-zinc-600">Meetings (lecture / lab / tutorial)</span>
                    <button onClick={() => setMeetings([...meetings, blankMeeting()])} className="flex items-center gap-1 text-xs font-semibold text-[#b8001f]">
                      <Plus size={12} /> Add
                    </button>
                  </div>
                  <div className="space-y-2">
                    {meetings.map((m, i) => (
                      <div key={i} className="rounded-lg bg-zinc-50 p-2">
                        <div className="mb-1 flex items-center gap-1">
                          <select value={m.meeting_type} onChange={(e) => upMeeting(i, { meeting_type: e.target.value })} className="oi !py-1 flex-1">
                            {MTYPES.map((t) => <option key={t}>{t}</option>)}
                          </select>
                          <select value={m.day_of_week} onChange={(e) => upMeeting(i, { day_of_week: e.target.value })} className="oi !py-1 flex-1">
                            {DAYS.map((d) => <option key={d}>{d}</option>)}
                          </select>
                          {meetings.length > 1 && (
                            <button onClick={() => setMeetings(meetings.filter((_, j) => j !== i))} className="text-zinc-300 hover:text-red-600"><X size={14} /></button>
                          )}
                        </div>
                        <div className="flex items-center gap-1">
                          <input type="time" value={m.start_time} onChange={(e) => upMeeting(i, { start_time: e.target.value })} className="oi !py-1" />
                          <span className="text-xs text-zinc-400">to</span>
                          <input type="time" value={m.end_time} onChange={(e) => upMeeting(i, { end_time: e.target.value })} className="oi !py-1" />
                          <select value={m.location ?? ""} onChange={(e) => upMeeting(i, { location: e.target.value })} className="oi !py-1 w-28" title="Hall / room">
                            <option value="">Room…</option>
                            {labRooms.length > 0 && (
                              <optgroup label="Lab halls">
                                {labRooms.map((r) => <option key={r.room_id} value={r.name}>{r.name}</option>)}
                              </optgroup>
                            )}
                            {lectureRooms.length > 0 && (
                              <optgroup label="Lecture halls">
                                {lectureRooms.map((r) => <option key={r.room_id} value={r.name}>{r.name}</option>)}
                              </optgroup>
                            )}
                            {/* keep a custom value (e.g. from an older offering) selectable */}
                            {m.location && !rooms.some((r) => r.name === m.location) && (
                              <option value={m.location}>{m.location}</option>
                            )}
                          </select>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <button onClick={submit} disabled={adding} className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#b8001f] py-2.5 text-sm font-semibold text-white hover:bg-[#9b0019] disabled:opacity-50">
                  {adding ? <Loader2 className="animate-spin" size={16} /> : <Plus size={16} />} Offer this course
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <style>{`.oi{width:100%;border:1px solid #d4d4d8;border-radius:0.5rem;padding:0.5rem 0.6rem;font-size:0.8rem;outline:none}.oi:focus{border-color:#b8001f}`}</style>
    </AdminShell>
  );
}
