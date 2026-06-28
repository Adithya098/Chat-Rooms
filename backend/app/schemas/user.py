"""Pydantic schemas for user auth and profile API payloads.

This module defines signup/login request models, a backward-compatible creation schema used internally, 
and the standardized user response model returned by user-facing endpoints."""

from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


class UserSignup(BaseModel):
    """Request payload for creating a user account with password and contact data."""
    name: str
    email: EmailStr
    password: str
    mobile: str


class UserLogin(BaseModel):
    """Request payload for authenticating an existing user with credentials."""
    email: EmailStr
    password: str


# Keep old schema for backward compat (used internally)
class UserCreate(BaseModel):
    """Backward-compatible schema for internal user creation flows without password."""
    name: str
    email: EmailStr


class UserUpdate(BaseModel):
    """Request payload for editing your own profile — fields omitted are left unchanged."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    mobile: Optional[str] = None


class UserResponse(BaseModel):
    """Response model that exposes persisted user fields returned by API endpoints."""
    id: int
    name: str
    email: str
    mobile: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """Response returned by login and signup — includes the JWT and user profile."""
    token: str
    user: UserResponse
