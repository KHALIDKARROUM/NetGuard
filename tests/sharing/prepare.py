"""Generate masked, ephemeral accounts for an isolated HTTPS container test."""
import importlib.util
import json
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("manage_users", ROOT / "deploy/manage_users.py")
users = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(users)
password = secrets.token_urlsafe(32)
print("::add-mask::" + password)
private = ROOT / "deploy/private"
users.initialize(private, "netguard.example.test", "ci@example.test", "alice", password, "alice@example.test", "Test account")
users.update_user(private, "add", "locked", password, "locked@example.test", "Lockout test account")
users.update_user(private, "add", "denied", password, "denied@example.test", "Unapproved test account")
database = json.loads((private / "users.json").read_text())
database["users"]["denied"]["groups"] = []
users.write_private(private / "users.json", json.dumps(database))
values = {}
for line in (private / "sharing.env").read_text().splitlines():
    key, value = line.split("=", 1)
    values[key] = json.loads(value)
print("::add-mask::" + values["NETGUARD_API_KEY"])
values["NETGUARD_TEST_PASSWORD"] = password
with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as output:
    for key, value in values.items():
        output.write(key + "=" + value + "\n")
