# AIU Smart Academic Advisor — Complete Project Record
*Al Alamein International University — graduation project documentation*
*Up to date as of June 12, 2026. All numbers below were queried from the live system.*

---

## 1. What the project is

A full university advising platform with an AI academic advisor at its core. It has three applications sharing one PostgreSQL database and one FastAPI backend:

| Application | Tech | Port | Users |
|---|---|---|---|
| Student portal | Next.js 16 (React, TypeScript, Tailwind) | 3000 | Students |
| Admin portal | Next.js (separate app, `admin-ui/`) | 3001 | Registrar / staff / super-admin |
| Backend API | FastAPI (Python, async SQLAlchemy) | 8000 | Both portals |
| Database | PostgreSQL 17 + pgvector (Docker `aiu-postgres`) | 5433 | — |
| AI inference | Groq cloud (LLaMA 3.1-8B + LLaMA 3.3-70B) | — | — |

**Core design principle (the thesis statement of the project):**
> **The rules engine computes; the LLM narrates.** Every number the AI advisor shows — GPA, credit limits, graduation dates, seat counts — is computed by deterministic Python services from real database records. The language model is never allowed to invent or modify academic data. This makes every AI answer verifiable against the transcript and the official rulebook.

---

## 2. Database layer

### 2.1 Engine
- **PostgreSQL 17 with the pgvector extension**, in Docker (container `aiu-postgres`, port 5433, database `aiu`).
- Async SQLAlchemy ORM throughout; SQLite kept only as a one-line `.env` fallback for development.
- pgvector powers semantic search (RAG) with `cosine_distance` directly in SQL.

### 2.2 Schema — 37 tables, grouped by domain

| Domain | Tables |
|---|---|
| Academic structure | `programs`, `majors`, `semesters`, `registration_periods`, `requirement_categories`, `requirement_groups`, `requirement_group_courses` |
| Catalog | `courses`, `sections`, `section_meetings`, `prerequisites` |
| Students | `students`, `academic_standing`, `enrollments`, `grades`, `waitlist`, `retake_records` |
| Advising | `advisors`, `advisor_assignments`, `advisor_approvals`, `petitions` |
| Financial | `financial_accounts`, `financial_transactions`, `scholarships` |
| Capstone & quality | `capstone_enrollments`, `capstone_milestones`, `course_evaluations`, `course_evaluation_summaries`, `attendance_records`, `attendance_summaries` |
| AI | `chat_sessions`, `chat_messages`, `course_embeddings` (pgvector column) |
| Governance | `policy_config` (32 rows), `staff`, `audit_logs`, `notifications` |

### 2.3 The generated dataset (committee-defensible)
Live row counts: **400 students, 81 courses, 1,854 sections, 11,360 enrollments, 11,274 grades, 19 semesters, 28 prerequisite edges, 139 study-plan rows, 40 advisors, 2 majors.**

- Scope deliberately trimmed to **two majors: AIS (Artificial Intelligence Science) and AIE (AI Engineering)** — clean catalogs, no orphan courses.
- **Student ID convention: code prefix = entry year.** `25xxxxxx` = 1st year, `24` = 2nd, `23` = 3rd, `22` = 4th, `21` = graduated (or 5th-year AIE). Instantly readable cohorts during the demo.
- **Every transcript is rule-clean**: the generator never produces a record that violates a policy (no illegal overloads, no course before its prerequisite, standing transitions follow the state machine). The committee can audit any student and find zero contradictions.
- Cohorts include deliberate edge cases: racers (early-graduation candidates), probation students, dismissal-risk, retake-heavy students, Math-0 entrants.
- **Re-runnable pipeline** (`backend/scripts/`): `migrate_to_pg.py` (schema + base data, clones future semesters with sections forced Open) → `generate_students_pg.py` (the 400 transcripts) → `embed_courses.py` / `embed_pdfs.py` (vector embeddings for RAG).
- Demo logins (shared demo password `changeme123`): `25100002` Walid (CGPA 3.2 — early-graduation story), `25100045` (CGPA 1.83 — weak-areas story), `25100103` (CGPA 3.1 — summer-enrolled racer). Admin: `admin / admin123`.

---

## 3. Business rules engine — 32 live policies

All policies live in the `policy_config` table and are read at runtime by `services/policy.py` — **nothing is hardcoded**. They implement the official AIU rulebook PDF clause-for-clause (23 policies) plus Dr. Ashraf's advising notes (9 more).

