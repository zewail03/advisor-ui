# Deploying AIU Academic Advisor — free tier

A practical, **$0/month** setup that splits the app across the best free tiers and
sidesteps the one real blocker (the chatbot's PyTorch model).

## Architecture

```
  Vercel (free)            Railway / Render (free)        Neon (free)
 ┌──────────────┐   API   ┌──────────────────────┐  SQL ┌──────────────────┐
 │ Student portal│ ─────▶ │  FastAPI backend     │ ───▶ │ Postgres+pgvector │
 │ Admin  portal │        │  (slim, no PyTorch)  │      └──────────────────┘
 └──────────────┘        └──────────┬───────────┘
                                    │ embeddings (HTTP)
                                    ▼
                          HuggingFace Inference API (free)
                          Groq API (LLM)  ·  Stripe (test)
```

**Why the split:** the backend bundles `sentence-transformers` (PyTorch, ~1 GB RAM),
which does NOT fit a 512 MB free tier. In deploy we set `EMBEDDING_BACKEND=hf` so
query embeddings come from the **HuggingFace API** using the *same* `all-MiniLM-L6-v2`
model — so your stored 384-dim vectors stay compatible (no re-embedding) and the
image shrinks enough to fit free RAM. If HF is ever unavailable, the chatbot still
answers — it just skips the cited policy snippets (graceful degradation).

> **Heads-up on Railway:** Railway no longer has a sustainable free tier — new accounts
> get a one-time ~$5 trial credit, then it's the ~$5/mo Hobby plan. For a *sustainably*
> free backend, **Render's free web service** is better (it sleeps after 15 min idle and
> cold-starts in ~30–60 s, but never expires). The steps below work on either — pick one.

---

## 0. Accounts you'll need (all free)
- **GitHub** (the repo is already here) · **Vercel** · **Neon** · **Railway** *or* **Render**
- **HuggingFace** → a free read token: huggingface.co/settings/tokens
- **Groq** (you already have a key) · **Stripe** test key (you already have one)

---

## 1. Database — Neon (Postgres + pgvector)
1. Create a project at **neon.tech** → it gives you a connection string like
   `postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require`.
2. In the Neon SQL editor, enable pgvector:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Load your data. Easiest is to copy your local DB up (same 384-dim model, so the
   stored embeddings work as-is). From your machine:
   ```bash
   # dump local (Docker Postgres on :5433)
   docker exec aiu-postgres pg_dump -U aiu -d aiu -Fc -f /tmp/aiu.dump
   docker cp aiu-postgres:/tmp/aiu.dump ./aiu.dump
   # restore into Neon (psql/pg_restore must reach Neon over SSL)
   pg_restore --no-owner --no-acl -d "postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require" ./aiu.dump
   ```
   Convert the async URL for SQLAlchemy: the app's `DATABASE_URL` must start with
   `postgresql+asyncpg://` — i.e. take Neon's string and replace `postgresql://`
   with `postgresql+asyncpg://` (drop `?sslmode=require`; asyncpg uses SSL to Neon by default).

---

## 2. Backend — Railway (or Render)
The repo already has `backend/Dockerfile` (slim) + `backend/requirements-deploy.txt`.

### Railway
1. **New Project → Deploy from GitHub repo** → pick this repo.
2. In the service **Settings → Root Directory** = `backend` (so it uses `backend/Dockerfile`).
3. **Variables** (Settings → Variables):
   ```
   DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.neon.tech/neondb
   SECRET_KEY=<a long random string>
   GROQ_API_KEY=<your groq key>
   EMBEDDING_BACKEND=hf
   HF_API_TOKEN=<your huggingface token>
   STRIPE_SECRET_KEY=<your sk_test_ key>
   CORS_ORIGINS=https://<your-student>.vercel.app,https://<your-admin>.vercel.app
   FRONTEND_BASE_URL=https://<your-student>.vercel.app
   REDIS_URL=redis://localhost:6379
   CELERY_BROKER_URL=redis://localhost:6379/0
   CELERY_RESULT_BACKEND=redis://localhost:6379/0
   ```
   (Redis/Celery vars just satisfy config; no worker runs. You can fill the Vercel
   URLs after step 3 and redeploy.)
4. Deploy. Railway gives you a URL like `https://aiu-backend.up.railway.app`.
   Sanity check: open `<that-url>/` → `{"status":"ok"}`.

### Render (sustainably free alternative)
- **New → Web Service → from repo** → **Root Directory** `backend`, **Runtime** Docker.
- Add the same env vars. Free plan sleeps when idle; hit the URL once to wake it
  before a demo.

> The backend creates tables + the `vector` extension on first boot, so an empty Neon
> DB also works — but restoring your dump (step 1) keeps your curated dataset, demo
> students, and embeddings.

---

## 3. Frontends — Vercel (two projects)
The student portal is the repo root; the admin portal is `admin-ui/`. Create **two**
Vercel projects from the same repo:

| Project | Root Directory | Env var |
|---|---|---|
| Student portal | `/` (repo root) | `NEXT_PUBLIC_API_URL=https://<backend-url>` |
| Admin portal | `admin-ui` | `NEXT_PUBLIC_API_URL=https://<backend-url>` |

1. **Add New → Project → import this repo.** For the admin one, set Root Directory =
   `admin-ui`. Vercel auto-detects Next.js (build `next build`, output handled).
2. Add `NEXT_PUBLIC_API_URL` = your backend URL (from step 2) in each project's
   **Settings → Environment Variables**, then deploy.
3. You'll get URLs like `https://aiu-advisor.vercel.app` (student) and
   `https://aiu-admin.vercel.app` (admin).

---

## 4. Wire the URLs back to the backend
Now that you have the Vercel URLs, set them on the backend and redeploy:
- `CORS_ORIGINS=https://aiu-advisor.vercel.app,https://aiu-admin.vercel.app`
- `FRONTEND_BASE_URL=https://aiu-advisor.vercel.app` (Stripe success redirect)

(`*.vercel.app` is already allowed by a CORS regex, so preview deployments work too —
`CORS_ORIGINS` is mainly for a custom domain later.)

---

## 5. Verify
- Backend: `GET https://<backend>/` → `{"status":"ok"}`.
- Student portal: log in (`25100045 / changeme123`), open a page, try the chatbot.
- Admin portal: log in (`admin / admin123`).
- Payments: Financial → Make Payment → Stripe test card `4242 4242 4242 4242`.

## Notes / gotchas
- **Free-tier sleep / cold start:** Render free (and a depleted Railway trial) sleep
  when idle — the first request after a nap is slow. Hit the URL once to warm it up
  before demoing.
- **HF embeddings cold start:** the first chatbot query after idle may take a few
  seconds while HF loads the model (`wait_for_model` handles it). RAG citations are
  the only thing that depends on HF; the rest of the chat works regardless.
- **Secrets:** never commit real keys. Set them only as host env vars (your local
  `.env` stays gitignored; `.env.example` documents the names).
- **Cost:** Vercel + Neon + HuggingFace + Groq + Stripe-test are all free. Only the
  backend host has a cost ceiling — Render free = $0 (with sleep), Railway = trial
  credit then ~$5/mo.
