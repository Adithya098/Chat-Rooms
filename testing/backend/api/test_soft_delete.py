"""Soft-delete tests: preservation behavior AND deletion authorization.

Two concerns are pinned here:

1. Soft-delete mechanics — messages are flagged (is_deleted) rather than removed,
   so a reply that quotes a now-deleted message still renders its snippet and the
   row survives in the database.
2. Authorization — a message may be deleted by its **sender** (the only deletion
   path in direct rooms, which have no admin) or by an approved **admin** (group
   moderation of others' messages). Anyone else is rejected with 403.

The client acts as Alice (admin of seed_room) by default; tests switch the acting
user via `auth_user["current"]`.
"""
from app.models.message import Message
from app.models.room import Room
from app.models.room_member import RoomMember


def _add_message(db_session, room_id, sender_id, content, reply_to=None):
    msg = Message(
        room_id=room_id,
        sender_id=sender_id,
        type="text",
        content=content,
        reply_to=reply_to,
    )
    db_session.add(msg)
    db_session.commit()
    db_session.refresh(msg)
    return msg


def _make_direct_room(db_session, user_a_id, user_b_id):
    """Creates a direct room with two approved write members (no admin)."""
    room = Room(name=None, room_type="direct", created_by=user_a_id)
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    db_session.add_all([
        RoomMember(room_id=room.id, user_id=user_a_id, role="write", status="approved"),
        RoomMember(room_id=room.id, user_id=user_b_id, role="write", status="approved"),
    ])
    db_session.commit()
    return room


def test_soft_deleted_message_disappears_but_reply_snippet_survives(
    client, db_session, seed_room, seed_users
):
    # Original message, and a reply that quotes it.
    original = _add_message(db_session, seed_room.id, seed_users["bob"].id, "the original")
    _add_message(
        db_session, seed_room.id, seed_users["alice"].id, "quoting you", reply_to=original.id
    )

    # Before deletion: both messages present, reply carries the snippet.
    before = client.get(f"/rooms/{seed_room.id}/messages").json()
    contents = [m["content"] for m in before]
    assert "the original" in contents
    reply = next(m for m in before if m["content"] == "quoting you")
    assert reply["reply_snippet"]["content"] == "the original"

    # Admin soft-deletes the original.
    deleted = client.delete(f"/rooms/{seed_room.id}/messages/{original.id}")
    assert deleted.status_code == 200

    # After deletion: original is gone from the timeline...
    after = client.get(f"/rooms/{seed_room.id}/messages").json()
    after_contents = [m["content"] for m in after]
    assert "the original" not in after_contents

    # ...but the reply still renders the preserved preview of it.
    reply_after = next(m for m in after if m["content"] == "quoting you")
    assert reply_after["reply_snippet"] is not None
    assert reply_after["reply_snippet"]["content"] == "the original"


def test_soft_delete_keeps_row_in_database(client, db_session, seed_room, seed_users):
    msg = _add_message(db_session, seed_room.id, seed_users["bob"].id, "delete me")

    client.delete(f"/rooms/{seed_room.id}/messages/{msg.id}")

    # The row is retained (flagged), not physically removed — that's what lets
    # reply snippets keep resolving.
    db_session.expire_all()
    row = db_session.query(Message).filter(Message.id == msg.id).first()
    assert row is not None
    assert row.is_deleted is True


# --- Authorization: sender or admin ------------------------------------------

def test_sender_can_delete_own_message(client, auth_user, db_session, seed_room, seed_users):
    # Bob is a writer (not admin); he can still delete a message he sent.
    msg = _add_message(db_session, seed_room.id, seed_users["bob"].id, "mine to delete")
    auth_user["current"] = seed_users["bob"]

    res = client.delete(f"/rooms/{seed_room.id}/messages/{msg.id}")
    assert res.status_code == 200

    after = client.get(f"/rooms/{seed_room.id}/messages").json()
    assert "mine to delete" not in [m["content"] for m in after]


def test_non_sender_non_admin_cannot_delete(client, auth_user, db_session, seed_room, seed_users):
    # Alice's message; Bob (writer, not admin) must not be able to delete it.
    msg = _add_message(db_session, seed_room.id, seed_users["alice"].id, "not yours")
    auth_user["current"] = seed_users["bob"]

    res = client.delete(f"/rooms/{seed_room.id}/messages/{msg.id}")
    assert res.status_code == 403

    db_session.expire_all()
    assert db_session.query(Message).filter(Message.id == msg.id).first().is_deleted is False


def test_admin_can_delete_others_message(client, db_session, seed_room, seed_users):
    # Default client is Alice (admin). She moderates Bob's message.
    msg = _add_message(db_session, seed_room.id, seed_users["bob"].id, "moderate me")
    res = client.delete(f"/rooms/{seed_room.id}/messages/{msg.id}")
    assert res.status_code == 200


def test_sender_can_delete_own_message_in_direct_room(client, db_session, seed_users):
    # Direct rooms have no admin, so sender-deletes-own is the only path.
    dm = _make_direct_room(db_session, seed_users["alice"].id, seed_users["bob"].id)
    msg = _add_message(db_session, dm.id, seed_users["alice"].id, "oops")

    res = client.delete(f"/rooms/{dm.id}/messages/{msg.id}")  # Alice = sender
    assert res.status_code == 200


def test_cannot_delete_other_participants_message_in_direct_room(
    client, auth_user, db_session, seed_users
):
    dm = _make_direct_room(db_session, seed_users["alice"].id, seed_users["bob"].id)
    msg = _add_message(db_session, dm.id, seed_users["alice"].id, "alice said this")

    # Bob can delete his own messages, but not Alice's.
    auth_user["current"] = seed_users["bob"]
    res = client.delete(f"/rooms/{dm.id}/messages/{msg.id}")
    assert res.status_code == 403


def test_delete_nonexistent_message_404(client, seed_room):
    res = client.delete(f"/rooms/{seed_room.id}/messages/999999")
    assert res.status_code == 404


def test_delete_already_deleted_message_404(client, db_session, seed_room, seed_users):
    msg = _add_message(db_session, seed_room.id, seed_users["bob"].id, "twice")
    assert client.delete(f"/rooms/{seed_room.id}/messages/{msg.id}").status_code == 200
    # A second delete finds it already flagged → treated as not found.
    assert client.delete(f"/rooms/{seed_room.id}/messages/{msg.id}").status_code == 404
