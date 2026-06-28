from app.models.document import Document
from app.models.message import Message


def test_get_messages_returns_chronological_rows(client, db_session, seed_room, seed_users):
    older = Message(
        room_id=seed_room.id,
        sender_id=seed_users["alice"].id,
        type="text",
        content="older",
    )
    newer = Message(
        room_id=seed_room.id,
        sender_id=seed_users["bob"].id,
        type="text",
        content="newer",
    )
    db_session.add_all([older, newer])
    db_session.commit()

    res = client.get(f"/rooms/{seed_room.id}/messages", params={"limit": 10, "offset": 0})
    assert res.status_code == 200
    payload = res.json()
    contents = [item["content"] for item in payload]
    assert "older" in contents
    assert "newer" in contents


def test_get_messages_includes_reply_snippet_for_file(client, db_session, seed_room, seed_users):
    file_msg = Message(
        room_id=seed_room.id,
        sender_id=seed_users["bob"].id,
        type="file",
        content="/documents/file-123",
    )
    db_session.add(file_msg)
    db_session.commit()
    db_session.refresh(file_msg)

    doc = Document(
        file_id="file-123",
        room_id=seed_room.id,
        sender_id=seed_users["bob"].id,
        original_filename="photo.png",
    )
    reply = Message(
        room_id=seed_room.id,
        sender_id=seed_users["alice"].id,
        type="text",
        content="replying",
        reply_to=file_msg.id,
    )
    db_session.add_all([doc, reply])
    db_session.commit()

    res = client.get(f"/rooms/{seed_room.id}/messages")
    assert res.status_code == 200
    reply_message = next(item for item in res.json() if item["content"] == "replying")
    assert reply_message["reply_to"] == file_msg.id
    assert reply_message["reply_snippet"]["filename"] == "photo.png"
    assert reply_message["reply_snippet"]["is_image"] is True


def test_delete_message_requires_admin(client, auth_user, db_session, seed_room, seed_users):
    msg = Message(
        room_id=seed_room.id,
        sender_id=seed_users["bob"].id,
        type="text",
        content="delete me",
    )
    db_session.add(msg)
    db_session.commit()
    db_session.refresh(msg)

    # The deleter is the authenticated caller, not a client-supplied admin_id.
    auth_user["current"] = seed_users["carol"]  # read-only member
    forbidden = client.delete(f"/rooms/{seed_room.id}/messages/{msg.id}")
    assert forbidden.status_code == 403

    auth_user["current"] = seed_users["alice"]  # room admin
    ok = client.delete(f"/rooms/{seed_room.id}/messages/{msg.id}")
    assert ok.status_code == 200
