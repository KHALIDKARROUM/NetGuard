"""Create private sharing settings and manage named Authelia accounts."""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import secrets

from argon2 import PasswordHasher
from argon2.low_level import Type

DEFAULT_DIRECTORY = Path(__file__).resolve().parent / "private"
HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16, type=Type.ID)


def validate_username(username: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_.-]{2,63}", username):
        raise ValueError("Use a 3–64 character username starting with a lowercase letter.")
    return username


def validate_hostname(hostname: str) -> str:
    labels = hostname.split(".")
    if len(labels) < 2 or len(hostname) > 253 or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in labels
    ) or labels[-1].isdigit():
        raise ValueError("Use a lowercase DNS hostname without a scheme, port, path, or wildcard.")
    return hostname


def validate_email(email: str) -> str:
    if not re.fullmatch(r"[^\s@\"\\]+@[^\s@\"\\]+\.[^\s@\"\\]+", email) or len(email) > 254:
        raise ValueError("Enter a valid email address without whitespace.")
    return email


def user_record(password: str, email: str, display_name: str) -> dict:
    validate_email(email)
    if not 1 <= len(display_name) <= 100 or any(ord(c) < 32 for c in display_name):
        raise ValueError("Enter a display name between 1 and 100 characters.")
    if not 15 <= len(password) <= 128:
        raise ValueError("Use a unique password or passphrase between 15 and 128 characters.")
    return {"displayname": display_name, "password": HASHER.hash(password), "email": email, "groups": ["netguard-users"]}


def write_private(path: Path, content: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    # No password or private configuration is printed or placed in shell arguments.
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def initialize(directory: Path, hostname: str, acme_email: str, username: str, password: str, email: str, display_name: str) -> None:
    validate_hostname(hostname)
    validate_email(acme_email)
    validate_username(username)
    account = user_record(password, email, display_name)
    directory = directory.resolve()
    files = [directory / name for name in ("sharing.env", "users.json", "session.key", "storage.key")]
    if any(path.exists() for path in files):
        raise ValueError("Sharing settings already exist. Use the account commands; initialization never rotates existing secrets.")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_private(directory / "users.json", json.dumps({"users": {username: account}}, indent=2) + "\n")
    write_private(directory / "session.key", secrets.token_urlsafe(48))
    write_private(directory / "storage.key", secrets.token_urlsafe(48))
    values = {
        "NETGUARD_PUBLIC_HOST": hostname,
        "NETGUARD_ACME_EMAIL": acme_email,
        "NETGUARD_API_KEY": secrets.token_urlsafe(48),
        "NETGUARD_PRIVATE_DIR": directory.as_posix(),
    }
    write_private(directory / "sharing.env", "".join(key + "=" + json.dumps(value) + "\n" for key, value in values.items()))


def update_user(directory: Path, operation: str, username: str, password: str | None = None, email: str | None = None, display_name: str | None = None) -> None:
    validate_username(username)
    path = directory / "users.json"
    database = json.loads(path.read_text(encoding="utf-8"))
    users = database["users"]
    if operation == "add":
        if username in users:
            raise ValueError("That account already exists.")
        users[username] = user_record(password or "", email or "", display_name or username)
    else:
        if username not in users:
            raise ValueError("That account does not exist.")
        if operation == "remove":
            if len(users) == 1:
                raise ValueError("Add another account before removing the last account.")
            del users[username]
        elif operation == "password":
            old = users[username]
            users[username] = user_record(password or "", old["email"], old["displayname"])
        else:
            raise ValueError("Unknown account operation.")
    write_private(path, json.dumps(database, indent=2) + "\n")


def read_password() -> str:
    password = getpass.getpass("New password (15–128 characters): ")
    if password != getpass.getpass("Confirm password: "):
        raise ValueError("The passwords do not match.")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, default=DEFAULT_DIRECTORY)
    commands = parser.add_subparsers(dest="command", required=True)
    initialize_parser = commands.add_parser("init")
    initialize_parser.add_argument("--hostname", required=True)
    initialize_parser.add_argument("--acme-email", required=True)
    initialize_parser.add_argument("--username", required=True)
    initialize_parser.add_argument("--email", required=True)
    initialize_parser.add_argument("--name", required=True)
    for command in ("add", "password", "remove"):
        subparser = commands.add_parser(command)
        subparser.add_argument("username")
        if command == "add":
            subparser.add_argument("--email", required=True)
            subparser.add_argument("--name", required=True)
    args = parser.parse_args()
    try:
        if args.command == "init":
            initialize(args.private_dir, args.hostname, args.acme_email, args.username, read_password(), args.email, args.name)
            print("Created private sharing settings in " + str(args.private_dir))
        else:
            update_user(args.private_dir, args.command, args.username,
                        read_password() if args.command != "remove" else None,
                        getattr(args, "email", None), getattr(args, "name", None))
            print("Account updated. Recreate the auth container to reload accounts and revoke existing sessions.")
    except (ValueError, FileNotFoundError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
