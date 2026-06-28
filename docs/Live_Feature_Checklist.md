# Live Feature Checklist (For Evaluators)

A hands-on guide to everything built in **Chat Rooms**. Use this to explore the app in a browser — no code required.

**Live demo:** [https://chat-rooms-6h4f.onrender.com/](https://chat-rooms-6h4f.onrender.com/)

**Local:** `npm run dev` → [http://localhost:3000](http://localhost:3000)

---

## How to test effectively

Most real-time features need **two browser sessions** at once:

| Session | Suggestion |
|---------|------------|
| Window A | Normal browser — e.g. **Alice** (room admin) |
| Window B | Incognito / second browser — e.g. **Bob** (member or join requester) |

Optional **Window C** for a **read-only** user (Carol) to verify permissions.

Sign up two or three accounts on the demo, or run locally and create fresh users. For pre-seeded rooms and message history locally, run:

```bash
cd backend && python -m scripts.seed_dummy_data
```

> Seed users are created without login passwords — use **Sign up** on the live demo, or sign up locally after seeding.

---

## Auth & session

| Feature | What to try | Expected result |
|---------|-------------|-----------------|
| Sign up | Create account with name, email, mobile, password | Logged in immediately; JWT stored |
| Log in | Use existing credentials | Enters app with sidebar visible |
| Log out | **Log out** button in sidebar | Returns to login screen |
| Session persistence | Refresh the page while logged in | Still logged in; rooms and history intact |
| Auto-logout | (Advanced) Wait for token expiry or invalidate token | 401 clears session and redirects to login |

---

## Rooms & discovery

| Feature | What to try | Expected result |
|---------|-------------|-----------------|
| Create room | **+** in sidebar header | New room appears; you are **admin** |
| Room list | Browse **Rooms** section | Group rooms with membership badges |
| Search | Type in sidebar search bar | Filters rooms (and DMs) by name |
| Role badges | Look at room rows | `admin`, `write`, `read`, `pending`, or `rejected` |
| Join request | Click a room you are not in | Join modal: request **Reader**, **Writer**, or **Admin** |
| Pending state | Click a room with `pending` badge | Info toast: waiting for admin approval |
| Rejected state | (If rejected) click that room | Error toast |
| Leave room | **Leave** in chat header (group rooms) | Confirm dialog → removed from room |

---

## Admin: join requests & membership

| Feature | What to try | Expected result |
|---------|-------------|-----------------|
| Requests button | Bob requests join; Alice is admin | Alice sees **Requests** button with count badge |
| Auto-popup | New request arrives while Alice is online | Join requests modal opens automatically |
| Approve / reject (modal) | Alice opens **Requests** | Grouped by room; **Approve** or **Reject** per user + role badge |
| Members panel | **Members** in chat header (group rooms) | List of approved members with roles |
| Pending in panel | Admin opens Members with pending users | Pending section with Approve / Reject |
| Promote to admin | Admin clicks **Promote** on a member | Member role becomes `admin` |
| Remove member | Admin clicks **Remove** | Member removed; confirm dialog first |
| Kick (live) | Remove someone who has the room open | They get a toast, are ejected from chat, room list refreshes |
| Last-admin protection | Try removing the only admin | Blocked (cannot orphan room) |

---

## Role-based permissions

| Role | What to try | Expected result |
|------|-------------|-----------------|
| **Admin** | Send, upload, delete others' messages, manage members | Full access |
| **Write** | Send messages, reply, upload files | Compose box and actions available |
| **Read** | Open room as reader | Messages visible; banner: *"You have read-only access"* — no compose box |

---

## Real-time chat (core)

| Feature | What to try | Expected result |
|---------|-------------|-----------------|
| Instant messaging | Send from Window A | Appears in Window B without refresh |
| Sender identity | View incoming messages | Sender **name** shown on others' messages |
| Message bubbles | Send as self vs receive | Outgoing vs incoming styling |
| Timestamps | Check message footer | Time shown on each message |
| Message history | Open a room / refresh page | Past messages load from database |
| Online count | Both users in same room | Header shows **N online** |

---

## Live collaboration UX

| Feature | What to try | Expected result |
|---------|-------------|-----------------|
| Typing indicators | Start typing in Window B | Window A shows *"Bob is typing…"* (3s fade after stop) |
| Multi-user typing | Two people type at once | *"X and Y are typing…"* or *"N people are typing…"* |
| Reply | Click **Reply** on a message | Reply banner with quoted preview; send attaches thread |
| Quote in timeline | View a reply message | Quoted block with original sender + snippet |
| Scroll to original | Click the quote block | Scrolls to the original message |
| Edit message | Pencil on **your own text** message | Inline editor; **Enter** save, **Esc** cancel |
| Edited label | Edit in Window A | Window B updates live; *(edited)* shown on both |
| Delete (own) | Delete your message | Gone for everyone in the room |
| Delete (admin) | Admin deletes someone else's message | Removed for all participants |
| Soft delete | Delete a message that was replied to | Message gone; reply preview may show placeholder |

---

## Files & media

| Feature | What to try | Expected result |
|---------|-------------|-----------------|
| Upload file | Paperclip in compose area | File appears as a message |
| 10 MB limit | Upload a file &gt; 10 MB | Toast error; upload blocked |
| Image preview | Upload PNG/JPG | Inline thumbnail; **Expand** overlay |
| Audio / video | Upload mp3/mp4 | Native player controls |
| Documents | Upload PDF or txt | **Open** / **Download** links |
| Live file sync | Upload in Window A | Window B receives file message via WebSocket |
| Authenticated media | View image in chat | Loads via signed/token URL (members only) |

---

## Unread & navigation

| Feature | What to try | Expected result |
|---------|-------------|-----------------|
| Unread badge | Bob messages in Room B while Alice is in Room A | Badge count on Room B in Alice's sidebar |
| Mark as read | Alice opens Room B | Badge clears for that room |
| Tab focus refresh | Switch away and back to tab | Unread counts refresh |
| Background poll | Wait ~10s with another room active | Badges stay roughly current |

---

## Direct messages (1:1)

| Feature | What to try | Expected result |
|---------|-------------|-----------------|
| DM section | Sidebar **Direct Messages** | Separate list from group rooms |
| Start DM (profile) | Click a name → **Message** | Opens 1:1 chat with that person |
| Start DM (mobile) | **+** under DMs → enter mobile number | Finds user → profile → **Message** |
| Find-or-create | Message the same person twice | Only one DM row (no duplicates) |
| DM chat features | Send, reply, upload, edit, delete in DM | Same pipeline as group rooms |
| DM simplicity | Open a DM | No Members panel, Leave, or admin controls |
| Delete in DM | Either participant deletes own message | Removed for both sides |

---

## Profiles

| Feature | What to try | Expected result |
|---------|-------------|-----------------|
| View profile | Click any name (message, sidebar, members) | Read-only modal with name, email, mobile |
| Edit own profile | Pencil next to your name in sidebar | Edit name, email, mobile → **Save** |
| Profile updates app-wide | Change your name | Sidebar and outgoing context update immediately |

---

## App polish & reliability

| Feature | What to try | Expected result |
|---------|-------------|-----------------|
| Light / dark theme | **Light** / **Dark** toggle in sidebar | Theme switches; persisted in localStorage |
| Custom toasts | Trigger any error (e.g. rejected room) | Styled toast — not browser `alert` |
| Confirm dialogs | Delete message, leave room, remove member | Custom confirm modal |
| WebSocket reconnect | Briefly stop backend / lose connection | Auto-reconnect after ~3s when back |
| Failed send UX | Send while WebSocket is down | Toast: message not sent; **input text preserved** |

---

## Backend & engineering (optional — not UI)

These are not clickable in the app but support reliability:

| Area | Detail |
|------|--------|
| **Persistence** | PostgreSQL — messages, rooms, members survive refresh |
| **File storage** | Supabase Storage with local-disk fallback |
| **Security** | JWT on REST + WebSocket; identity from token, not client params |
| **API docs** | [http://localhost:8000/docs](http://localhost:8000/docs) when running locally |
| **Automated tests** | `python testing/scripts/run_backend_tests.py` — permissions, edit, unread, DMs, soft-delete, files |
| **Documentation** | [Application_Features.md](Application_Features.md), [api_docs.md](api_docs.md), [setup_docs.md](setup_docs.md) |

---
