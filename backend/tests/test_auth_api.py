from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import User

COOKIE = get_settings().session_cookie_name

NEW_USER = {"email": "ada@example.com", "display_name": "Ada", "password": "analytical-engine"}


def register(client, **overrides):
    return client.post("/api/auth/register", json={**NEW_USER, **overrides})


def login(client, email=NEW_USER["email"], password=NEW_USER["password"]):
    return client.post("/api/auth/login", json={"email": email, "password": password})


# --- register ---


def test_register_creates_account_and_logs_in(client):
    response = register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert body["display_name"] == "Ada"
    assert "password" not in body and "password_hash" not in body
    assert client.get("/api/auth/me").json()["id"] == body["id"]


def test_register_sets_a_locked_down_cookie(client):
    set_cookie = register(client).headers["set-cookie"].lower()

    assert f"{COOKIE.lower()}=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "path=/api" in set_cookie


def test_register_stores_an_argon2_hash_not_the_password(client):
    register(client)

    with SessionLocal() as db:
        user = db.scalar(select(User))
    assert user.password_hash.startswith("$argon2id$")
    assert NEW_USER["password"] not in user.password_hash


def test_register_normalizes_email_and_rejects_duplicates_ignoring_case(client, other_client):
    register(client, email="Ada@Example.COM")

    with SessionLocal() as db:
        assert db.scalar(select(User)).email == "ada@example.com"

    duplicate = register(other_client, email="ADA@example.com")
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "An account with this email already exists"


def test_register_trims_display_name(client):
    assert register(client, display_name="  Ada  ").json()["display_name"] == "Ada"


def test_register_validates_input(client):
    assert register(client, password="short").status_code == 422
    assert register(client, password="x" * 129).status_code == 422
    assert register(client, email="not-an-email").status_code == 422
    assert register(client, display_name="   ").status_code == 422
    assert client.post("/api/auth/register", json={}).status_code == 422


# --- login ---


def test_login_with_correct_credentials(client, other_client):
    register(client)

    response = login(other_client, email="ADA@example.com")

    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"
    assert other_client.get("/api/auth/me").status_code == 200


def test_login_failures_look_identical_for_wrong_password_and_unknown_email(client, other_client):
    register(client)

    wrong_password = login(other_client, password="wrong-password")
    unknown_email = login(other_client, email="nobody@example.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert COOKIE not in other_client.cookies


# --- current user ---


def test_me_requires_login(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_me_rejects_a_tampered_cookie(client):
    register(client)
    client.cookies.set(COOKIE, client.cookies[COOKIE][:-3] + "abc", path="/api")

    assert client.get("/api/auth/me").status_code == 401


def test_token_for_a_deleted_user_is_rejected(client):
    register(client)
    with SessionLocal() as db:
        db.delete(db.scalar(select(User)))
        db.commit()

    assert client.get("/api/auth/me").status_code == 401


def test_each_session_only_sees_its_own_user(client, other_client):
    register(client, email="ada@example.com", display_name="Ada")
    register(other_client, email="grace@example.com", display_name="Grace")

    assert client.get("/api/auth/me").json()["display_name"] == "Ada"
    assert other_client.get("/api/auth/me").json()["display_name"] == "Grace"


# --- logout ---


def test_logout_clears_the_session(client):
    register(client)

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_logout_without_a_session_is_harmless(client):
    assert client.post("/api/auth/logout").status_code == 204
