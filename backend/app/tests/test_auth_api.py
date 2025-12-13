import pytest

def test_register_then_login(client):
    reg = client.post("/api/auth/register", json={"email": "t1@example.com", "password": "Password123!"})
    assert reg.status_code == 201, reg.text
    assert reg.json()["email"] == "t1@example.com"

    login = client.post(
        "/api/auth/login",
        data={"username": "t1@example.com", "password": "Password123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200, login.text
    data = login.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "Password123!"}
    r1 = client.post("/api/auth/register", json=payload)
    assert r1.status_code == 201, r1.text

    r2 = client.post("/api/auth/register", json=payload)
    assert r2.status_code == 400

def test_me_profile_works_with_cookie_after_login(client, register_user):
    # register + login; login response should set HttpOnly cookie access_token
    email = "cookieuser@example.com"
    password = "Password123!"
    reg = register_user(email=email, password=password)
    assert reg.status_code in (200, 201), reg.text

    login = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200, login.text

    # Important: no Authorization header here — must work via cookie
    prof = client.get("/api/me/profile")
    assert prof.status_code == 200, prof.text
    assert prof.json()["email"] == email


def test_me_profile_rejects_invalid_bearer_token(client):
    prof = client.get("/api/me/profile", headers={"Authorization": "Bearer not-a-real-token"})
    assert prof.status_code == 401
    assert "validate" in prof.text.lower() or "authenticated" in prof.text.lower()
