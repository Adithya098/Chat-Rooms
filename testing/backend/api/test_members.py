"""Membership workflow tests.

Acting identity (the joiner, the moderating admin) comes from the JWT, which the
test client overrides via the `auth_user` fixture. Request bodies carry only the
target: a role to join with, or the user_id being approved/rejected.
"""
from app.models.room_member import RoomMember
from app.models.user import User


def _signup(client, db_session, name, email):
    """Signs up a user and returns the persisted User (for switching identity)."""
    uid = client.post(
        "/users/signup",
        json={"name": name, "email": email, "password": "Passw0rd!", "mobile": "0000000000"},
    ).json()["user"]["id"]
    return db_session.query(User).filter(User.id == uid).first()


def test_join_room_creates_pending_membership(client, auth_user, seed_room, seed_users, db_session):
    # An already-approved member (Alice) cannot re-join.
    already = client.post(f"/rooms/{seed_room.id}/join", json={"role": "write"})
    assert already.status_code == 400

    # A brand-new user requests to join and lands in 'pending'.
    dave = _signup(client, db_session, "Dave", "dave@example.com")
    auth_user["current"] = dave
    join = client.post(f"/rooms/{seed_room.id}/join", json={"role": "write"})
    assert join.status_code == 201

    created = db_session.query(RoomMember).filter(RoomMember.user_id == dave.id).first()
    assert created is not None
    assert created.status == "pending"


def test_approve_and_reject_require_admin(client, auth_user, seed_room, seed_users, db_session):
    # Eve requests to join (acting as Eve).
    eve = _signup(client, db_session, "Eve", "eve@example.com")
    auth_user["current"] = eve
    client.post(f"/rooms/{seed_room.id}/join", json={"role": "read"})

    # A non-admin (Carol) cannot approve.
    auth_user["current"] = seed_users["carol"]
    no_admin = client.post(f"/rooms/{seed_room.id}/approve", json={"user_id": eve.id})
    assert no_admin.status_code == 403

    # The admin (Alice) approves.
    auth_user["current"] = seed_users["alice"]
    approved = client.post(f"/rooms/{seed_room.id}/approve", json={"user_id": eve.id})
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    # The admin rejects a different pending user (Frank).
    frank = _signup(client, db_session, "Frank", "frank@example.com")
    auth_user["current"] = frank
    client.post(f"/rooms/{seed_room.id}/join", json={"role": "read"})

    auth_user["current"] = seed_users["alice"]
    rejected = client.post(f"/rooms/{seed_room.id}/reject", json={"user_id": frank.id})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


def test_last_admin_cannot_leave(client, seed_room, seed_users):
    # Acting as Alice, the room's only admin.
    res = client.post(f"/rooms/{seed_room.id}/leave")
    assert res.status_code == 400
    assert "only admin" in res.json()["detail"]
