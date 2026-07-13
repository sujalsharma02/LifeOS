# LifeOS — AI Diary Assistant

An AI companion you talk to instead of writing a journal. It chats with you about your day, then automatically writes a diary entry in your preferred style, extracts structured memories, embeds them for retrieval, and maintains a living profile of who you are. Built from `AI_Diary_Assistant_Product_Architecture.pdf`.

## Stack

- **Frontend** — Next.js 16 + Tailwind CSS (`frontend/`)
- **Backend** — FastAPI + SQLAlchemy async (`backend/`)
- **Database** — Neon (serverless PostgreSQL) + pgvector
- **LLM** — provider abstraction (`backend/app/llm/`): NVIDIA Build API first, automatic fallback to Gemini when NVIDIA is unavailable (5-minute cooldown between retries); within Gemini, transient 503/429s are retried and a lite model (`GEMINI_FALLBACK_MODEL`) takes over if the flagship stays overloaded. Voyage AI for embeddings (embeddings never fall back — mixing embedding models breaks vector search)

## Setup

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env   # then fill in DATABASE_URL and GEMINI_API_KEY
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Tables and the pgvector extension are created automatically on first startup.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The frontend expects the API at `http://localhost:8000` (override with `NEXT_PUBLIC_API_URL` in `frontend/.env.local`).

## How it works

1. **Chat** (`POST /api/chat/stream`) — you talk naturally and the reply streams in token by token; the companion asks gentle follow-ups. The living profile is always in context; diary memories are retrieved via RAG **only when** a cheap classifier decides historical context is needed (per the spec's selective-RAG strategy). A non-streaming `POST /api/chat` also exists.
2. **End conversation** (`POST /api/conversations/{id}/end`) — kicks off a background pipeline:
   - **Memory extraction** — summary, people, places, projects, goals, tasks, companies, skills, topics, events, important facts, mood, emotion, importance score
   - **Diary generation** — an essay in your chosen style (7 presets + custom prompt)
   - **Embedding** — the retrieval document (summary + facts + topics) is embedded into pgvector
   - **Living profile update** — goals, interests, career, relationships, preferences, challenges merged with the new day
3. **Retrieval** — future conversations vector-search `diary_metadata.embedding` (cosine) when context is needed.
4. **Insights** (`/insights`) — streaks, mood mix, importance timeline, top people/topics/projects/places, and journaling rhythm, computed from the extracted metadata (no LLM calls).
5. **Weekly reflection** (`POST /api/reflections/generate`) — the LLM reads the last 7 days of entries plus the living profile and writes a week-in-review: the arc, wins, patterns, and one suggestion.
6. **Semantic search & memories** — the diary page searches by meaning ("the week I felt stuck"), and an "On this day" strip resurfaces entries from a week / month / year ago.

## API surface

| Endpoint | Purpose |
|---|---|
| `POST /api/chat` | Send a message, get the companion's reply |
| `POST /api/chat/stream` | Same, but the reply streams as server-sent events |
| `GET /api/insights` | Streaks, moods, timeline, top people/topics, rhythm |
| `GET /api/search?q=` | Semantic (vector) search over diary memories |
| `GET /api/onthisday` | Entries from a week / month / year ago today |
| `GET /api/reflections`, `POST /api/reflections/generate` | Weekly AI reflections |
| `GET /api/conversations/active` | Get or create the active conversation |
| `POST /api/conversations/{id}/end` | End conversation, trigger diary pipeline |
| `GET /api/diaries` / `GET /api/diaries/{id}` | List / read diary entries (+ extracted memory) |
| `GET /api/profile` | The living user profile |
| `GET /api/styles`, `PATCH /api/settings/style` | Diary style presets / custom prompt |
| `GET /api/export/{markdown,json,sqlite}` | Export all your data |
| `GET /health` | Health + database status |

## Configuration

All backend config lives in `backend/.env` (see `.env.example`): `DATABASE_URL`, `NVIDIA_API_KEY`, `GEMINI_API_KEY`, model overrides, and optional `EMBEDDING_PROVIDER=voyage` + `VOYAGE_API_KEY`. The chat chain is `LLM_PROVIDER` → `LLM_FALLBACK_PROVIDER` (set the fallback empty to disable it).

Swapping LLM vendors means implementing `LLMProvider` (`backend/app/llm/base.py`) and registering it in `registry.py` — business logic never touches a vendor API directly.

## Roadmap (from the spec)

- **Phase 1 (done)** — chat, diary generation, metadata, embeddings
- **Phase 2 (done)** — selective RAG retrieval, living profile, exports (Markdown / JSON / SQLite)
- **Phase 3 (done)** — insights dashboard (streaks, moods, timeline, top entities), weekly AI reflections, semantic search, "On this day", streaming chat
- **Phase 4** — voice, mobile app, calendar/photo integrations, monthly reports

## License

Apache 2.0 — see [LICENSE](LICENSE).
