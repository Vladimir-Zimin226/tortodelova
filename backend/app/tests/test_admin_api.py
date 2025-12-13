import pytest

def _login(client, email: str, password: str) -> str:
    r = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]

def test_admin_requires_admin_role(client, auth_headers):
    r = client.get("/api/admin/users", headers=auth_headers)
    assert r.status_code == 403

@pytest.mark.asyncio
async def test_admin_list_users_as_admin(client, db_session):
    # register normal user
    client.post("/api/auth/register", json={"email": "admin2@example.com", "password": "Password123!"})

    # promote to admin in DB
    from sqlalchemy import select
    from app.models.user import User, UserRole

    res = await db_session.execute(select(User).where(User.email == "admin2@example.com"))
    u = res.scalar_one()
    u.role = UserRole.ADMIN
    await db_session.commit()

    token = _login(client, "admin2@example.com", "Password123!")
    r = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)
