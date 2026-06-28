# API Documentation

HTTP and WebSocket reference for the Chat Rooms backend. Interactive docs are also available at `/docs` when the server is running.

---

## Authentication

All endpoints except `/users/login`, `/users/signup`, `/health`, and `/db_health` require:

```
Authorization: Bearer <token>
```

The token is returned by `/users/login` and `/users/signup`.

### Authentication Flow

```
1. POST /users/login  →  { token: "eyJ...", user: { id, name, ... } }
2. Store token in localStorage
3. All REST calls:  Authorization: Bearer <token>
4. WebSocket:       ws://.../ws/{room_id}?token=<token>
5. Media URLs:      /documents/{file_id}?token=<token>
6. Token expires after 30 days → 401 response → auto-logout + redirect to login
```

---

## REST Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/users/signup` | — | Register (returns `{ token, user }`) |
| POST | `/users/login` | — | Authenticate (returns `{ token, user }`) |
| GET | `/users/` | Bearer | List users |
| GET | `/users/{user_id}` | Bearer | Get user by ID |
| PATCH | `/users/me` | Bearer | Update own profile (`name`, `mobile`) |
| GET | `/users/by-mobile/{number}` | Bearer | Find a user by mobile number (to start a DM) |
| POST | `/rooms/` | Bearer | Create room (creator from token) |
| POST | `/rooms/direct` | Bearer | Find-or-create a 1:1 direct room with `{ user_id }` |
| GET | `/rooms/` | Bearer | List rooms (group rooms + your own direct rooms) |
| GET | `/rooms/unread/counts` | Bearer | Per-room unread counts `{ room_id: count }` |
| POST | `/rooms/{id}/read` | Bearer | Mark a room read (advance read watermark) |
| GET | `/rooms/{id}` | Bearer | Get room by ID |
| POST | `/rooms/{id}/join` | Bearer | Request to join with role (`read` or `write`) |
| POST | `/rooms/{id}/approve` | Bearer (admin) | Approve a pending member |
| POST | `/rooms/{id}/reject` | Bearer (admin) | Reject a pending member |
| POST | `/rooms/{id}/promote` | Bearer (admin) | Promote member to admin |
| POST | `/rooms/{id}/leave` | Bearer | Leave room (user from token) |
| DELETE | `/rooms/{id}/members/{user_id}` | Bearer (admin) | Remove a member |
| GET | `/rooms/{id}/members` | Bearer | List all members |
| GET | `/rooms/{id}/pending` | Bearer | List pending join requests |
| GET | `/rooms/{id}/messages/` | Bearer | Paginated message history |
| DELETE | `/rooms/{id}/messages/{message_id}` | Bearer (admin) | Soft-delete a message |
| POST | `/rooms/{id}/upload` | Bearer | Upload file (creates message + document record) |
| GET | `/rooms/{id}/documents` | Bearer | List room documents |
| GET | `/documents/{file_id}` | Bearer or `?token=` | Open document (signed URL redirect or local stream) |
| GET | `/files/{filename}` | Bearer | Legacy local file endpoint |
| WS | `/ws/{room_id}?token=` | `?token=` JWT | WebSocket (messages, typing, presence) |

> `/documents/{file_id}` accepts both `Authorization: Bearer` and `?token=` query param. The `?token=` fallback is required because browser `<img>`, `<audio>`, and `<video>` tags cannot attach custom headers.

> **Direct rooms** (`room_type: "direct"`) are private to their two members: list/detail/message reads return `404` to non-members, and the join/approve/promote/leave/remove endpoints return `400`. Both members are auto-approved at creation, so the existing WebSocket and message endpoints work unchanged.

---

## WebSocket Events

Connect to `/ws/{room_id}?token=<jwt>`.

### Client → Server

```json
{ "type": "message",     "content": "hello", "reply_to": 42 }
{ "type": "typing" }
{ "type": "stop_typing" }
{ "type": "file", "message_id": 5, "file_url": "/documents/<file_id>", "filename": "photo.png" }
```

### Server → Client

```json
{ "type": "message",      "id": 1, "sender_id": 3, "sender_name": "Alice", "content": "hello", "created_at": "...", "reply_to": 42, "reply_snippet": { ... } }
{ "type": "typing",       "user_id": 3, "user_name": "Alice" }
{ "type": "stop_typing",  "user_id": 3, "user_name": "Alice" }
{ "type": "file",         "id": 5, "sender_id": 3, "sender_name": "Alice", "file_url": "...", "filename": "..." }
{ "type": "online_users", "users": [1, 2, 3] }
{ "type": "error",        "content": "You don't have write permission in this room" }
{ "type": "message_deleted", "message_id": 100 }
{ "type": "member_removed",  "user_id": 5 }
{ "type": "kicked",          "content": "You were removed from 'general' by Alice" }
```
