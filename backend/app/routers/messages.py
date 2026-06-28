"""Message retrieval and moderation endpoints for room conversations.

This module returns paginated message history with sender names,
resolves file metadata for file-type messages, enriches replies with compact original-message snippets,
and allows admins to delete messages while broadcasting realtime deletion events.

All endpoints require a valid JWT. The admin identity for delete is extracted
from the token — admin_id is no longer a client-supplied query parameter."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.connection_manager import manager
from app.models.document import Document
from app.models.message import Message
from app.models.room import Room
from app.models.room_member import RoomMember
from app.models.user import User
from app.schemas.message import MessageResponse, MessageEdit, ReplySnippet
from app.auth import get_current_user

router = APIRouter(prefix="/rooms/{room_id}/messages", tags=["messages"])

_DOC_PREFIX = "/documents/"
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _file_id_from_message_content(content: str) -> str | None:
    """Extracts the document file ID from a message content path when the prefix matches."""
    if not content.startswith(_DOC_PREFIX):
        return None
    rest = content[len(_DOC_PREFIX):].split("?")[0].strip("/")
    return rest or None


def _is_image_filename(filename: str | None) -> bool:
    """Determines whether a filename extension represents an image preview type."""
    if not filename:
        return False
    dot = filename.rfind(".")
    if dot == -1:
        return False
    return filename[dot:].lower() in _IMAGE_EXTENSIONS


@router.get("/", response_model=list[MessageResponse])
def get_messages(
    room_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns paginated room messages — caller must be an authenticated user."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Direct rooms are private: only their two members may read the history.
    # A 404 (not 403) avoids confirming the room exists to an outsider.
    if room.room_type == "direct":
        is_member = db.query(RoomMember).filter(
            RoomMember.room_id == room_id,
            RoomMember.user_id == current_user.id,
        ).first()
        if not is_member:
            raise HTTPException(status_code=404, detail="Room not found")

    rows = (
        db.query(Message, User.name)
        .join(User, Message.sender_id == User.id)
        .filter(Message.room_id == room_id)
        .filter(Message.is_deleted.is_(False))
        .order_by(Message.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    rows_chrono = list(reversed(rows))

    file_ids = [
        fid
        for msg, _ in rows_chrono
        if msg.type == "file" and (fid := _file_id_from_message_content(msg.content))
    ]
    filenames: dict[str, str] = {}
    if file_ids:
        for doc in db.query(Document).filter(Document.file_id.in_(file_ids)).all():
            filenames[doc.file_id] = doc.original_filename

    reply_ids = [msg.reply_to for msg, _ in rows_chrono if msg.reply_to is not None]
    reply_map: dict[int, ReplySnippet] = {}
    if reply_ids:
        from sqlalchemy.orm import aliased
        OrigUser = aliased(User)
        orig_rows = (
            db.query(Message, OrigUser.name)
            .join(OrigUser, Message.sender_id == OrigUser.id)
            .filter(Message.id.in_(reply_ids))
            .filter(Message.room_id == room_id)
            .all()
        )
        reply_file_ids = [
            fid
            for orig_msg, _ in orig_rows
            if orig_msg.type == "file" and (fid := _file_id_from_message_content(orig_msg.content))
        ]
        reply_filenames: dict[str, str] = {}
        if reply_file_ids:
            for doc in db.query(Document).filter(Document.file_id.in_(reply_file_ids)).all():
                reply_filenames[doc.file_id] = doc.original_filename

        for orig_msg, orig_name in orig_rows:
            file_id = _file_id_from_message_content(orig_msg.content) if orig_msg.type == "file" else None
            filename = reply_filenames.get(file_id) if file_id else None
            is_image = _is_image_filename(filename)
            preview = (filename or "Attachment") if orig_msg.type == "file" else orig_msg.content[:120]
            reply_map[orig_msg.id] = ReplySnippet(
                id=orig_msg.id,
                sender_name=orig_name,
                content=preview,
                type=orig_msg.type,
                filename=filename,
                file_url=orig_msg.content if orig_msg.type == "file" else None,
                is_image=is_image,
            )

    out: list[MessageResponse] = []
    for msg, sender_name in rows_chrono:
        fid = _file_id_from_message_content(msg.content) if msg.type == "file" else None
        out.append(
            MessageResponse(
                id=msg.id,
                room_id=msg.room_id,
                sender_id=msg.sender_id,
                sender_name=sender_name,
                type=msg.type,
                content=msg.content,
                created_at=msg.created_at,
                edited_at=msg.edited_at,
                filename=filenames.get(fid) if fid else None,
                reply_to=msg.reply_to,
                reply_snippet=reply_map.get(msg.reply_to) if msg.reply_to else None,
            )
        )
    return out


@router.delete("/{message_id}")
async def delete_message(
    room_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-deletes a room message — caller must be the sender or an approved admin.

    Senders can delete their own messages in any room (the only deletion path in
    direct chats, which have no admin); admins additionally moderate others'
    messages in group rooms.
    """
    msg = db.query(Message).filter(
        Message.id == message_id,
        Message.room_id == room_id,
    ).first()
    if not msg or msg.is_deleted:
        raise HTTPException(status_code=404, detail="Message not found")

    is_sender = msg.sender_id == current_user.id
    is_admin = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == current_user.id,
        RoomMember.role == "admin",
        RoomMember.status == "approved",
    ).first() is not None
    if not (is_sender or is_admin):
        raise HTTPException(status_code=403, detail="You can only delete your own messages")

    msg.is_deleted = True
    db.commit()

    await manager.broadcast(room_id, {"type": "message_deleted", "message_id": message_id})

    return {"detail": "Message deleted", "message_id": message_id}


@router.patch("/{message_id}")
async def edit_message(
    room_id: int,
    message_id: int,
    req: MessageEdit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edits a text message's content — caller must be the original sender.

    Only the author may edit (you can't rewrite someone else's words), and only
    text messages are editable. Sets edited_at so the UI can show an "(edited)"
    label, then broadcasts the change so every open client updates in place.
    """
    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    msg = db.query(Message).filter(
        Message.id == message_id,
        Message.room_id == room_id,
    ).first()
    if not msg or msg.is_deleted:
        raise HTTPException(status_code=404, detail="Message not found")
    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own messages")
    if msg.type != "text":
        raise HTTPException(status_code=400, detail="Only text messages can be edited")

    msg.content = content
    msg.edited_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)

    await manager.broadcast(room_id, {
        "type": "message_edited",
        "id": msg.id,
        "content": msg.content,
        "edited_at": msg.edited_at.isoformat(),
    })

    return {"detail": "Message edited", "message_id": message_id}
