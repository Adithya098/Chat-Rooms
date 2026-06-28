"""Message-edit tests.

Editing is sender-only (you can't rewrite someone else's words, not even as an
admin) and text-only. A successful edit sets edited_at, which drives the
"(edited)" label. The client acts as Alice (admin of seed_room) by default;
tests switch the acting user via auth_user["current"].
"""
from app.models.message import Message


def _add_message(db_session, room_id, sender_id, content, msg_type="text"):
    msg = Message(room_id=room_id, sender_id=sender_id, type=msg_type, content=content)
    db_session.add(msg)
    db_session.commit()
    db_session.refresh(msg)
    return msg


def test_sender_can_edit_own_message(client, db_session, seed_room, seed_users):
    # Alice (default caller) edits her own message.
    msg = _add_message(db_session, seed_room.id, seed_users["alice"].id, "original")

    res = client.patch(f"/rooms/{seed_room.id}/messages/{msg.id}", json={"content": "fixed"})
    assert res.status_code == 200

    history = client.get(f"/rooms/{seed_room.id}/messages").json()
    edited = next(m for m in history if m["id"] == msg.id)
    assert edited["content"] == "fixed"
    assert edited["edited_at"] is not None


def test_edited_at_is_null_before_editing(client, db_session, seed_room, seed_users):
    _add_message(db_session, seed_room.id, seed_users["alice"].id, "untouched")
    history = client.get(f"/rooms/{seed_room.id}/messages").json()
    assert history[0]["edited_at"] is None


def test_non_sender_cannot_edit_even_as_admin(client, db_session, seed_room, seed_users):
    # Bob's message; Alice is admin but may not edit someone else's words.
    msg = _add_message(db_session, seed_room.id, seed_users["bob"].id, "bob's words")

    res = client.patch(f"/rooms/{seed_room.id}/messages/{msg.id}", json={"content": "hijacked"})
    assert res.status_code == 403

    db_session.expire_all()
    assert db_session.query(Message).filter(Message.id == msg.id).first().content == "bob's words"


def test_edit_empty_content_rejected(client, db_session, seed_room, seed_users):
    msg = _add_message(db_session, seed_room.id, seed_users["alice"].id, "keep me")
    res = client.patch(f"/rooms/{seed_room.id}/messages/{msg.id}", json={"content": "   "})
    assert res.status_code == 400


def test_file_messages_cannot_be_edited(client, db_session, seed_room, seed_users):
    # Alice owns the file message, so the caller passes the sender check and hits
    # the text-only guard.
    msg = _add_message(
        db_session, seed_room.id, seed_users["alice"].id, "/documents/abc", msg_type="file"
    )
    res = client.patch(f"/rooms/{seed_room.id}/messages/{msg.id}", json={"content": "nope"})
    assert res.status_code == 400


def test_edit_nonexistent_message_404(client, seed_room):
    res = client.patch(f"/rooms/{seed_room.id}/messages/999999", json={"content": "hi"})
    assert res.status_code == 404


def test_edit_deleted_message_404(client, db_session, seed_room, seed_users):
    msg = _add_message(db_session, seed_room.id, seed_users["alice"].id, "to delete")
    msg.is_deleted = True
    db_session.commit()
    res = client.patch(f"/rooms/{seed_room.id}/messages/{msg.id}", json={"content": "back"})
    assert res.status_code == 404