### 3.1 The credit-load ladder (semester-indexed)
| Situation | Max load |
|---|---|
| Semester 1, Math-0 track | 12 CH (16 regular) |
| Semester 2 | 16 CH fixed |
| Semester 3 | 20 CH if CGPA ≥ 1.667, else 12 |
| Semester 4+ | 20 CH if CGPA ≥ 2.0, else 12 |
| Overload | **22 CH only when CGPA > 3.0, only from semester 4** |
| Summer term | **9 CH maximum, always** |

### 3.2 Academic standing state machine
Good Standing → Warning → Probation (consecutive-semester counters) → Dismissal risk, with recovery transitions — recomputed per semester by `services/standing.py` and stored in `academic_standing`.

### 3.3 Other enforced policy families
Prerequisites, registration windows (open/close dates per semester), retake rules, withdrawal rules, GPA computation (`counts_in_gpa`, repeat handling), graduation requirements per requirement group, advisor-approval requirements.

---

## 4. Backend API — FastAPI

### 4.1 Routers (27 mounted)
**Student-facing:** `auth` (JWT login), `students` (profile, academic-profile, degree-plan), `courses`, `enrollments` (enroll/drop/withdraw + waitlist), `gpa` (records + simulator), `schedule` (+ generator), `chat` (SSE streaming, session history, delete), `notifications`, `financial`, `capstone`, `evaluations`, `attendance`, `petitions`, `advisor`, `retakes`, `audit`.

**Admin:** `admin_auth`, `admin_dashboard`, `admin_students`, `admin_grades`, `admin_catalog`, `admin_offerings`, `admin_approvals`, `admin_policies`, `admin_notifications`, `admin_financial`, `admin_assistant` (AI), `admin_staff`.

All 31 verification endpoints pass; verified after the router migration on 2026-06-09.

### 4.2 Services layer (22 services — the actual brain)
| Service | What it does |
|---|---|
| `policy.py` | Runtime policy lookup from `policy_config` |
| `gpa_calculator.py` | CGPA/SGPA from real grades; simulation; required-grades-for-target solver |
| `standing.py` | Warning/probation/dismissal state machine |
| `validation.py` | Prerequisite, time-conflict, and window checks |
| `enrollment_service.py` | Enroll/drop pipeline + **advisor gates** (overload → `load_adjustment` approval; ahead-of-plan → `add` approval; enrollment held until approved) |
| `waitlist_service.py` | Tier-ranked waitlists + **auto-promotion** when a seat frees (stale entries expired, student notified, queue renumbered) |
| `registration_priority.py` | **4-tier seat priority** (see §5.3) |
| `academic_profile.py` | Weak/strong subject-area detection vs cohort (see §5.1) |
| `prereq_graph.py` | Transitive prerequisite-chain analysis (which courses unlock which) |
| `degree_planner.py` | Multi-term roadmap to graduation (see §5.2) |
| `schedule_generator.py` | Three intelligent schedule options per term (see §5.4) |
| `course_recommender.py` | Recommendations with unlock counts and difficulty |
| `recovery_service.py` | Probation-recovery planning |
| plus | `advisor`, `petition`, `retake`, `capstone`, `evaluation`, `attendance`, `withdrawal`, `notification`, `audit` services |

---

## 5. The smart generative planner (the differentiator)

Everything in this section is **computed live from the student's real records** on every request — nothing memorized, nothing canned.

### 5.1 Academic profile (`academic_profile.py`)
- Classifies every graded course into a subject area — mathematics, physics, hardware, programming, AI/data, general — via course-code prefix + name patterns.
- Compares the student's average grade points **against the cohort average on the same courses**. An area is *weak* when n ≥ 2 courses and (delta ≤ −0.35 below cohort or average < 2.0); also computes a per-area pass rate.
- Produces evidence strings used everywhere: *"Hard for you — your mathematics average is 1.7 vs cohort 2.8."*
- REST: `GET /students/me/academic-profile`.

### 5.2 Degree planner (`degree_planner.py`)
Simulates the student's future term by term until graduation, honoring **all** of: study-plan order, retakes-first, prerequisites (a prereq must be passed in an *earlier* term), course offering patterns (learned from real section history — a Fall-only course is never planned in Spring), the full credit ladder, and weak-area load shaping (at most 1 personally-hard course per term, 2 when racing; hard terms kept lighter).

Two modes, returned together by `compare_degree_plans`:
- **Normal** — main semesters only, plan pace, light terms around weak courses.
- **Fastest** — adds summer terms and legal overload; leads with Summer 2026 when its registration window is open and the student isn't already enrolled in it.

