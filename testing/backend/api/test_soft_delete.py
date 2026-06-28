"""Soft-delete tests: deleting a message preserves replies that quote it.

Messages are soft-deleted (is_deleted flag) rather than removed, so a reply that
quotes a now-deleted message can still render its preview snippet instead of
breaking the thread. These tests pin both halves of that behavior:
the deleted message disappears from the timeline, but the reply's snippet remains.
The client acts as Alice (room admin) by default.
"""
from app.models.message import Message


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
