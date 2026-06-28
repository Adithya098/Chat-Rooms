"""Pydantic schemas for chat message response shaping.

This module defines the message response contract returned by history APIs 
and the compact reply snippet model used to embed minimal context for replied-to messages."""

from pydantic import BaseModel
from datetime import datetime


class ReplySnippet(BaseModel):
    """Compact representation of a replied-to message used in message lists."""
    id: int
    sender_name: str
    content: str
    type: str = "text"
    filename: str | None = None
    file_url: str | None = None
    is_image: bool = False


class MessageResponse(BaseModel):
    """Serialized chat message payload including sender, file, and reply metadata."""
    id: int
    room_id: int
    sender_id: int
    sender_name: str
    type: str
    content: str
    created_at: datetime
    edited_at: datetime | None = None
    filename: str | None = None
    reply_to: int | None = None
    reply_snippet: ReplySnippet | None = None


class MessageEdit(BaseModel):
    """Request payload for editing a text message's content."""
    content: str
