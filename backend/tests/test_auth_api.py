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
    tampered = client.cookies[COOKIE][:-3] + "abc"
    # Replace the cookie: setting it again could keep the real one next to it.
    client.cookies.clear()
    client.cookies.set(COOKIE, tampered, path="/api")

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


def test_a_copied_token_stops_working_after_logout(client, other_client):
    register(client)
    token = client.cookies.get(COOKIE)
    other_client.cookies.set(COOKIE, token, path="/api")
    assert other_client.get("/api/auth/me").status_code == 200

    client.post("/api/auth/logout")

    assert other_client.get("/api/auth/me").status_code == 401


def test_logging_out_twice_with_the_same_token_is_harmless(client):
    register(client)
    token = client.cookies.get(COOKIE)

    client.post("/api/auth/logout")
    client.cookies.set(COOKIE, token, path="/api")

    assert client.post("/api/auth/logout").status_code == 204


def test_a_new_login_still_works_after_an_earlier_logout(client):
    register(client)
    client.post("/api/auth/logout")

    assert login(client).status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_expired_revocations_are_purged(client):
    from datetime import UTC, datetime, timedelta

    from app.models import RevokedToken
    from app.services import sessions

    with SessionLocal() as db:
        db.add_all(
            [
                RevokedToken(jti="old", expires_at=datetime.now(UTC) - timedelta(minutes=1)),
                RevokedToken(jti="live", expires_at=datetime.now(UTC) + timedelta(days=1)),
            ]
        )
        db.commit()

        assert sessions.purge_expired(db) == 1
        assert sessions.is_revoked(db, "live") and not sessions.is_revoked(db, "old")


# --- rate limiting ---


def test_repeated_wrong_passwords_lock_the_account_for_a_while(client):
    register(client)
    client.post("/api/auth/logout")
    limit = get_settings().login_max_failures_per_email

    for _ in range(limit):
        assert login(client, password="wrong-password").status_code == 401
    blocked = login(client)  # even the right password is refused while locked

    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    assert "Too many failed attempts" in blocked.json()["detail"]


def test_the_email_limit_ignores_case_and_does_not_affect_other_accounts(client, other_client):
    register(client)
    register(other_client, email="grace@example.com")
    limit = get_settings().login_max_failures_per_email

    for _ in range(limit):
        login(client, email="ADA@example.com", password="wrong-password")

    assert login(client).status_code == 429
    assert login(other_client, email="grace@example.com").status_code == 200


def test_a_successful_login_clears_the_failures_for_that_email(client):
    register(client)
    limit = get_settings().login_max_failures_per_email

    for _ in range(limit - 1):
        login(client, password="wrong-password")
    assert login(client).status_code == 200
    for _ in range(limit - 1):
        login(client, password="wrong-password")

    assert login(client).status_code == 200


def test_one_address_guessing_many_emails_is_blocked(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "login_max_failures_per_ip", 3)
    app_limits = client.app.state.login_limits
    app_limits.by_ip.max_failures = 3

    for number in range(3):
        assert (
            login(client, email=f"nobody{number}@example.com", password="x" * 10).status_code == 401
        )

    assert login(client, email="another@example.com", password="x" * 10).status_code == 429


def test_forwarded_address_is_used_only_when_the_proxy_is_trusted(client, monkeypatch):
    client.app.state.login_limits.by_ip.max_failures = 1
    headers = {"X-Forwarded-For": "203.0.113.7"}

    client.post(
        "/api/auth/login", json={"email": "a@example.com", "password": "x" * 10}, headers=headers
    )
    untrusted = client.post(
        "/api/auth/login",
        json={"email": "b@example.com", "password": "x" * 10},
        headers={"X-Forwarded-For": "198.51.100.1"},
    )
    assert untrusted.status_code == 429  # both counted against the socket address

    client.app.state.login_limits.by_ip.reset("testclient")
    monkeypatch.setattr(get_settings(), "trust_proxy_headers", True)
    client.post(
        "/api/auth/login", json={"email": "a@example.com", "password": "x" * 10}, headers=headers
    )
    other = client.post(
        "/api/auth/login",
        json={"email": "b@example.com", "password": "x" * 10},
        headers={"X-Forwarded-For": "198.51.100.1"},
    )
    assert other.status_code == 401  # a different address, so not blocked


def test_every_endpoint_except_the_public_ones_requires_login(client):
    """A new route that forgets its login dependency fails here."""
    import re

    public = {
        ("get", "/api/health"),
        ("post", "/api/auth/register"),
        ("post", "/api/auth/login"),
        ("post", "/api/auth/logout"),
    }
    unprotected = []
    for path, operations in client.app.openapi()["paths"].items():
        url = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)
        for method in operations:
            if (method, path) in public:
                continue
            response = client.request(method.upper(), url, json={})
            if response.status_code != 401:
                unprotected.append((method, path, response.status_code))

    assert unprotected == []