On top of the simulation, three pieces of computed insight:
1. **Feasibility bound** — pure arithmetic proof: remaining CH vs the sum of maximum legal loads of every future term → "the earliest *mathematically possible* graduation term". Example proven live: Walid has 83 CH remaining; max legal through Fall 2027 = 9+20+22+9+22 = 82 → Fall 2027 impossible by exactly 1 CH; Spring 2028 is provably optimal, and the fastest plan achieves it.
2. **Bottleneck analysis** — memoized DFS finds the longest remaining prerequisite chain (e.g. AIE111 → AIE121 → AIE323 → AIE425); names whether **credit caps** or the **prerequisite chain** is the binding constraint.
3. **Risk projection** — per-course p(pass) = 0.35 · student-area pass-rate + 0.65 · cohort course pass-rate → expected failures, at-risk courses (p < 0.6), expected extra terms, and a *realistic* vs *optimistic* graduation term.

Extra: the first roadmap term gets **real, conflict-free sections** assigned (actual meeting times, clash detection).

**Plan revision (added 2026-06-12):** `term_caps` parameter — "make Fall 2027 lighter" re-runs the whole engine with that term capped (a request can only *lower* a term below its legal limit, never raise it). Displaced courses are re-planned into later terms with every rule re-checked.

REST: `GET /students/me/degree-plan?mode=both|normal|fastest`.

### 5.3 Registration priority — 4 tiers (`registration_priority.py`)
1. **Tier 1** — on-plan, never-failed students taking courses due now.
2. **Tier 2** — retakes by students ≥ 70 % toward graduation (a failed course blocks their degree).
3. **Tier 3** — other retakes.
4. **Tier 4** — ahead-of-plan "racers" (also gated behind advisor approval).

The tiers drive: waitlist ordering (a tier-1 joiner jumps ahead of an earlier tier-3 — verified), auto-promotion order, and the advisor-approval gate.

### 5.4 Schedule generator (`schedule_generator.py`)
Three options per term: **Fastest** (up to the legal limit, max 2 personally-hard courses), **Balanced** (≤ 18 CH, 1 hard), **Focus Load** (≤ 12 CH with an evidence note when a weak-area course is due). Course ordering key combines urgency bucket (retake/backlog > due-now > ahead), study-plan year, **chain criticality** (transitive unlock count), **seat scarcity** (students-needing vs open seats), credits, and personal difficulty. Each course carries flags the chatbot surfaces: RETAKE / ahead-of-plan-needs-approval / "Hard for you (reason)" / "register FIRST — 23 students need it, only 8 seats."

---

## 6. The AI advisor chatbot

### 6.1 Pipeline (LangGraph, `backend/ai/`)
```
student message
  → intent_classifier   (LLaMA 3.1-8B, 10 intents, disambiguation hints)
  → context_loader      (live student context from PostgreSQL)
  → one tool node       (deterministic Python — the rules engine)
  → rag_retriever       (pgvector cosine search over embedded documents)
  → response_generator  (LLaMA 3.3-70B, streamed over SSE)
```
Intents: `academic_info, course_recommendation, gpa_simulation, schedule_planning, graduation_planning, probation_recovery, career_guidance, financial_query, policy_question, general_chat`.

### 6.2 Context injection (every single message)
Today's date · registration windows open right now **with close dates** · degree progress (earned/total CH) · in-progress courses · CGPA/SGPA computed from actual grades · academic standing · **hard load limits from the policy table** (summer 9 / standard 20 / overload 22 with CGPA > 3.0 from semester 4).

### 6.3 The advisor-voice contract (system prompt)
1. **Verdict first** — open with the direct answer.
2. **Show the evidence** — every claim with the actual numbers.
3. **Name the binding constraint** — credit caps vs prereq chain vs seats vs policy.
4. **Point out the non-obvious** — one insight the student didn't ask for.
5. **One next action with its deadline** — "Register for Summer 2026 before June 14."

### 6.4 Guardrails — the LLM never invents plans
- Plans/schedules must come **verbatim from tool results**; the prompt explicitly forbids moving courses between terms.
- Plan-modification requests ("make Fall 2027 lighter", "cap Spring 2027 at 14 hours") are parsed **deterministically** (regex, no LLM guessing: strong keywords alone, weak keywords only with an explicit number, default light load 12 CH) and re-routed through the degree-plan engine.
- Tool summaries embed the hard load limits and a "REVISION APPLIED by the planning engine" marker so the narrator presents only validated plans.
- Verified end-to-end: the conversation that once produced an illegal 10-CH summer now returns Fall 2027 = 12 CH with the spill going to Spring 2028 (15 CH, legal) and Summer 2027 untouched at 7 CH.

