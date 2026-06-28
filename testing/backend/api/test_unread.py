"""Unread-badge API tests.

Covers the read-watermark design: unread counts are derived from
RoomMember.last_read_message_id, and POST /rooms/{id}/read advances it.
The client authenticates as Alice (admin of seed_room) by default.
"""
from app.models.message import Message
from app.models.room_member import RoomMember


def _add_message(db_session, room_id, sender_id, content="hi"):
    """Inserts a message and returns it (ids are sequential ints)."""
    msg = Message(room_id=room_id, sender_id=sender_id, type="text", content=content)
    db_session.add(msg)
    db_session.commit()
    db_session.refresh(msg)
    return msg


def test_unread_counts_all_messages_when_nothing_read(client, db_session, seed_room, seed_users):
    # Fresh member: last_read_message_id is NULL, so every message is unread.
    _add_message(db_session, seed_room.id, seed_users["bob"].id, "one")
    _add_message(db_session, seed_room.id, seed_users["bob"].id, "two")

    res = client.get("/rooms/unread/counts")
    assert res.status_code == 200
    # JSON object keys are strings.
    assert res.json()[str(seed_room.id)] == 2


def test_unread_count_absent_when_no_messages(client, seed_room):
    # A room with no messages simply doesn't appear in the map.
    res = client.get("/rooms/unread/counts")
    assert res.status_code == 200
    assert str(seed_room.id) not in res.json()


def test_mark_read_clears_unread(client, db_session, seed_room, seed_users):
    _add_message(db_session, seed_room.id, seed_users["bob"].id, "one")
    _add_message(db_session, seed_room.id, seed_users["bob"].id, "two")

    read = client.post(f"/rooms/{seed_room.id}/read")
    assert read.status_code == 200

    res = client.get("/rooms/unread/counts")
    assert str(seed_room.id) not in res.json()


def test_new_message_after_read_counts_again(client, db_session, seed_room, seed_users):
    _add_message(db_session, seed_room.id, seed_users["bob"].id, "one")
    client.post(f"/rooms/{seed_room.id}/read")

    # A message that arrives after the watermark is unread again.
    _add_message(db_session, seed_room.id, seed_users["bob"].id, "two")
    res = client.get("/rooms/unread/counts")
    assert res.json()[str(seed_room.id)] == 1


def test_mark_read_sets_watermark_to_latest(client, db_session, seed_room, seed_users):
    _add_message(db_session, seed_room.id, seed_users["bob"].id, "one")
    latest = _add_message(db_session, seed_room.id, seed_users["bob"].id, "two")

    res = client.post(f"/rooms/{seed_room.id}/read")
    assert res.json()["last_read_message_id"] == latest.id

    member = (
        db_session.query(RoomMember)
        .filter(
            RoomMember.room_id == seed_room.id,
            RoomMember.user_id == seed_users["alice"].id,
        )
        .first()
    )
    assert member.last_read_message_id == latest.id


def test_deleted_messages_do_not_count_as_unread(client, db_session, seed_room, seed_users):
    _add_message(db_session, seed_room.id, seed_users["bob"].id, "keep")
    gone = _add_message(db_session, seed_room.id, seed_users["bob"].id, "deleted")
    gone.is_deleted = True
    db_session.commit()

    res = client.get("/rooms/unread/counts")
    # Only the non-deleted message counts.
    assert res.json()[str(seed_room.id)] == 1


def test_mark_read_forbidden_for_non_member(client, auth_user, seed_room, seed_users, db_session):
    # Act as a brand-new user who is not a member of the room.
    outsider = seed_users["bob"]
    db_session.query(RoomMember).filter(
        RoomMember.room_id == seed_room.id,
        RoomMember.user_id == outsider.id,
    ).delete()
    db_session.commit()
    auth_user["current"] = outsider

    res = client.post(f"/rooms/{seed_room.id}/read")
    assert res.status_code == 403
