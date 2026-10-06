import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("manage_users", Path(__file__).resolve().parents[1] / "manage_users.py")
users = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(users)
PASSWORD = "synthetic test passphrase 123"


def initialize(tmp_path):
    users.initialize(tmp_path, "netguard.example.com", "admin@example.com", "alice", PASSWORD, "alice@example.com", "Alice")


def test_initialization_hashes_password_and_creates_independent_secrets(tmp_path):
    initialize(tmp_path)
    database = json.loads((tmp_path / "users.json").read_text())
    record = database["users"]["alice"]
    assert record["password"].startswith("$argon2id$")
    assert users.HASHER.verify(record["password"], PASSWORD)
    assert record["groups"] == ["netguard-users"]
    secrets = [(tmp_path / name).read_text() for name in ("session.key", "storage.key")]
    assert len(set(secrets)) == 2
    assert all(len(secret) >= 64 for secret in secrets)
    assert not any(PASSWORD in file.read_text() for file in tmp_path.iterdir())
    env = (tmp_path / "sharing.env").read_text()
    assert 'NETGUARD_PUBLIC_HOST="netguard.example.com"' in env
    assert not any(secret in env for secret in secrets)
    with pytest.raises(ValueError, match="already exist"):
        initialize(tmp_path)
    assert secrets == [(tmp_path / name).read_text() for name in ("session.key", "storage.key")]


def test_account_lifecycle_keeps_service_secrets(tmp_path):
    initialize(tmp_path)
    original = (tmp_path / "sharing.env").read_bytes()
    users.update_user(tmp_path, "add", "bobby", PASSWORD, "bobby@example.com", "Bob")
    with pytest.raises(ValueError, match="already exists"):
        users.update_user(tmp_path, "add", "bobby", PASSWORD, "bobby@example.com", "Bob")
    users.update_user(tmp_path, "password", "alice", "replacement test passphrase")
    database = json.loads((tmp_path / "users.json").read_text())
    assert users.HASHER.verify(database["users"]["alice"]["password"], "replacement test passphrase")
    users.update_user(tmp_path, "remove", "bobby")
    with pytest.raises(ValueError, match="last account"):
        users.update_user(tmp_path, "remove", "alice")
    with pytest.raises(ValueError, match="does not exist"):
        users.update_user(tmp_path, "remove", "nobody")
    assert original == (tmp_path / "sharing.env").read_bytes()


@pytest.mark.parametrize("hostname", ["localhost", "http://example.com", "example.com:443", "*.example.com", "example.com/path", "evil.com\nINJECT=1", "127.0.0.1", "-a.example.com"])
def test_rejects_invalid_public_hosts(hostname):
    with pytest.raises(ValueError):
        users.validate_hostname(hostname)


@pytest.mark.parametrize("username", ["a", "Alice", "../alice", "a b", "a\nb", "a" * 65])
def test_rejects_invalid_account_names(username):
    with pytest.raises(ValueError):
        users.validate_username(username)


def test_invalid_input_does_not_create_private_files(tmp_path):
    with pytest.raises(ValueError, match="password"):
        users.initialize(tmp_path, "netguard.example.com", "admin@example.com", "alice", "short", "alice@example.com", "Alice")
    assert not list(tmp_path.iterdir())
