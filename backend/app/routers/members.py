"""Room membership workflow endpoints for join and moderation lifecycle.

This module validates room/admin access, creates join requests,
approves or rejects pending members, promotes members to admin, removes or disconnects members,
supports voluntary leave, and returns member/pending lists for moderation UIs.

Acting user identity is always resolved from the JWT — admin_id and self-action user_id
are no longer accepted as client-supplied parameters."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.connection_manager import manager
from app.models.user import User
from app.models.room import Room
from app.models.room_member import RoomMember
from app.schemas.room_member import JoinRequest, ApproveRejectRequest, RoomMemberResponse
from app.auth import get_current_user

router = APIRouter(prefix="/rooms/{room_id}", tags=["members"])


def _get_room_or_404(room_id: int, db: Session) -> Room:
    """Loads a room by ID and raises a not-found error when it does not exist."""
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


def _reject_if_direct(room: Room) -> None:
    """Blocks the join/approve/admin workflow on direct rooms.

    Personal chats have a fixed two-person membership created up front, so joining,
    approving, kicking, promoting, or leaving them is meaningless. Reads (member list)
    stay allowed — the UI needs them to resolve the other participant's name.
    """
    if room.room_type == "direct":
        raise HTTPException(status_code=400, detail="This action is not available for direct messages")


def _get_admin_or_403(room_id: int, admin_id: int, db: Session) -> RoomMember:
    """Validates that the requester is an approved room admin before protected actions."""
    admin = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == admin_id,
        RoomMember.role == "admin",
        RoomMember.status == "approved",
    ).first()
    if not admin:
        raise HTTPException(status_code=403, detail="Only admins can perform this action")
    return admin


@router.post("/join", response_model=RoomMemberResponse, status_code=201)
def join_room(
    room_id: int,
    req: JoinRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates a pending membership request for the authenticated user with a chosen role."""
    _reject_if_direct(_get_room_or_404(room_id, db))

    existing = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already a member or pending request exists")

    if req.role not in ("read", "write"):
        raise HTTPException(status_code=400, detail="Role must be 'read' or 'write'")

    member = RoomMember(
        user_id=current_user.id,
        room_id=room_id,
        role=req.role,
        status="pending",
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.post("/approve", response_model=RoomMemberResponse)
def approve_member(
    room_id: int,
    req: ApproveRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approves a pending room membership request — caller must be an approved admin."""
    _reject_if_direct(_get_room_or_404(room_id, db))
    _get_admin_or_403(room_id, current_user.id, db)

    member = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == req.user_id,
        RoomMember.status == "pending",
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="No pending request found for this user")

    member.status = "approved"
    db.commit()
    db.refresh(member)
    return member


@router.post("/reject", response_model=RoomMemberResponse)
def reject_member(
    room_id: int,
    req: ApproveRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rejects a pending room membership request — caller must be an approved admin."""
    _reject_if_direct(_get_room_or_404(room_id, db))
    _get_admin_or_403(room_id, current_user.id, db)

    member = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == req.user_id,
        RoomMember.status == "pending",
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="No pending request found for this user")

    member.status = "rejected"
    db.commit()
    db.refresh(member)
    return member


@router.delete("/members/{user_id}")
async def remove_member(
    room_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Removes a member from a room — caller must be an approved admin."""
    _reject_if_direct(_get_room_or_404(room_id, db))
    _get_admin_or_403(room_id, current_user.id, db)

    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Admins cannot remove themselves")

    member = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == user_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if member.role == "admin":
        admin_count = db.query(RoomMember).filter(
            RoomMember.room_id == room_id,
            RoomMember.role == "admin",
            RoomMember.status == "approved",
        ).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last admin")

    room = db.query(Room).filter(Room.id == room_id).first()
    room_name = room.name if room else f"room {room_id}"
    admin_name = current_user.name

    db.delete(member)
    db.commit()

    await manager.kick_user(
        room_id,
        user_id,
        reason=f"You were removed from '{room_name}' by {admin_name}",
    )
    await manager.broadcast(room_id, {"type": "member_removed", "user_id": user_id})

    return {"detail": "Member removed"}


@router.get("/members", response_model=list[RoomMemberResponse])
def list_members(
    room_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Lists all membership records for a room — requires a valid JWT."""
    _get_room_or_404(room_id, db)
    return db.query(RoomMember).filter(RoomMember.room_id == room_id).all()


@router.post("/promote")
async def promote_member(
    room_id: int,
    req: ApproveRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Promotes an approved room member to admin — caller must be an approved admin."""
    _reject_if_direct(_get_room_or_404(room_id, db))
    _get_admin_or_403(room_id, current_user.id, db)

    member = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == req.user_id,
        RoomMember.status == "approved",
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if member.role == "admin":
        raise HTTPException(status_code=400, detail="User is already an admin")

    member.role = "admin"
    db.commit()
    db.refresh(member)
    return member


@router.post("/leave")
async def leave_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Removes the authenticated user from a room while protecting against last-admin exit."""
    _reject_if_direct(_get_room_or_404(room_id, db))

    member = db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.user_id == current_user.id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Not a member of this room")

    if member.role == "admin":
        admin_count = db.query(RoomMember).filter(
            RoomMember.room_id == room_id,
            RoomMember.role == "admin",
            RoomMember.status == "approved",
        ).count()
        if admin_count == 1:
            raise HTTPException(status_code=400, detail="Cannot leave: you are the only admin")

    db.delete(member)
    db.commit()

    await manager.kick_user(room_id, current_user.id, reason="You left the room")
    await manager.broadcast(room_id, {
        "type": "system",
        "content": f"User {current_user.id} left the room",
    })

    return {"detail": "Left room successfully"}


@router.get("/pending", response_model=list[RoomMemberResponse])
def list_pending(
    room_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Lists pending join requests for a room — requires a valid JWT."""
    _get_room_or_404(room_id, db)
    return db.query(RoomMember).filter(
        RoomMember.room_id == room_id,
        RoomMember.status == "pending",
    ).all()
