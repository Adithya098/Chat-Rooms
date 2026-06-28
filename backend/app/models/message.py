"""SQLAlchemy model definition for persisted chat messages.

This file represents room messages sent by users, supports text/file message types, 
stores payload content, supports optional reply threading via self-reference, 
and records creation timestamps for chronological retrieval."""

from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class Message(Base):
    """Represents a message sent in a room by a user at a specific timestamp."""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String(20), nullable=False, default="text")  # text | file
    content = Column(Text, nullable=False)  # text content or file URL
    reply_to = Column(Integer, ForeignKey("messages.id"), nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False, server_default="false")
    # Set when the sender edits the message; NULL means never edited (drives the "(edited)" label).
    edited_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
