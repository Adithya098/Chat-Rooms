# Application Features

Detailed feature reference for Chat Rooms. For API endpoints and WebSocket payloads, see [api_docs.md](api_docs.md).

---

## Authentication and User Session

- **JWT authentication**: login and signup return a signed JWT (`Authorization: Bearer <token>`) used on every subsequent request
- **Session persistence**: token and user profile are restored from `localStorage` on page reload; expired tokens force re-login automatically
- **Password security**: bcrypt hashing with salted hash — plaintext passwords are never stored
- **Input validation**: required fields and password minimum checks on signup

---

## Room Access and Membership

- **Role-based room access** (`admin` / `write` / `read`)
- **Join requests** with admin approve/reject flow — users may request `read` or `write` roles only (admin role is assigned by promotion, not self-request)
- **Admin request inbox** with grouped pending requests and role badges
- **Member management**: promote members to admin, remove members, prevent last-admin removal
- **Room management**: users can leave voluntarily; last-admin protection prevents orphaned rooms

---

## Messaging and Realtime Collaboration

- **Real-time messaging** over WebSocket with JWT-authenticated connections (`?token=` query param)
- **Message replies** with quoted preview and scroll-to-original
- **Typing indicators** with 3-second graceful fade
- **Room presence** (`online_users` count)
- **Admin moderation**: soft-delete messages with real-time deletion broadcast
- **Unread message badges**: per-room unread counts in the sidebar, derived from a per-member read watermark (`last_read_message_id`); the open room is auto-marked read and badges refresh on read, tab focus, and a 10s poll
- **Custom toast + confirm UX** instead of native browser alerts
- **Safer send UX**: message input is preserved and a toast is shown if the WebSocket is not open

---

## Direct Messages and Profiles

- **1:1 direct messages**: private chats modeled as a special room (`room_type = "direct"`) with both participants auto-approved — no join request, approval, or admin role
- **Two ways to start a DM**: click a member/sender name to open their profile and hit **Message**, or search by phone number from the sidebar's **Direct Messages** section
- **Find-or-create**: opening a DM reuses the existing 1:1 room if one exists, so duplicates are never created
- **Privacy**: direct rooms are visible and readable only to their two members; group rooms stay discoverable
- **Profile cards**: view any user's name/mobile/email; edit your own name and mobile inline
- **Reused pipeline**: DMs ride the same WebSocket, messages, files, replies, and unread badges as group rooms

---

## File and Document Handling

- **File uploads** (images, audio, video, PDFs, docs, archives)
- **Upload guardrails**: 10 MB max with frontend pre-check and backend enforcement
- **Media rendering**: images expand inline; audio and video have native player controls
- **Document center**: room-scoped document listing with secure open/download links
- **Dual storage**: Supabase Storage (signed URLs) with local-disk fallback
- **Authenticated media**: `<img>`, `<audio>`, `<video>` tags load media via `?token=` query param since browser tags cannot send `Authorization` headers

---

## Security

- All API endpoints (except `/users/login`, `/users/signup`, `/health`, `/db_health`) require a valid JWT
- Acting identity (`user_id`, `admin_id`) is always resolved from the token — never trusted from client-supplied parameters
- WebSocket connections are authenticated via `?token=` before any messages are accepted
- 401 responses automatically clear the local session and redirect to login

---

## Role Permissions

| Role | Read | Send | Reply | Upload | Approve/Reject | Delete Messages | Remove Members | Promote Members | Leave Room |
|------|------|------|-------|--------|---------------|-----------------|----------------|-----------------|------------|
| `admin` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (if not last admin) | ✓ | ✓ (if not last admin) |
| `write` | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |
| `read`  | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |

---

## File Storage

- Allowed extensions: images, audio, video, PDF, txt, doc/docx, csv, zip
- Max size: **10 MB** (enforced frontend and backend)
- Primary: Supabase Storage — files served via time-limited signed URLs (default 1 hour)
- Fallback: local `backend/uploads/` directory
- File access is always membership-checked — non-members cannot open documents
