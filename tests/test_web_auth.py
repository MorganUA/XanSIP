"""Web auth password hashing and account lists."""
from services.web_auth import (
    PRIVILEGED_USERNAMES,
    SUPPORT_USERNAMES,
    hash_password,
    verify_password,
)


def test_hash_and_verify_roundtrip():
    stored = hash_password("secret-pass")
    assert verify_password("secret-pass", stored)
    assert not verify_password("wrong", stored)


def test_privileged_and_support_lists():
    assert len(PRIVILEGED_USERNAMES) == 5
    assert len(SUPPORT_USERNAMES) == 5
    assert PRIVILEGED_USERNAMES[0] == "admin01"
    assert SUPPORT_USERNAMES[-1] == "support05"
