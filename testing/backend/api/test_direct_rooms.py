"""Direct-message feature tests.

Covers the 1:1 direct-room model and its supporting endpoints:
- POST /rooms/direct          — find-or-create the room (idempotent), self/unknown guards
- GET /users/by-mobile/{n}    — phone lookup used to start a DM
- PATCH /users/me             — self profile editing
- privacy guards              — direct rooms are visible/readable only to their two members,
                                and the group join/leave workflow is blocked on them

The client authenticates as Alice by default; tests switch the acting user via
`auth_user["current"]`. Direct rooms are created through the real endpoint so the
find-or-create and membership behavior is exercised end to end.
"""
from app.models.message import Message
from app.models.room_member import RoomMember
from app.models.user import User


def _create_direct(client, other_id):
    """Creates or finds the caller's direct room with another user."""
    return client.post("/rooms/direct", json={"user_id": other_id})


# --- POST /rooms/direct -------------------------------------------------------

def test_create_direct_room_has_direct_type_and_two_approved_members(
    client, db_session, seed_users
):
    bob = seed_users["bob"]
    res = _create_direct(client, bob.id)
    assert res.status_code == 201

    body = res.json()
    assert body["room_type"] == "direct"
    assert body["name"] is None

    members = db_session.query(RoomMember).filter(RoomMember.room_id == body["id"]).all()
    assert {m.user_id for m in members} == {seed_users["alice"].id, bob.id}
    assert all(m.status == "approved" and m.role == "write" for m in members)


def test_create_direct_room_is_idempotent(client, seed_users):
    bob = seed_users["bob"]
    first = _create_direct(client, bob.id).json()
    second = _create_direct(client, bob.id).json()
    # Same pair → same room, never a duplicate.
    assert first["id"] == second["id"]


def test_create_direct_room_with_self_rejected(client, seed_users):
    res = _create_direct(client, seed_users["alice"].id)
    assert res.status_code == 400


def test_create_direct_room_with_unknown_user_404(client):
    res = _create_direct(client, 999999)
    assert res.status_code == 404


# --- GET /users/by-mobile/{number} -------------------------------------------

def test_find_user_by_mobile(client, seed_users):
    res = client.get(f"/users/by-mobile/{seed_users['bob'].mobile}")
    assert res.status_code == 200
    assert res.json()["id"] == seed_users["bob"].id


def test_find_user_by_own_mobile_rejected(client, seed_users):
    res = client.get(f"/users/by-mobile/{seed_users['alice'].mobile}")
    assert res.status_code == 400


def test_find_user_by_unknown_mobile_404(client):
    res = client.get("/users/by-mobile/0000000000")
    assert res.status_code == 404


# --- PATCH /users/me ----------------------------------------------------------

def test_update_own_profile(client, db_session, seed_users):
    res = client.patch("/users/me", json={"name": "Alice X", "mobile": "5550001111"})
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Alice X"
    assert body["mobile"] == "5550001111"

    db_session.expire_all()
    alice = db_session.query(User).filter(User.id == seed_users["alice"].id).first()
    assert alice.name == "Alice X"
    assert alice.mobile == "5550001111"


def test_update_profile_blank_name_rejected(client):
    res = client.patch("/users/me", json={"name": "   "})
    assert res.status_code == 400


def test_update_profile_partial_keeps_other_field(client):
    # Only mobile sent → name is left untouched.
    res = client.patch("/users/me", json={"mobile": "5559998888"})
    assert res.status_code == 200
    body = res.json()
    assert body["mobile"] == "5559998888"
    assert body["name"] == "Alice"


# --- Privacy guards -----------------------------------------------------------

def test_direct_room_excluded_from_non_member_room_list(
    client, auth_user, seed_room, seed_users
):
    # Alice opens a DM with Bob; Carol is not part of it.
    dm = _create_direct(client, seed_users["bob"].id).json()

    auth_user["current"] = seed_users["carol"]
    ids = [r["id"] for r in client.get("/rooms/").json()]
    assert dm["id"] not in ids          # someone else's DM is hidden
    assert seed_room.id in ids          # group rooms stay discoverable


def test_direct_room_visible_to_its_members(client, seed_users):
    dm = _create_direct(client, seed_users["bob"].id).json()
    ids = [r["id"] for r in client.get("/rooms/").json()]   # still Alice
    assert dm["id"] in ids


def test_direct_room_detail_404_for_non_member(client, auth_user, seed_users):
    dm = _create_direct(client, seed_users["bob"].id).json()
    auth_user["current"] = seed_users["carol"]
    res = client.get(f"/rooms/{dm['id']}")
    assert res.status_code == 404


def test_direct_room_messages_404_for_non_member(client, auth_user, db_session, seed_users):
    dm = _create_direct(client, seed_users["bob"].id).json()
    db_session.add(
        Message(room_id=dm["id"], sender_id=seed_users["alice"].id, type="text", content="secret")
    )
    db_session.commit()

    auth_user["current"] = seed_users["carol"]
    res = client.get(f"/rooms/{dm['id']}/messages")
    assert res.status_code == 404


def test_member_can_read_direct_room_messages(client, auth_user, db_session, seed_users):
    dm = _create_direct(client, seed_users["bob"].id).json()
    db_session.add(
        Message(room_id=dm["id"], sender_id=seed_users["alice"].id, type="text", content="hi bob")
    )
    db_session.commit()

    # Bob is the other participant — he can read it.
    auth_user["current"] = seed_users["bob"]
    res = client.get(f"/rooms/{dm['id']}/messages")
    assert res.status_code == 200
    assert [m["content"] for m in res.json()] == ["hi bob"]


def test_join_blocked_on_direct_room(client, auth_user, seed_users):
    dm = _create_direct(client, seed_users["bob"].id).json()
    auth_user["current"] = seed_users["carol"]
    res = client.post(f"/rooms/{dm['id']}/join", json={"role": "write"})
    assert res.status_code == 400


def test_leave_blocked_on_direct_room(client, seed_users):
    dm = _create_direct(client, seed_users["bob"].id).json()
    # Alice is a member, but you don't "leave" a direct chat.
    res = client.post(f"/rooms/{dm['id']}/leave")
    assert res.status_code == 400
