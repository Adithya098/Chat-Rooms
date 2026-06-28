"""Room API tests.

Identity comes from the JWT (get_current_user), which the test client overrides
to act as Alice by default — so room creation no longer takes a creator id in the
body; the caller is the creator.
"""
from app.models.room_member import RoomMember


def test_create_room_success(client, seed_users):
    res = client.post("/rooms/", json={"name": "Project Room"})
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Project Room"
    # Creator is the authenticated caller (Alice), not a client-supplied id.
    assert body["created_by"] == seed_users["alice"].id


def test_create_room_enrolls_creator_as_admin(client, seed_users, db_session):
    res = client.post("/rooms/", json={"name": "Auto Admin Room"})
    assert res.status_code == 201
    room_id = res.json()["id"]

    member = (
        db_session.query(RoomMember)
        .filter(
            RoomMember.room_id == room_id,
            RoomMember.user_id == seed_users["alice"].id,
        )
        .first()
    )
    assert member is not None
    assert member.role == "admin"
    assert member.status == "approved"


def test_list_rooms_returns_created_room(client):
    create = client.post("/rooms/", json={"name": "Listable Room"})
    assert create.status_code == 201
    res = client.get("/rooms/")
    assert res.status_code == 200
    names = [room["name"] for room in res.json()]
    assert "Listable Room" in names


def test_get_room_not_found(client):
    res = client.get("/rooms/404404")
    assert res.status_code == 404
    assert "Room not found" in res.json()["detail"]