### 6.5 RAG
Course descriptions **and policy PDF pages** are embedded into the `course_embeddings` pgvector table (document name + page number kept per chunk). Retrieval = cosine distance in SQL (with an in-Python fallback); answers cite sources inline as `[doc: name]` and the UI shows **citation chips**.

### 6.6 Chat UX
Markdown rendering incl. **GitHub-style tables** (degree plans: `| Term | Courses | CH | Note |`; schedules: `| Course | Title | CH | Day & Time | Notes |`) · streaming tokens · conversation **persists across page navigation** (localStorage) · **history drawer** listing past conversations · **per-conversation delete** (owner-only API + confirm dialog) · full **Arabic** answers when the UI language is Arabic.

---

## 7. Student portal (Next.js, 20 pages)

| Page | Highlights |
|---|---|
| Login | Demo-friendly: advertises the shared demo credentials |
| Dashboard | Standing, GPA trend, notifications, quick actions |
| Academic Records | Transcript by semester, 2-decimal GPA everywhere |
| **GPA Simulator** | Past semesters locked read-only 🔒; in-progress terms grade-only simulatable (excluded until a grade is picked — fixed phantom-"A" inflation); hypothetical semesters fully editable; target-CGPA solver |
| **Schedule Generator** | The 3 intelligent options with tier/difficulty/scarcity flags |
| Study Plan | Requirement groups vs completed/in-progress/remaining |
| Course Recommendations | Unlock counts, difficulty, personal fit |
| Manage Classes | Requirements, my classes, enroll (with waitlist + approval flows) |
| Advisor | Assigned advisor, approval requests |
| Petitions / Capstone / Evaluations / Attendance / Financial / Career / Analytics / Profile / Settings | Full CRUD against their routers |
| **AI Chat panel** | Available on every page (floating panel) |

**Theming & i18n:** dark mode across all pages with live toggle sync; `useLanguage` hook + en/ar dictionary, full RTL flip; chrome, login, and settings translated.

---

## 8. Admin portal (separate app, 10 sections)

