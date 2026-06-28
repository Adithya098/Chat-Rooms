"""File upload and document access tests.

The uploader/reader identity comes from the JWT (overridden via `auth_user`),
not from a form field — so authorization is exercised by switching the acting user.
"""
import io
from app.models.document import Document


def test_upload_rejects_disallowed_extension(client, auth_user, seed_room, seed_users):
    auth_user["current"] = seed_users["bob"]  # writer
    files = {"file": ("bad.exe", io.BytesIO(b"abc"), "application/octet-stream")}
    res = client.post(f"/rooms/{seed_room.id}/upload", files=files)
    assert res.status_code == 400
    assert "not allowed" in res.json()["detail"]


def test_upload_requires_write_permission(client, auth_user, seed_room, seed_users):
    auth_user["current"] = seed_users["carol"]  # read-only member
    files = {"file": ("ok.txt", io.BytesIO(b"abc"), "text/plain")}
    res = client.post(f"/rooms/{seed_room.id}/upload", files=files)
    assert res.status_code == 403


def test_list_documents_requires_membership(client, auth_user, seed_room, outsider):
    auth_user["current"] = outsider  # not a member of any room
    res = client.get(f"/rooms/{seed_room.id}/documents")
    assert res.status_code == 403


def test_open_document_forbidden_for_non_member(client, auth_user, db_session, seed_room, seed_users, outsider):
    doc = Document(
        file_id="doc-forbidden",
        room_id=seed_room.id,
        sender_id=seed_users["alice"].id,
        original_filename="note.txt",
    )
    db_session.add(doc)
    db_session.commit()

    auth_user["current"] = outsider  # not a member of the room
    res = client.get("/documents/doc-forbidden")
    assert res.status_code == 403
