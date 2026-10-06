# Share NetGuard with named accounts and HTTPS

The public Compose configuration adds an Authelia password sign-in portal and
a Caddy HTTPS gateway. Only ports 80 and 443 are published. The backend,
dashboard, and authentication service have no host ports; separate internal
networks connect only the services that need to communicate. Local research
use with the original Compose file remains available.

All approved accounts can use the same research workspace. Accounts are created
by the administrator; there is no public registration. The API key continues to
authenticate the dashboard service separately from the user's sign-in session.

## Set up a sharing server

Use a single Docker host with Compose **2.24.4 or later**, Python 3.10 or later,
and a public DNS hostname that you control. Point its A record (and any AAAA
record) to the server. Make TCP ports 80 and 443 reachable for HTTPS certificate
issuance and renewal. Caddy obtains and renews publicly trusted certificates
automatically. Keep its `gateway_data` volume across updates.

From the repository root, install the account-management dependency:

```sh
python -m venv .venv-sharing
# Linux:
.venv-sharing/bin/python -m pip install -r deploy/requirements.txt
# Windows instead:
# .venv-sharing/Scripts/python.exe -m pip install -r deploy/requirements.txt
```

Initialize the private configuration, replacing the example hostname, account,
and email addresses with your own. The command prompts for a password twice;
passwords need 15–128 characters and should be unique passphrases.

```sh
.venv-sharing/bin/python deploy/manage_users.py init \
  --hostname netguard.example.com --acme-email admin@example.com \
  --username alice --email alice@example.com --name "Alice"
```

On Windows, use `.venv-sharing/Scripts/python.exe` and enter the arguments on
one line. Initialization creates `deploy/private/sharing.env`, independent
random session/storage secrets, and `users.json` with an Argon2id password
hash. It refuses to replace existing settings. These files are excluded from
Git and image build contexts. Back up this directory securely, alongside the
`auth_state` volume; the storage encryption key must survive upgrades.

On a Linux host, grant the non-root authentication container's group read
access to its three mounted secret files. Keep `sharing.env` private to the
operator; it contains the service API key.

```sh
sudo chgrp 10001 deploy/private/users.json deploy/private/session.key deploy/private/storage.key
chmod 640 deploy/private/users.json deploy/private/session.key deploy/private/storage.key
```

On Windows, protect `deploy/private` with filesystem permissions restricted to
the operator and Docker. Docker Desktop handles Linux bind-mount permissions.

Start the public configuration using **both** Compose files:

```sh
docker compose --env-file deploy/private/sharing.env \
  -f docker-compose.yaml -f docker-compose.public.yaml \
  up --build -d --wait --wait-timeout 180
```

Open `https://netguard.example.com`. Anonymous users are redirected to the
sign-in form, then returned to the page they requested. HTTP redirects to HTTPS.
The dashboard's **Account & sign out** link opens the account portal in the
same tab; **Logout** revokes the server-side session.

Before sharing the address, check that only gateway ports 80 and 443 appear in
`docker compose ... ps`, that your browser trusts the certificate, and that a
private browser window cannot access dashboard pages, uploads, or downloads
without signing in. The example domain is a placeholder, not a deployed site.

## Manage accounts

These commands prompt for new passwords without exposing them in command-line
arguments:

```sh
.venv-sharing/bin/python deploy/manage_users.py add bobby --email bobby@example.com --name "Bob"
.venv-sharing/bin/python deploy/manage_users.py password alice
.venv-sharing/bin/python deploy/manage_users.py remove bobby
```

After any account change on Linux, reapply the group/read permissions above.
Then **recreate** the authentication container to load the updated file and
revoke existing sessions, including sessions belonging to removed accounts:

```sh
docker compose --env-file deploy/private/sharing.env \
  -f docker-compose.yaml -f docker-compose.public.yaml \
  up -d --no-deps --force-recreate --wait --wait-timeout 90 auth
```

All users must sign in again. A restart alone does not reload an atomically
replaced secret file's bind mount. The helper prevents removal of the last
account. Password resets and changes through the portal are disabled; account
management remains an administrator operation.

## Session and deployment behavior

- Session cookies are Secure, HttpOnly, and SameSite=Lax. Sessions expire after
  one hour or 15 minutes of inactivity; persistent “remember me” is disabled.
- Five failed attempts within two minutes trigger a ten-minute account/IP ban.
  The login portal returns generic credential errors. Authentication failures
  and usernames/IP addresses can appear in private service logs.
- Caddy checks authentication before pages, uploads, media downloads, and
  WebSocket upgrades. It strips client-supplied identity headers, never routes
  the backend API publicly, and fails closed when authentication is unavailable.
- An already upgraded WebSocket is checked again when it reconnects. Connections
  are capped at five minutes, bounding the delay after session revocation or
  expiry. Signing out in the same tab closes that tab's dashboard connection.
- Authelia uses one instance with in-memory sessions and persistent SQLite
  storage. This configuration is for one host, not a replicated deployment.
  Host time synchronization must remain enabled. For MFA or organizational SSO,
  extend the identity configuration with the required notification/provider
  setup before changing the access policy.

The gateway uses [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https)
and the official [Authelia forward-auth integration](https://www.authelia.com/integration/proxies/caddy/).
Their base images are pinned to release digests. All four containers run as UID
10001 with read-only root filesystems and dropped capabilities. Writable
authentication and certificate state use volumes.

## Automated sharing verification

The `Dashboard sign-in and HTTPS` GitHub Actions job starts the actual four
containers. It creates disposable accounts, uses a local test certificate
authority, and validates HTTPS with that CA before testing sign-in, protected
pages/files/WebSockets, predictions, sign-out, cookie replay, failed-login
lockout, header spoofing, private service ports, and authentication outages.
Failures retain browser traces and container logs for seven days.

`docker-compose.sharing-e2e.yaml` and `tests/sharing/tls.caddy` are **test-only**.
They use loopback ports and a local CA; do not include them in a public launch.
Production uses the two files in the setup command and publicly trusted ACME
certificates. No site is published by the tests.
