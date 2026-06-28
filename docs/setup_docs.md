# Setup Guide

Local development and Render deployment for Chat Rooms.

---

## Project Structure

```
Chat-Rooms/                   # repo root (.env, package.json, runtime.txt)
├── backend/
│   ├── app/
│   │   ├── auth.py           # JWT token creation + verification
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── connection_manager.py
│   │   ├── supabase_storage.py
│   │   ├── models/           # SQLAlchemy models
│   │   ├── routers/          # API + WebSocket route handlers
│   │   └── schemas/          # Pydantic request/response schemas
│   ├── scripts/              # Migration + seed utilities
│   ├── uploads/              # Local file storage (non-Supabase)
│   └── requirements.txt
└── frontend/                 # React + Vite
    └── src/
        ├── context/          # ChatContext (user session + JWT state)
        ├── hooks/            # useApi, useWebSocket
        └── components/       # UI components
```

---

## Local Setup

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1          # Windows
pip install -r backend/requirements.txt --default-timeout=100
npm install
cd frontend && npm install && cd ..
```

Create a `.env` file at the repo root:

```env
JWT_SECRET_KEY=change-this-to-a-long-random-secret-before-deploying

DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=5432
DB_NAME=postgres
DB_SSLMODE=require

SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_STORAGE_BUCKET=chat-documents
SUPABASE_STORAGE_PUBLIC_URLS=false
```

> `JWT_SECRET_KEY` must be a strong random value in production. Never commit `.env` to Git.

**Run (API + frontend together):**

```bash
npm run dev
```

Additional scripts:

```bash
npm run dev:api      # backend only
npm run dev:web      # frontend only (backend must already be running)
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| DB health | http://localhost:8000/db_health |

Tables are created automatically on first backend startup. Run migration scripts after pulling schema changes:

```bash
python backend/scripts/add_reply_to_column.py
python backend/scripts/add_is_deleted_to_messages.py
python backend/scripts/add_edited_at_to_messages.py
```

**Backend only** (serves built `frontend/dist` if present):

```bash
cd backend && python -m uvicorn app.main:app --reload --no-access-log
```

---

## Deployment (Render)

The app deploys as a single Render Web Service — FastAPI serves both the API and the built React frontend.

**Build command:**

```bash
pip install -r backend/requirements.txt && npm ci --prefix frontend && npm run build --prefix frontend
```

**Start command:**

```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-access-log
```

Set the same environment variables from `.env` in the Render dashboard. Render sets `RENDER=true` automatically for production CORS.

**Live demo:** [https://chat-rooms-6h4f.onrender.com/](https://chat-rooms-6h4f.onrender.com/)
