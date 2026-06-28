# Testing Guide

How the automated tests for this project work, and how to run them.

---

## Running the tests

From the **repo root**:

```bash
# Run everything
python testing/scripts/run_backend_tests.py

# Or call pytest directly
pytest testing/backend
```

When tests run, pytest prints one character per test on a single line:

| Symbol | Meaning |
|--------|---------|
| `.` | Test passed |
| `F` | Test failed |
| `E` | Test errored (crashed before finishing) |

When you use `run_backend_tests.py`, a successful run ends with a line like `10/10 passed in 0.08s` — the fraction shows passed tests out of the total collected.

```bash
python testing/scripts/run_backend_tests.py --api    # API tests only
python testing/scripts/run_backend_tests.py --unit   # unit tests only
pytest testing/backend -v                            # verbose: one line per test
pytest testing/backend/api/test_unread.py            # a single file
pytest testing/backend -k "permission"               # tests matching a keyword
```

> **Prerequisite:** `pytest` must be installed in your environment
> (`pip install pytest`). No database, server, or `.env` is required — see why below.

---

## What gets tested

These are **backend** tests. They check the FastAPI API and a few small helper
functions. There are no frontend tests yet.

```
testing/
├── README.md                  ← this file
├── scripts/
│   └── run_backend_tests.py   ← convenience runner (--api / --unit flags)
└── backend/
    ├── conftest.py            ← shared setup (fake DB, fake login, seed data)
    ├── pytest.ini             ← pytest config
    ├── api/                   ← endpoint tests (request in → response out)
    │   ├── test_users.py        signup / login
    │   ├── test_rooms.py        create / list / get rooms
    │   ├── test_members.py      join / approve / reject
    │   ├── test_messages.py     history / delete
    │   ├── test_files.py        upload / download authorization
    │   ├── test_permissions.py  admin-only moderation (promote / remove)
    │   ├── test_soft_delete.py  deleted message keeps reply previews
    │   ├── test_unread.py       per-room unread counts
    │   └── test_health.py       health endpoint
    └── unit/                  ← isolated function tests (no HTTP, no DB)
        ├── test_database.py
        ├── test_router_helpers.py
        └── test_supabase_storage.py
```

- **`api/` tests** exercise whole endpoints end-to-end through FastAPI's
  `TestClient` (no network, no running server).
- **`unit/` tests** call tiny standalone helpers directly.

---

## How it works (the important part)

The tests never touch your real Postgres, never start a web server, and never
use real JWT tokens. Four things are faked, all set up in `conftest.py`:

### 1. Database → in-memory SQLite
A fresh SQLite database is created in memory before each test and thrown away
after. Every test starts from a clean slate, so tests can't interfere with each
other and your real data is never touched. (Fixture: `db_session`.)

### 2. Login → a fake "current user"
Endpoints normally identify the caller by decoding a JWT. In tests that step is
replaced so the caller is simply a known user — **Alice** (a room admin) by
default. (Fixture: `auth_user`.)

To test permissions, a test switches who is acting:

```python
auth_user["current"] = seed_users["carol"]   # now act as Carol (read-only)
```

### 3. Seed data → fixtures
Before a test runs, some data is pre-loaded so there's something to act on:

| Fixture | What it provides |
|---|---|
| `seed_users` | Alice, Bob, Carol |
| `seed_room`  | a "General" room — Alice = **admin**, Bob = **write**, Carol = **read** |
| `seed_message` | one message in the room |
| `outsider`   | a user in **no** room (for non-member denial tests) |

A test "asks for" what it needs by listing the fixture name as an argument.

### 4. Server → `TestClient`
Tests call endpoints in-process (e.g. `client.get("/rooms/unread/counts")`).
This runs the real route code and DB queries, just without a network.

---

## Anatomy of a test

Every test follows **Arrange → Act → Assert**:

```python
def test_mark_read_clears_unread(client, db_session, seed_room, seed_users):
    # ARRANGE: create two unread messages
    _add_message(db_session, seed_room.id, seed_users["bob"].id, "one")
    _add_message(db_session, seed_room.id, seed_users["bob"].id, "two")

    # ACT: mark the room read
    client.post(f"/rooms/{seed_room.id}/read")

    # ASSERT: the unread badge is gone
    res = client.get("/rooms/unread/counts")
    assert str(seed_room.id) not in res.json()
```

Permission tests do the same action as two different users and expect opposite
results (403 vs 200) — that's how the role system is verified.

---

## Writing a new test

1. Put it in `api/` if it calls an endpoint, or `unit/` if it tests a plain
   function.
2. Name the file `test_*.py` and the function `test_*` (pytest discovers these).
3. List the fixtures you need as function arguments (`client`, `db_session`,
   `seed_room`, `seed_users`, `auth_user`, `outsider`).
4. Switch identity with `auth_user["current"] = ...` when testing permissions.
5. Run it: `pytest testing/backend/api/your_file.py -v`.

---

## Notes / known gaps

- **WebSocket flows** (live message delivery, live membership enforcement) are
  not yet covered by automated tests — the REST surface around them is.
- **No frontend tests** yet (React side).
- **No CI** yet — a GitHub Action running `pytest testing/backend` would enforce
  green on every push.
