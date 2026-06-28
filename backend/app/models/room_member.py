"""SQLAlchemy model definition for room memberships and access control state.

This file models the relationship between users and rooms, stores role and approval status, 
tracks join time, and enforces uniqueness so each user has at most one membership record per room."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class RoomMember(Base):
    """Represents one user-to-room membership entry including role and approval status."""
    __tablename__ = "room_members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    role = Column(String(20), nullable=False, default="write")  # admin | write | read
    status = Column(String(20), nullable=False, default="pending")  # pending | approved | rejected
    # Read watermark: id of the newest message this member has seen in the room.
    # Unread count is derived as COUNT(messages.id > last_read_message_id), so this
    # single value can never drift the way a stored counter would. NULL = nothing read yet.
    last_read_message_id = Column(Integer, nullable=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "room_id", name="uq_user_room"),
    )
