# NetGuard security and deployment

NetGuard defaults to a local research workspace. The backend and Streamlit
dashboard bind to `127.0.0.1`; Docker Compose publishes both ports on the host's
loopback interface. Local use does not require a key.

## Application safeguards

- Exact backend host and browser-origin allowlists reject unexpected hosts and
  origins. CORS permits GET/POST with Content-Type and X-API-Key headers.
- When configured, an API key is required for every backend route except
  `/health`. Comparison uses `secrets.compare_digest`. Authentication occurs
  before body parsing and prediction. Authenticated health responses omit model
  identity and artifact hashes. Shared mode disables Swagger, ReDoc and OpenAPI.
- Bodies are limited to 1 MiB, including streams with missing or misleading
  Content-Length headers. Reading a body times out after 10 seconds. Prediction
  POSTs require JSON, and compressed bodies are rejected.
- Each API worker permits 120 non-health requests per client IP per 60-second
  window and two concurrent `/api/` requests. Rejections use HTTP 429 and
  Retry-After. The client table is bounded to 4,096 active windows. Forwarded IP
  headers are ignored by the documented server commands.
- API responses disable caching and include content-sniffing, framing and
  referrer restrictions. Server failures return generic messages; diagnostic
  details stay in server logs. The application error logger omits query strings.
- Streamlit keeps its CORS and XSRF protections enabled. CSV uploads are limited
  to 2 MiB, UTF-8 text, unique short headers and consistent field counts. At most
  1,001 records are parsed so the 1,000-connection limit can be enforced before
  submission. Measurements must satisfy the existing numerical input contract.
- CSV downloads quote fields and prefix formula-like text with an apostrophe,
  including headers. Numeric measurements retain their values. Spreadsheet
  software can change escaping when a file is edited and saved again; keep the
  original export when exchanging untrusted text.
- Docker services run as non-root users with read-only filesystems, dropped
  capabilities, process limits and no privilege escalation. Data and model
  mounts remain read-only. Temporary files have a bounded `/tmp` mount.
- Local `.env` files and Streamlit secrets are excluded from Git and Docker
  build contexts. `backend/.env.example` contains configuration examples only.

## Configure protected API access

Generate a random key and set it in the backend and frontend **server processes**.
The frontend reads the key from its environment and sends it directly to the
API; it is never a dashboard input or a browser URL parameter.

For Docker Compose, from a PowerShell terminal at the repository root:

```powershell
$env:NETGUARD_API_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:NETGUARD_DEPLOYMENT_MODE = "shared"
docker compose up --build
```

This still publishes only local ports. The generated key remains in that
terminal's environment; store a persistent key in your deployment's secret
manager if needed. Recreating these services with a different key requires both
services to receive the new value. Never commit an actual key.

For native processes, the backend also reads `backend/.env`. Set the same
`NETGUARD_API_KEY` in the terminal that starts Streamlit; the frontend does not
read the backend's `.env`. Keys need at least 32 ASCII characters without
whitespace. Restart both processes when rotating a key or changing allowlists.

```powershell
# Backend, from the repository root with the key already set:
$env:NETGUARD_DEPLOYMENT_MODE = "shared"
.venv-api/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 5000 --no-proxy-headers

# Frontend, in a separate terminal with the same key already set:
cd frontend
$env:BACKEND_URL = "http://localhost:5000"
streamlit run app.py
```

Authenticated remote backend URLs must use HTTPS. HTTP is permitted for
loopback names and the internal Compose service name `backend`. The API client
rejects redirects so the custom authentication header cannot be forwarded to a
different service.

## Share the dashboard

The API key authenticates the **Streamlit service**, not individual dashboard
users. Anyone who can open the dashboard can use its API access. Before allowing
remote access, put the dashboard behind an HTTPS reverse proxy with user
authentication, such as your organization's SSO, and keep the API reachable only
from the frontend/proxy. Enable `NETGUARD_DEPLOYMENT_MODE=shared` and set the key.

Configure exact public backend hostnames with `ALLOWED_HOSTS` and exact browser
origins with `CORS_ORIGINS`, using JSON arrays. Wildcards are rejected. Adjust
Streamlit's public browser address for your reverse proxy and retain its
CORS/XSRF protections. Configure TLS, authentication and rate limits at the
proxy as well. Restrict trusted forwarding to your actual proxy if you choose
to enable proxy-header handling in the server.

The built-in limits apply independently to each worker. The default Docker
backend has two workers; a reverse proxy sees one combined service and should
enforce the desired total limit. Connection-level denial-of-service protection,
account permissions, access auditing and distributed rate limits belong at the
deployment boundary.

## Data, models and logs

Uploaded files are processed in memory for the Streamlit session. NetGuard does
not write uploaded CSVs to disk or log their measurements. Uploaded data and
analysis results can remain in session memory; this is not a retention or secure
deletion guarantee. Apply your organization's data handling rules when hosting
the app.

Model files use Python joblib/pickle serialization and must come from a trusted
source. The existing artifact hash, manifest consistency and numerical-runtime
checks detect mismatches before loading. They are not a signature or a sandbox:
an attacker able to replace both model and manifest can supply executable model
content. Restrict filesystem access and mount model artifacts read-only.

Backend logs can contain server paths and exception diagnostics. Limit access
to logs and do not log API keys at your reverse proxy. Docker now stores logs in
the `netguard_logs` named volume rather than the local `backend/logs` directory,
so the non-root backend can write while its root filesystem stays read-only.
Existing local logs remain where they were.

## Verification

```powershell
.venv-api/Scripts/python.exe -m unittest discover -s tests -p test_security.py -v
.venv-api/Scripts/python.exe -m unittest discover -s tests -p test_shared_prediction_api.py -v
python -m pytest frontend/tests -q
docker compose config --quiet
```

The checks cover missing/wrong/duplicate API keys, shared-mode startup, origin
and host rejection, request and streaming limits, slow bodies, concurrency,
rate limits, error redaction, CSV boundaries and exports, redirect handling,
and prediction parity with the fitted notebook pipeline.
