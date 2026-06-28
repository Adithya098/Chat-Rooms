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

## Documentation

| Document | Description |
|----------|-------------|
| [Application_Features.md](Application_Features.md) | Features, roles, security, and file storage |
| [api_docs.md](api_docs.md) | REST endpoints, auth flow, and WebSocket events |
| [setup_docs.md](setup_docs.md) | Local setup, environment variables, and Render deployment |
