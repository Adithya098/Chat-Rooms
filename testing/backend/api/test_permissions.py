"""Permission-enforcement tests for admin-only moderation actions.

The role system (admin / write / read) is a core safety property: only an
approved admin may promote or remove members. These tests pin that boundary by
attempting each action as a non-admin (expect 403) and then as the admin
(expect success), switching identity via the `auth_user` fixture.
"""
from app.models.room_member import RoomMember


def test_promote_requires_admin(client, auth_user, seed_room, seed_users, db_session):
    target = seed_users["carol"]  # currently a read-only member

    # A non-admin (Bob, write role) must not be able to promote anyone.
    auth_user["current"] = seed_users["bob"]
    forbidden = client.post(f"/rooms/{seed_room.id}/promote", json={"user_id": target.id})
    assert forbidden.status_code == 403

    # The admin (Alice) can promote.
    auth_user["current"] = seed_users["alice"]
    ok = client.post(f"/rooms/{seed_room.id}/promote", json={"user_id": target.id})
    assert ok.status_code == 200

    promoted = (
        db_session.query(RoomMember)
        .filter(RoomMember.room_id == seed_room.id, RoomMember.user_id == target.id)
        .first()
    )
    assert promoted.role == "admin"


def test_remove_member_requires_admin(client, auth_user, seed_room, seed_users, db_session):
    target = seed_users["carol"]

    # A non-admin (Bob) cannot remove a member.
    auth_user["current"] = seed_users["bob"]
    forbidden = client.delete(f"/rooms/{seed_room.id}/members/{target.id}")
    assert forbidden.status_code == 403

    # Carol is still a member after the failed attempt.
    still_there = (
        db_session.query(RoomMember)
        .filter(RoomMember.room_id == seed_room.id, RoomMember.user_id == target.id)
        .first()
    )
    assert still_there is not None

    # The admin (Alice) can remove the member.
    auth_user["current"] = seed_users["alice"]
    ok = client.delete(f"/rooms/{seed_room.id}/members/{target.id}")
    assert ok.status_code == 200

    gone = (
        db_session.query(RoomMember)
        .filter(RoomMember.room_id == seed_room.id, RoomMember.user_id == target.id)
        .first()
    )
    assert gone is None
