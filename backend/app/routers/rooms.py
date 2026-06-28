"""Room management endpoints for creating and reading chat rooms.

This module validates room creators, persists new room records,
auto-enrolls creators as approved admins, and provides list/detail APIs
for room discovery. All endpoints require a valid JWT — the creator
identity is extracted from the token, not the request body."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.message import Message
from app.models.room import Room
from app.models.room_member import RoomMember
from app.models.user import User
from app.schemas.room import RoomCreate, RoomResponse
from app.auth import get_current_user

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.post("/", response_model=RoomResponse, status_code=201)
def create_room(
    room: RoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates a room and automatically adds the token-authenticated caller as approved admin."""
    db_room = Room(name=room.name, created_by=current_user.id)
    db.add(db_room)
    db.commit()
    db.refresh(db_room)

    member = RoomMember(
        user_id=current_user.id,
        room_id=db_room.id,
        role="admin",
        status="approved",
    )
    db.add(member)
    db.commit()

    return db_room


@router.get("/", response_model=list[RoomResponse])
def get_rooms(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Returns all chat rooms — requires a valid JWT."""
    return db.query(Room).all()


@router.get("/unread/counts")
def get_unread_counts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns {room_id: unread_count} for the caller's approved rooms.

    A single aggregate query: for each room the user belongs to, count messages
    newer than their read watermark. Rooms that are fully read (or have no
    messages) simply don't appear in the map — the client treats them as 0.
    """
    rows = (
        db.query(Message.room_id, func.count(Message.id))
        .join(
            RoomMember,
            RoomMember.room_id == Message.room_id,
        )
        .filter(RoomMember.user_id == current_user.id)
        .filter(RoomMember.status == "approved")
        .filter(Message.is_deleted.is_(False))
        .filter(Message.id > func.coalesce(RoomMember.last_read_message_id, 0))
        .group_by(Message.room_id)
        .all()
    )
    return {room_id: count for room_id, count in rows}


@router.post("/{room_id}/read")
def mark_room_read(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Advances the caller's read watermark to the room's newest message.

    Called when a member opens a room (or receives a message while viewing it),
    which clears that room's unread badge for them.
    """
    member = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == current_user.id,
        RoomMember.status == "approved",
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not an approved member of this room")

    latest_id = db.query(func.max(Message.id)).filter(
        Message.room_id == room_id,
    ).scalar()

    if latest_id is not None and (member.last_read_message_id or 0) < latest_id:
        member.last_read_message_id = latest_id
        db.commit()

    return {"room_id": room_id, "last_read_message_id": member.last_read_message_id}


@router.get("/{room_id}", response_model=RoomResponse)
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Returns room details for a specific room ID — requires a valid JWT."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room
