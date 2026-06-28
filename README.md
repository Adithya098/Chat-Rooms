# Chat Rooms

A real-time, room-based chat application — create spaces, invite members with role-based access, and collaborate over live WebSocket messaging with file sharing.

**Live demo:** [https://chat-rooms-6h4f.onrender.com/](https://chat-rooms-6h4f.onrender.com/)

---

## What It Does

Chat Rooms lets users sign up, join or create chat rooms, and communicate in real time. Each room has its own membership model with **admin**, **write**, and **read** roles, so you control who can send messages, upload files, and manage members.

Built as a full-stack learning project to explore how messaging apps work under the hood — JWT auth, WebSocket connections, PostgreSQL persistence, and optional cloud file storage.

### Highlights

- **Real-time chat** — instant messages, typing indicators, and online presence via WebSockets
- **Room-based access** — join requests, admin approval, and role-based permissions
- **Direct messages** — private 1:1 chats started by clicking a name or searching a phone number
- **Editable profiles** — click a name to view a profile; edit your own name, email, and mobile
- **Unread badges** — per-room unread counts in the sidebar
- **Message deletion** — delete your own messages anywhere; admins moderate any message in a group
- **Message editing** — edit your own text messages inline; changes sync live and show an `(edited)` label
- **File sharing** — upload images, audio, video, and documents (up to 10 MB)
- **Secure by design** — JWT authentication on every API call and WebSocket connection

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, SQLAlchemy, WebSockets |
| Database | PostgreSQL (Supabase) |
| File storage | Supabase Storage (optional local fallback) |
| Frontend | React, Vite |
| Auth | JWT (python-jose), bcrypt |
| Hosting | Render |

---

## Project Structure

```
Chat-Rooms/                         # repo root (.env, package.json, runtime.txt)
├── README.md
├── Application_Features.md         # feature reference (roles, DMs, unread, edit, …)
├── api_docs.md                     # REST + WebSocket reference
├── setup_docs.md                   # local setup and Render deployment
├── backend/
│   ├── app/
│   │   ├── auth.py                 # JWT create / verify
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── connection_manager.py   # WebSocket room broadcast
│   │   ├── supabase_storage.py
│   │   ├── models/                 # User, Room, RoomMember, Message, Document
│   │   ├── routers/                # users, rooms, members, messages, files, ws
│   │   └── schemas/                # Pydantic request/response types
│   ├── scripts/                    # idempotent DB migrations + seed_dummy_data.py
│   ├── uploads/                    # local file fallback (when Supabase is off)
│   └── requirements.txt
├── frontend/                       # React + Vite
│   └── src/
│       ├── context/                # ChatContext (session, rooms, messages reducer)
│       ├── hooks/                  # useApi, useWebSocket
│       ├── components/             # Sidebar, ChatArea, modals, profile, DMs, …
│       ├── styles/                 # component CSS
│       └── utils/                  # toast, confirm helpers
└── testing/
    ├── Testing_README.md           # how to run the suite
    ├── scripts/run_backend_tests.py
    └── backend/
        ├── conftest.py             # fake DB + auth fixtures
        ├── api/                    # endpoint tests (edit, unread, DMs, delete, …)
        └── unit/                   # isolated helper tests
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Live_Feature_Checklist.md](Live_Feature_Checklist.md) | Hands-on feature list for evaluators — what to test live in the browser |
| [Application_Features.md](Application_Features.md) | Features, roles, security, and file storage |
| [api_docs.md](api_docs.md) | REST endpoints, auth flow, and WebSocket events |
| [setup_docs.md](setup_docs.md) | Local setup, environment variables, and Render deployment |
