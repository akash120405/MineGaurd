# Deployment and operational boundaries

## Local deployment

`python run.py` binds only to `127.0.0.1:8000`. Keep a single application process (`--workers 1`). The embedded durable worker recovers jobs marked processing on startup; it is not a multi-instance lease system.

The supplied Windows launcher uses an existing `.venv` when available. This workspace also has a tested fallback Python runtime and installed dependencies. That fallback path is specific to this computer; use the standard installation instructions elsewhere.

## Container deployment

Docker was not available on the build machine, so the container recipe is supplied but has not been built here.

Initialize accounts inside the running service so the generated credential file remains available:

```text
docker compose up -d --build
docker compose exec mineguard python setup_local.py
docker compose exec mineguard cat .local-access.txt
```

Store the resulting credentials in your password manager. Do not run setup in a disposable container first. The database is stored in the named volume. The container runs as a nonroot user with dropped Linux capabilities. Docker Compose maps the service to loopback only.

For remote access, place the service behind a managed HTTPS reverse proxy, set `COOKIE_SECURE=true`, restrict ingress, and use your organization's secret manager for the API keys. Do not expose the development HTTP server directly to the internet. The provided artifact is production-oriented coursework, not a certified or independently security-audited mining system.

## State and backup

- Back up SQLite using its backup API or stop the server before copying the database. Copying a live `.db` without its WAL may lose recent transactions.
- Keep backups encrypted and access-controlled; inspection evidence and conversations may contain confidential information.
- Restore into the same single-worker application version and verify the audit chain after recovery.
- Existing policy IDs cannot be overwritten through the API. Use a new version ID and retain provenance in the policy text.
- Existing decisions cannot be silently reversed through the UI. Submit corrected evidence as a new inspection and reference the earlier record in notes.

## Security controls and limits

Implemented: scrypt password hashes with independent salts; eight-hour sessions; hashed session tokens in the database; HttpOnly/SameSite cookies; CSRF headers; server-enforced roles; no self-approval; bounded request fields; rate-limited sign-in; source-only script CSP; escaped rendered text; fixed provider URLs; TLS verification; prompt-injection screening; no model credentials in prompts; no executable model tools; append-only application audit operations.

Remaining production work: organization SSO/MFA, account recovery and revocation UI, tenant separation, external tamper-resistant audit retention, managed encryption/backups, stricter request/rate limits at the ingress, provider egress policies, dependency scanning, signed release artifacts, deployment monitoring and load testing. All roles belong to one mine workspace and can read its evidence. The app is not a multi-tenant SaaS product.

Prompt-injection regex screening is intentionally only one layer and cannot recognize every attack. The stronger boundary is capability restriction: model output cannot mutate state or run operations. Citation matching validates provenance, not semantics. A determined database administrator could rewrite the hash chain; use external signed archival for stronger assurance.

Approval means acceptance of an escalation recommendation, not permission to operate a mine. No email/SMS, regulatory filing, equipment action or official compliance certification occurs.

## Performance and recovery

- Groq is attempted first; Gemini follows on provider error. Each request has a 25-second timeout and at most one retry for rate limits/transient HTTP errors.
- Each inspection workflow has a 120-second budget. Failed jobs retain sanitized error categories; an administrator can retry them.
- The worker processes one job at a time. This is intentionally simple and appropriate for the classroom demonstration, not high-throughput telemetry ingestion.
- Queries return recent records (200 jobs, 100 traces, 1000 audit events). These are bounded views, not full archival exports.
- API health: `/health`; authenticated metrics: `/api/metrics`.

## Live-provider status at delivery

Groq: authenticated model discovery and JSON inference succeeded. A real evidence workflow produced two cited observations.

Gemini: configuration is present, but live verification encountered local TLS trust failures and HTTP 503. It remains an unverified fallback. Do not disable TLS validation to work around this. Validate the key, network trust and configured model in the deployment environment, then run `python check_providers.py`.

No public production deployment was performed. The Python backend is running locally; the provided Sites/Workers hosting option does not execute this Python AutoGen runtime.