- **RBAC** (role-based access control) + **audit logging** on every mutating action (`audit_logs`).
- Sections: Dashboard (KPIs), Students (list, detail, transcript, financial), Courses & catalog, Offerings (sections/meetings), Approvals (advisor-gate queue), Announcements, Rules (live policy editor over `policy_config`), Audit log browser, **AI Assistant**, Staff.
- **Phase 3 — AI assistant for staff:** natural-language queries over the database + **anomaly scan** (flags inconsistent records).
- **Phase 4 — staff management:** super-admin-only admin CRUD with self-lockout guards (can't delete/demote yourself or the last super-admin).
- Login: `admin / admin123`.

---

## 9. Quality engineering & key fixes (the story of hardening)

Documented, reproducible fixes — each one is presentation material:

1. **"Is this answer good?" audit** → response-quality overhaul: verdict-first contract, no repeated course lists, finish-your-sentence rule, 1200-token budget for tool-backed answers.
2. **Contradicting bot answers** → root cause: 54 cloned Fall-2026 sections carried `status='Closed'`; fixed in data **and** in the migration script (clones force Open).
3. **Identical schedule options** → hard caps + frozenset dedupe in the generator.
4. **Illegal 22 CH for a semester-3 student** → semester-indexed ladder inside the planner simulation.
5. **Pre-existing 500 on enrollment** → `EnrollResult` schema accepted only `str` IDs; now `int | str` + `requires_approval`/`approval_type`.
6. **The 10-CH summer hallucination** → the full "engine computes, LLM narrates" guardrail set (§6.4).
7. **"Can't graduate Fall 2027" challenged by the user** → answered with the feasibility-bound proof; the bot was right and can now show the arithmetic.

**Regression tests:** `backend/scripts/test_plan_revision.py` (extractor false-positive matrix + planner cap invariants) and `test_chat_revision.py` (full E2E: login → SSE chat → revision → assertions). Build verified clean; all 31 endpoint checks pass.

---

## 10. Academic early-warning model (the predictive ML layer)

The one **trained** model in the system — everything else is rules + LLM. It predicts, from a student's **first-year record only**, whether they will later hit a formal academic warning / probation / dismissal, early enough to intervene. It fits the project thesis as *"the model computes the risk, the LLM narrates the advice."*

### 10.1 Why it is genuinely predictive (not circular)
- **Label** = did the student ever reach warning / probation / dismissal? Under the Dr. Ashraf ladder this can only happen from the **3rd main semester** on.
- **Features** = the **first two main semesters only**. Features and label never overlap in time, so the model forecasts a *later* outcome rather than restating the current CGPA.
- **Train set** = senior cohorts that have completed ≥ 3 main semesters (outcome already known). **Prediction targets** = current first/second-years, whose outcome is still open (`horizon = "forecast"`). The model learns from four graduated-enough cohorts and applies it to today's freshmen.

### 10.2 Features (4, curated for stable signs) — `services/risk_features.py`
`first_year_gpa`, `gpa_trend` (sem 2 − sem 1), `failed_courses`, `low_grade_rate` (share of first-year grades below C). Candidates were dropped on evidence, not taste: withdrawals (none occur in year 1), the Math-0 flag (near-constant in the data), raw credit load (the registration cap makes a light load a *proxy* for an already-low CGPA), and a math-deficit term (too collinear to hold a stable sign). The four survivors all carry the intuitive sign — a weaker first year always raises predicted risk.

### 10.3 Leakage fix — features are point-in-time
Found during the data audit: the extractor originally keyed off `counts_in_gpa`, which a **year-2 retake flips to False** — silently erasing a year-1 failure from a first-year feature. This inflated 18 senior students' first-year GPA by up to **1.26 points** (e.g. 21100002: a real 1.12 shown as 2.375) and was one-directional — current freshmen can't have retaken yet — so it skewed training and *hid* at-risk seniors from the signal. Fixed: every feature is now computed **as the record stood at first-year end** — judged by each course's letter grade, deduped to the latest attempt *within* the first year, never using the retake-sensitive flag.

### 10.4 Model + serving — `scripts/train_risk_model.py`, `services/risk_model.py`
`StandardScaler` + `LogisticRegression` (scikit-learn), trained offline and saved as a small JSON artifact (`ai/artifacts/risk_model.json`). The running backend **re-implements the sigmoid in pure Python** and never imports scikit-learn, so the server stays light. Held-out **AUC 1.0**, 5-fold **CV AUC 0.982 ± 0.015**, recall 1.0. Honest limitation stated up front: only **13 at-risk positives in 165 trained students** (7.9 % base rate) — a working, leakage-free pipeline, not a production-validated model.

### 10.5 Explainability + narration
Each score decomposes into per-factor contributions (coefficient × standardized value — a linear SHAP), surfaced as risk-raising **factors** with plain-language detail, **protective** factors, and a concrete next step mapped to each active factor. The student endpoint adds an optional **LLM-narrated advisor note** built strictly from those factors (graceful if Groq is unavailable).

### 10.6 Surfaces
- **Student:** `GET /students/me/risk` → dashboard card `RiskPanel.tsx` (risk gauge, weighed factors, protective chips, advisor note, model-provenance footer). Complements the *reactive* RecoveryPanel with a *predictive* forecast.
- **Admin:** `GET /admin/students/risk-predictions` (every active student scored and ranked by predicted risk — surfaces students whose current CGPA still looks fine) + `GET /admin/risk-model` (metrics card). The admin dashboard adds a "Predicted High-Risk (ML)" stat and an ML risk queue.

### 10.7 Data-integrity auditor — `scripts/audit_dataset.py`
Read-only, reusable; 30+ checks — duplicates, orphans/FKs, CGPA drift vs recomputed-from-grades, grade↔points coherence, `counts_in_gpa` correctness, the retake latest-counts invariant, prerequisite ordering, standing consistency. Whole dataset: **0 FAIL / 0 WARN**, with only by-design INFO (24 ungraded = the in-progress Summer 2026 term; LAN022/PSC101 are 0-credit pass/fail). Run it before every retrain.

---

## 11. Five-minute demo script

1. Login `25100002 / changeme123` (Walid, CGPA 3.2, 30/113 CH).
2. Ask the chat: *"I finished first year and I want a plan to graduate early"* → two table plans, Summer-2026 lead, June 14 deadline.
3. Ask: *"Can I graduate in Fall 2027?"* → **mathematical impossibility proof** (83 CH > 82 max legal).
4. Ask: *"Make Fall 2027 lighter"* → engine-recomputed revision; summer stays legal; graduation unchanged.
5. Switch to `25100045` (CGPA 1.83) → weak-area profile, **Focus Load** option, light degree plan around hard courses.
6. Admin portal → Rules editor (change a policy live), Approvals queue (the racer's pending request), AI anomaly scan.
7. **Early-warning model:** as a current first-year (`25100008`) the dashboard shows a **high-risk forecast (~75%)** with the factors behind it (failed courses, low first-year GPA) and an LLM advisor note — caught *before* any formal probation; Walid (`25100002`) shows **low / on-track**. Admin → dashboard ML risk queue ranks every active student by *predicted* risk, not just current CGPA.

---

*End of record.*
