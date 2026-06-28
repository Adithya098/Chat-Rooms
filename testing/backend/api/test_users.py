def test_signup_success(client):
    payload = {
        "name": "New User",
        "email": "new.user@example.com",
        "password": "Passw0rd!",
        "mobile": "9999999999",
    }
    res = client.post("/users/signup", json=payload)
    assert res.status_code == 201
    body = res.json()
    # Signup returns an AuthResponse: a JWT plus the nested user profile.
    assert body["token"]
    assert body["user"]["email"] == "new.user@example.com"
    assert body["user"]["name"] == "New User"


def test_signup_duplicate_email_fails(client, seed_users):
    payload = {
        "name": "Duplicate",
        "email": seed_users["alice"].email,
        "password": "Passw0rd!",
        "mobile": "8888888888",
    }
    res = client.post("/users/signup", json=payload)
    assert res.status_code == 400
    assert "already registered" in res.json()["detail"]


def test_login_invalid_password_fails(client, seed_users):
    # create a user through signup so password hash is valid bcrypt
    client.post(
        "/users/signup",
        json={
            "name": "Auth User",
            "email": "auth.user@example.com",
            "password": "correct-password",
            "mobile": "7777777777",
        },
    )
    res = client.post(
        "/users/login",
        json={"email": "auth.user@example.com", "password": "wrong-password"},
    )
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]


def test_login_success(client):
    client.post(
        "/users/signup",
        json={
            "name": "Login User",
            "email": "login.user@example.com",
            "password": "correct-password",
            "mobile": "6666666666",
        },
    )
    res = client.post(
        "/users/login",
        json={"email": "login.user@example.com", "password": "correct-password"},
    )
    assert res.status_code == 200
    body = res.json()
    # Login returns an AuthResponse: a JWT plus the nested user profile.
    assert body["token"]
    assert body["user"]["email"] == "login.user@example.com"
