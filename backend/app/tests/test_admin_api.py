import pytest
from sqlalchemy import select

from app.models.user import User, UserRole

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
async def test_admin_can_delete_user(client, db_session):
    # 1) Create admin via API, then promote in DB
    admin_email = "admin-del@example.com"
    admin_password = "Password123!"

    r = client.post("/api/auth/register", json={"email": admin_email, "password": admin_password})
    assert r.status_code in (200, 201), r.text

    res = await db_session.execute(select(User).where(User.email == admin_email))
    admin = res.scalar_one()
    admin.role = UserRole.ADMIN
    await db_session.commit()

    admin_token = _login(client, admin_email, admin_password)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2) Create a normal user to delete
    victim_email = "victim@example.com"
    victim_password = "Password123!"

    r = client.post("/api/auth/register", json={"email": victim_email, "password": victim_password})
    assert r.status_code in (200, 201), r.text

    res = await db_session.execute(select(User).where(User.email == victim_email))
    victim = res.scalar_one()
    victim_id = victim.id

    # 3) Delete user via admin endpoint
    resp = client.delete(f"/api/admin/users/{victim_id}", headers=admin_headers)
    assert resp.status_code in (200, 204), resp.text

    # 4) Verify user is gone
    res = await db_session.execute(select(User).where(User.id == victim_id))
    assert res.scalar_one_or_none() is None


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
