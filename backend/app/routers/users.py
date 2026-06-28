"""User account endpoints for registration, authentication, and lookup operations.

This module hashes and verifies passwords with bcrypt,
validates uniqueness constraints at signup, authenticates login attempts,
issues JWT tokens on success, and exposes user listing/detail routes
protected by token verification."""

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserSignup, UserLogin, UserUpdate, UserResponse, AuthResponse
from app.auth import create_access_token, get_current_user

router = APIRouter(prefix="/users", tags=["users"])


def _hash_password(password: str) -> str:
    """Generates a bcrypt hash for a plaintext password before persistence."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    """Compares a plaintext password against a stored bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


@router.post("/signup", response_model=AuthResponse, status_code=201)
def signup(req: UserSignup, db: Session = Depends(get_db)):
    """Registers a new user account and returns a JWT alongside the user profile."""
    normalized_email = str(req.email).strip().lower()

    existing = db.query(User).filter(User.email == normalized_email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user = User(
        name=req.name.strip(),
        email=normalized_email,
        password_hash=_hash_password(req.password),
        mobile=req.mobile.strip(),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    token = create_access_token(db_user.id)
    return AuthResponse(token=token, user=UserResponse.model_validate(db_user))


@router.post("/login", response_model=AuthResponse)
def login(req: UserLogin, db: Session = Depends(get_db)):
    """Authenticates a user by email and password and returns a JWT alongside the profile."""
    normalized_email = str(req.email).strip().lower()

    user = db.query(User).filter(User.email == normalized_email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.password_hash:
        raise HTTPException(status_code=401, detail="Account has no password. Please sign up again.")

    if not _verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id)
    return AuthResponse(token=token, user=UserResponse.model_validate(user))


@router.get("/", response_model=list[UserResponse])
def get_users(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Returns all user records — requires a valid JWT."""
    return db.query(User).all()


@router.patch("/me", response_model=UserResponse)
def update_me(
    req: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates the authenticated user's own profile (name and/or mobile).

    Only fields present in the request are touched, so a partial edit never wipes
    the other value. A blank name is rejected; mobile may be cleared to empty.
    """
    if req.name is not None:
        name = req.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be empty")
        current_user.name = name

    if req.mobile is not None:
        current_user.mobile = req.mobile.strip()

    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/by-mobile/{number}", response_model=UserResponse)
def get_user_by_mobile(
    number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resolves a mobile number to a user so the caller can start a direct message.

    Matches the stored (stripped) mobile exactly. Looking up your own number is
    rejected — there is no one to message. Declared before /{user_id} only for
    readability; the two paths differ in segment count and never collide.
    """
    needle = number.strip()
    if not needle:
        raise HTTPException(status_code=400, detail="Mobile number is required")

    user = db.query(User).filter(User.mobile == needle).first()
    if not user:
        raise HTTPException(status_code=404, detail="No user found with that mobile number")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="That is your own number")
    return user


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Returns a single user by ID — requires a valid JWT."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
