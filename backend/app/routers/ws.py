"""Realtime websocket endpoint for room chat event handling.

This module authenticates websocket users via a ?token= JWT query parameter
(Authorization headers are unavailable after the WebSocket upgrade),
manages connect/disconnect presence updates, receives message/typing/file events from clients,
persists chat messages, broadcasts payloads to room participants, and cleans up connection state on disconnect/errors."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.room_member import RoomMember
from app.models.user import User
from app.models.message import Message
from app.models.document import Document
from app.connection_manager import manager
from app.auth import _decode_token

router = APIRouter(tags=["websocket"])
_DOC_PREFIX = "/documents/"
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _file_id_from_message_content(content: str) -> str | None:
    """Extracts document file ID from a /documents/<id> message content path."""
    if not content.startswith(_DOC_PREFIX):
        return None
    rest = content[len(_DOC_PREFIX):].split("?")[0].strip("/")
    return rest or None


def _is_image_filename(filename: str | None) -> bool:
    """Determines if a filename should be rendered as an image preview."""
    if not filename:
        return False
    dot = filename.rfind(".")
    if dot == -1:
        return False
    return filename[dot:].lower() in _IMAGE_EXTENSIONS


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: int,
    token: str | None = Query(default=None),
):
    """Handles websocket lifecycle for a room member, authenticating via ?token= JWT."""
    db: Session = SessionLocal()
    accepted = False

    try:
        # Accept first so all failures can return a proper websocket close frame.
        await websocket.accept()
        accepted = True

        # 1. Validate JWT token
        if not token:
            await websocket.close(code=4001, reason="Authentication required")
            return

        user_id = _decode_token(token)
        if user_id is None:
            await websocket.close(code=4001, reason="Invalid or expired token")
            return

        # 2. Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await websocket.close(code=4001, reason="User not found")
            return

        # 3. Verify user is an approved member of this room
        member = db.query(RoomMember).filter(
            RoomMember.room_id == room_id,
            RoomMember.user_id == user_id,
            RoomMember.status == "approved",
        ).first()
        if not member:
            await websocket.close(code=4003, reason="Not an approved member of this room")
            return

        user_name = user.name

        # 4. Connect
        await manager.connect(room_id, user_id, websocket)

        # 5. Broadcast online users list to everyone in the room
        online = manager.get_online_users(room_id)
        await manager.broadcast(room_id, {
            "type": "online_users",
            "users": online,
        })

    except Exception:
        if accepted:
            await websocket.close(code=1011, reason="Internal server error")
        db.close()
        return

    db.close()

    # 6. Listen for messages
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "message":
                # Re-query membership on every message to catch role changes or kicks
                # that occurred after the WebSocket was established (stale-session fix).
                event_db = SessionLocal()
                try:
                    live_member = event_db.query(RoomMember).filter(
                        RoomMember.room_id == room_id,
                        RoomMember.user_id == user_id,
                        RoomMember.status == "approved",
                    ).first()
                finally:
                    event_db.close()

                if not live_member:
                    await manager.send_to_user(room_id, user_id, {
                        "type": "kicked",
                        "content": "Your membership in this room has been revoked",
                    })
                    manager.disconnect(room_id, user_id, websocket)
                    return

                if live_member.role not in ("write", "admin"):
                    await manager.send_to_user(room_id, user_id, {
                        "type": "error",
                        "content": "You don't have write permission in this room",
                    })
                    continue

                msg_db = SessionLocal()
                try:
                    reply_to_id = data.get("reply_to")
                    reply_snippet = None
                    if reply_to_id is not None:
                        orig = msg_db.query(Message).filter(
                            Message.id == reply_to_id,
                            Message.room_id == room_id,
                        ).first()
                        if orig:
                            orig_user = msg_db.query(User).filter(User.id == orig.sender_id).first()
                            filename = None
                            is_image = False
                            file_url = None
                            if orig.type == "file":
                                file_url = orig.content
                                file_id = _file_id_from_message_content(orig.content)
                                if file_id:
                                    doc = msg_db.query(Document).filter(Document.file_id == file_id).first()
                                    if doc:
                                        filename = doc.original_filename
                                is_image = _is_image_filename(filename)
                            preview = (filename or "Attachment") if orig.type == "file" else orig.content[:120]
                            reply_snippet = {
                                "id": orig.id,
                                "sender_name": orig_user.name if orig_user else f"User {orig.sender_id}",
                                "content": preview,
                                "type": orig.type,
                                "filename": filename,
                                "file_url": file_url,
                                "is_image": is_image,
                            }

                    content = data.get("content", "").strip()
                    if not content:
                        continue

                    db_msg = Message(
                        room_id=room_id,
                        sender_id=user_id,
                        type="text",
                        content=content,
                        reply_to=reply_to_id,
                    )
                    msg_db.add(db_msg)
                    msg_db.commit()
                    msg_db.refresh(db_msg)

                    # Sending implies the author has read up to their own message, so
                    # advance their read watermark here (authoritative, race-free) rather
                    # than relying on the client's mark-read call. Without this, a sender's
                    # own trailing messages can show up as unread to themselves.
                    msg_db.query(RoomMember).filter(
                        RoomMember.room_id == room_id,
                        RoomMember.user_id == user_id,
                    ).update({RoomMember.last_read_message_id: db_msg.id})
                    msg_db.commit()

                    await manager.broadcast(room_id, {
                        "type": "message",
                        "id": db_msg.id,
                        "sender_id": user_id,
                        "sender_name": user_name,
                        "content": db_msg.content,
                        "created_at": db_msg.created_at.isoformat(),
                        "reply_to": reply_to_id,
                        "reply_snippet": reply_snippet,
                    })
                finally:
                    msg_db.close()

            elif msg_type == "typing":
                await manager.broadcast(room_id, {
                    "type": "typing",
                    "user_id": user_id,
                    "user_name": user_name,
                }, exclude_websocket=websocket)

            elif msg_type == "stop_typing":
                await manager.broadcast(room_id, {
                    "type": "stop_typing",
                    "user_id": user_id,
                    "user_name": user_name,
                }, exclude_websocket=websocket)

            elif msg_type == "file":
                # Re-query membership on every file event (same stale-session fix).
                event_db = SessionLocal()
                try:
                    live_member = event_db.query(RoomMember).filter(
                        RoomMember.room_id == room_id,
                        RoomMember.user_id == user_id,
                        RoomMember.status == "approved",
                    ).first()
                finally:
                    event_db.close()

                if not live_member:
                    await manager.send_to_user(room_id, user_id, {
                        "type": "kicked",
                        "content": "Your membership in this room has been revoked",
                    })
                    manager.disconnect(room_id, user_id, websocket)
                    return

                if live_member.role not in ("write", "admin"):
                    await manager.send_to_user(room_id, user_id, {
                        "type": "error",
                        "content": "You don't have write permission in this room",
                    })
                    continue

                message_id = data.get("message_id")
                file_url = data.get("file_url", "")
                filename = data.get("filename", "")

                # Verify the message_id belongs to this room and this sender
                if message_id is not None:
                    msg_db = SessionLocal()
                    try:
                        db_msg = msg_db.query(Message).filter(
                            Message.id == message_id,
                            Message.room_id == room_id,
                            Message.sender_id == user_id,
                        ).first()
                        if not db_msg:
                            continue
                    finally:
                        msg_db.close()

                await manager.broadcast(room_id, {
                    "type": "file",
                    "id": message_id,
                    "sender_id": user_id,
                    "sender_name": user_name,
                    "file_url": file_url,
                    "filename": filename,
                })

    except WebSocketDisconnect:
        manager.disconnect(room_id, user_id, websocket)
        await manager.broadcast(room_id, {
            "type": "stop_typing",
            "user_id": user_id,
            "user_name": user_name,
        })
        online = manager.get_online_users(room_id)
        await manager.broadcast(room_id, {
            "type": "online_users",
            "users": online,
        })
    except Exception:
        manager.disconnect(room_id, user_id, websocket)
