"""File upload and document access endpoints with authorization and storage fallback logic.

This module validates room membership and write permissions, enforces file extension/size constraints,
stores uploads in Supabase Storage or local disk fallback, creates corresponding document/message records,
lists room documents, and serves or redirects secure document downloads.

All endpoints require a valid JWT. User identity is extracted from the token.
The /documents/{file_id} endpoint additionally accepts ?token= as a query param
so that browser <img>, <audio>, and <video> tags can load media without custom headers."""

import logging
import os
import uuid
import mimetypes
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from storage3.exceptions import StorageApiError

from app.database import get_db
from app.models.room import Room
from app.models.room_member import RoomMember
from app.models.message import Message
from app.models.document import Document
from app.models.user import User
from app import supabase_storage
from app.auth import get_current_user, get_current_user_flexible

router = APIRouter(tags=["files"])
logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
ALLOWED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".txt", ".doc", ".docx", ".csv", ".zip",
    ".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac",
    ".mp4", ".webm", ".mov", ".avi", ".mkv",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def _use_supabase_storage() -> bool:
    """Determines whether uploads/downloads should use configured Supabase Storage."""
    return supabase_storage.storage_configured()


def _approved_room_member(db: Session, room_id: int, user_id: int, need_write: bool = False):
    """Returns an approved membership row, optionally requiring write/admin privileges."""
    q = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == user_id,
        RoomMember.status == "approved",
    )
    if need_write:
        q = q.filter(RoomMember.role.in_(["write", "admin"]))
    return q.first()


@router.post("/rooms/{room_id}/upload")
def upload_file(
    room_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Validates and stores an uploaded file, then creates a file-type chat message record."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if not _approved_room_member(db, room_id, current_user.id, need_write=True):
        raise HTTPException(status_code=403, detail="Not authorized to upload in this room")

    original_name = file.filename or "upload"
    _, ext = os.path.splitext(original_name)
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not allowed")

    contents = file.file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size larger than 10MB. Cannot send.")

    file_id = str(uuid.uuid4())
    stored_suffix = f"{file_id}{ext}"
    content_type, _ = mimetypes.guess_type(original_name)

    storage_bucket = None
    storage_path = None
    storage_public_url = None

    if _use_supabase_storage():
        bucket = supabase_storage.storage_bucket_name()
        storage_path = f"rooms/{room_id}/{stored_suffix}"
        try:
            supabase_storage.upload_bytes(bucket, storage_path, contents, content_type)
        except StorageApiError as e:
            raise HTTPException(status_code=502, detail=f"Storage upload failed: {e}") from e
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Storage upload failed: {e}") from e
        storage_bucket = bucket
        if os.getenv("SUPABASE_STORAGE_PUBLIC_URLS", "").strip().lower() in ("1", "true", "yes"):
            storage_public_url = supabase_storage.public_object_url(bucket, storage_path)
    else:
        if supabase_storage.storage_env_ready():
            logger.warning(
                "Supabase env is set but Storage is not active: %s",
                supabase_storage.why_storage_disabled(),
            )
        else:
            logger.info("Saving upload to local disk (Supabase Storage not configured).")
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(UPLOAD_DIR, stored_suffix)
        with open(file_path, "wb") as f:
            f.write(contents)

    doc = Document(
        file_id=file_id,
        room_id=room_id,
        sender_id=current_user.id,
        original_filename=original_name,
        storage_bucket=storage_bucket,
        storage_path=storage_path,
        storage_public_url=storage_public_url,
    )
    db.add(doc)
    db.flush()

    file_url = f"/documents/{file_id}"
    db_msg = Message(
        room_id=room_id,
        sender_id=current_user.id,
        type="file",
        content=file_url,
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)
    db.refresh(doc)

    # Uploading a file is sending a message — advance the sender's read watermark so
    # their own upload is never counted as unread to them (mirrors the text-message path).
    db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == current_user.id,
    ).update({RoomMember.last_read_message_id: db_msg.id})
    db.commit()

    return {
        "message_id": db_msg.id,
        "file_id": doc.file_id,
        "file_url": file_url,
        "filename": doc.original_filename,
        "storage_bucket": doc.storage_bucket,
        "storage_path": doc.storage_path,
        "storage_public_url": doc.storage_public_url,
        "storage_backend": "supabase" if doc.storage_bucket else "local",
        "created_at": db_msg.created_at.isoformat(),
    }


@router.get("/rooms/{room_id}/documents")
def list_room_documents(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists uploaded documents in a room — caller must be an approved member."""
    if not db.query(Room).filter(Room.id == room_id).first():
        raise HTTPException(status_code=404, detail="Room not found")
    if not _approved_room_member(db, room_id, current_user.id, need_write=False):
        raise HTTPException(status_code=403, detail="Not a member of this room")

    rows = (
        db.query(Document)
        .filter(Document.room_id == room_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return [
        {
            "file_id": d.file_id,
            "original_filename": d.original_filename,
            "sender_id": d.sender_id,
            "open_url": f"/documents/{d.file_id}",
            "storage_bucket": d.storage_bucket,
            "storage_path": d.storage_path,
            "storage_public_url": d.storage_public_url,
            "created_at": d.created_at.isoformat(),
        }
        for d in rows
    ]


@router.get("/documents/{file_id}")
def open_document(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """Opens a document — accepts Authorization: Bearer header OR ?token= query param.

    The ?token= fallback allows browser <img>/<audio>/<video> src attributes to load
    media without custom headers."""
    doc = db.query(Document).filter(Document.file_id == file_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not _approved_room_member(db, doc.room_id, current_user.id, need_write=False):
        raise HTTPException(status_code=403, detail="Not authorized to open this document")

    if doc.storage_bucket and doc.storage_path:
        if not _use_supabase_storage():
            raise HTTPException(
                status_code=503,
                detail="File is in Supabase Storage but credentials are not configured",
            )
        expires = int(os.getenv("SUPABASE_SIGNED_URL_EXPIRES_SECONDS", "3600"))
        try:
            url = supabase_storage.signed_download_url(
                doc.storage_bucket, doc.storage_path, expires
            )
            if not url:
                raise HTTPException(status_code=502, detail="Could not create signed download URL")
            return RedirectResponse(url=url)
        except StorageApiError as e:
            raise HTTPException(status_code=502, detail=f"Could not create download URL: {e}") from e

    _, ext = os.path.splitext(doc.original_filename)
    ext = ext.lower()
    local_name = f"{doc.file_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, local_name)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found on server")
    return FileResponse(
        file_path,
        filename=doc.original_filename,
        media_type=mimetypes.guess_type(doc.original_filename)[0] or "application/octet-stream",
    )


@router.get("/files/{filename}")
def get_file(
    filename: str,
    _: User = Depends(get_current_user),
):
    """Serves legacy locally stored uploads by filename — requires a valid JWT."""
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)
