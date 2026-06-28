"""SQLAlchemy model definition for chat rooms.

This file declares the rooms table structure, including room identity, human-readable name,
room type (group channel vs 1:1 direct message), creator linkage to a user record,
and room creation timestamp."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Room(Base):
    """Represents a chat room created by a user and identified by name or type."""
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    # NULL for direct rooms — their title is derived from the other participant, not stored.
    name = Column(String(200), nullable=True)
    # group  = multi-user channel with the join/approve/admin workflow.
    # direct = 1:1 personal chat; both members auto-approved, no join/access flow.
    room_type = Column(String(20), nullable=False, default="group", server_default="group")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
