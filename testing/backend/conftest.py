import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import app.models  # noqa: F401
from app.database import Base, get_db
from app.auth import get_current_user
from app.main import app
import app.main as main_module
from app.models.message import Message
from app.models.room import Room
from app.models.room_member import RoomMember
from app.models.user import User


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def auth_user(seed_users):
    """Mutable holder for the identity the test client authenticates as.

    The endpoints derive the caller from the JWT (get_current_user); in tests we
    override that dependency to return this user. Defaults to Alice (room admin);
    a test can act as someone else via `auth_user["current"] = seed_users["bob"]`.
    """
    return {"current": seed_users["alice"]}


@pytest.fixture()
def client(db_session, auth_user):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_current_user():
        return auth_user["current"]

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    main_module._db_healthy = True
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seed_users(db_session):
    alice = User(
        name="Alice",
        email="alice@example.com",
        password_hash="hash",
        mobile="1111111111",
    )
    bob = User(
        name="Bob",
        email="bob@example.com",
        password_hash="hash",
        mobile="2222222222",
    )
    carol = User(
        name="Carol",
        email="carol@example.com",
        password_hash="hash",
        mobile="3333333333",
    )
    db_session.add_all([alice, bob, carol])
    db_session.commit()
    for user in (alice, bob, carol):
        db_session.refresh(user)
    return {"alice": alice, "bob": bob, "carol": carol}


@pytest.fixture()
def seed_room(db_session, seed_users):
    room = Room(name="General", created_by=seed_users["alice"].id)
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)

    admin = RoomMember(
        room_id=room.id,
        user_id=seed_users["alice"].id,
        role="admin",
        status="approved",
    )
    writer = RoomMember(
        room_id=room.id,
        user_id=seed_users["bob"].id,
        role="write",
        status="approved",
    )
    reader = RoomMember(
        room_id=room.id,
        user_id=seed_users["carol"].id,
        role="read",
        status="approved",
    )
    db_session.add_all([admin, writer, reader])
    db_session.commit()
    return room


@pytest.fixture()
def seed_message(db_session, seed_room, seed_users):
    message = Message(
        room_id=seed_room.id,
        sender_id=seed_users["bob"].id,
        type="text",
        content="hello world",
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)
    return message
