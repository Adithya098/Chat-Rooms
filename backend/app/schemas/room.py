"""Pydantic schemas for room creation inputs and room response outputs.

This module defines the data contract for creating rooms and serializing persisted room entities returned by room APIs."""

from pydantic import BaseModel
from datetime import datetime


class RoomCreate(BaseModel):
    """Request payload for creating a room — creator is resolved from the JWT."""
    name: str


class DirectRoomCreate(BaseModel):
    """Request payload for opening a 1:1 direct room with another user."""
    user_id: int


class RoomResponse(BaseModel):
    """Serialized room data returned by room API endpoints."""
    id: int
    name: str | None  # NULL for direct rooms — title derived from the other participant.
    room_type: str    # "group" | "direct"
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}
