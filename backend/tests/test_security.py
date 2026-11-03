import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher

from app.core.config import get_settings
from app.core.security import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    decode_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)


def _secret() -> str:
    return get_settings().jwt_secret.get_secret_value()


def test_hash_is_argon2_and_salted():
    first = hash_password("correct horse battery")
    second = hash_password("correct horse battery")

    assert first.startswith("$argon2id$")
    assert first != second  # random salt per hash


def test_verify_password():
    stored = hash_password("correct horse battery")

    assert verify_password(stored, "correct horse battery") is True
    assert verify_password(stored, "wrong password") is False


def test_verify_password_rejects_malformed_hash():
    assert verify_password("not-a-hash", "anything") is False


def test_weaker_hash_is_flagged_for_rehash():
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash("pw")

    assert password_needs_rehash(weak) is True
    assert password_needs_rehash(hash_password("pw")) is False


def test_token_round_trip():
    user_id = uuid.uuid4()

    assert decode_access_token(create_access_token(user_id)) == user_id


def test_expired_token_is_rejected():
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        },
        _secret(),
        algorithm=JWT_ALGORITHM,
    )

    assert decode_access_token(token) is None


def test_token_signed_with_another_key_is_rejected():
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(UTC) + timedelta(hours=1)},
        "a-different-secret-that-is-also-long-enough",
        algorithm=JWT_ALGORITHM,
    )

    assert decode_access_token(token) is None


def test_unsigned_token_is_rejected():
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(UTC) + timedelta(hours=1)},
        key=None,
        algorithm="none",
    )

    assert decode_access_token(token) is None


def test_token_without_expiry_is_rejected():
    token = jwt.encode({"sub": str(uuid.uuid4())}, _secret(), algorithm=JWT_ALGORITHM)

    assert decode_access_token(token) is None


def test_token_with_non_uuid_subject_is_rejected():
    token = jwt.encode(
        {"sub": "admin", "exp": datetime.now(UTC) + timedelta(hours=1)},
        _secret(),
        algorithm=JWT_ALGORITHM,
    )

    assert decode_access_token(token) is None


def test_garbage_is_rejected():
    assert decode_access_token("not.a.token") is None
    assert decode_access_token("") is None


def test_tokens_carry_a_unique_id():
    user_id = uuid.uuid4()

    assert (
        decode_token(create_access_token(user_id)).jti
        != decode_token(create_access_token(user_id)).jti
    )


def test_token_without_an_id_is_rejected():
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(UTC) + timedelta(hours=1)},
        _secret(),
        algorithm=JWT_ALGORITHM,
    )

    assert decode_token(token) is None
