# Validation record — 4 November 2026

## Automated regression

Result: **12 passed in 20.05 seconds** on Python 3.12.14 / AutoGen Core 0.7.5. One upstream Starlette warning recommends a newer test HTTP client; it did not fail tests. JavaScript syntax validation passed with Node.js 24.

Covered scenarios:

1. Authentication required, CSRF enforced, viewer cannot submit, inspector cannot administer.
2. Real AutoGen runtime completes analyst → monitor → escalation, then a separate reviewer approves; duplicate decisions fail.
3. Prompt-injection screening blocks provider invocation.
4. Missing measurements do not pass.
5. Fabricated citations are rejected; matching quotes are accepted.
6. Mutated audit payload invalidates the hash chain.
7. Policy IDs cannot be overwritten; invalid measurements and timestamps fail; self-approval fails.
8. Chat retrieval and persistent per-user memory work.
9. Groq failure invokes Gemini fallback (mocked provider test).
10. Password hashes have unique salts and reject wrong passwords.
11. Malformed model claim identifiers are suppressed safely.
12. No matching policy causes abstention instead of an invented answer.

Tests use temporary isolated databases. Live validation below uses the installed local app with the supplied key; it is separate from the deterministic test suite.

## Live provider and browser verification

- Groq key authenticated successfully against its model-discovery endpoint.
- The initially selected older model returned 404. The integration was updated to available `openai/gpt-oss-20b`.
- A minimal real inference returned valid JSON.
- Browser login as inspector succeeded. A demo inspection was submitted through the form, not inserted directly into the database.
- The background worker ran all three AutoGen agents and saved three policy checks.
- The live Groq response produced two verified cited observations with zero rejected citations.
- Methane 1.4% and airflow 4.2 m³/s triggered demo policy breaches; dust 1.2 mg/m³ passed its demo threshold.
- The job became high-priority and awaited review.
- A separate reviewer account signed in and approved the simulated escalation with a rationale. The dashboard showed the persisted approved record.
- Live conversational Q&A returned a Groq answer with the methane policy excerpt.
- The browser was reloaded; the authenticated dashboard retained its record and counters.
- The responsive narrow layout was visually inspected. Native progress indicators were corrected and rechecked. `dashboard.png` captures the final view.

## Limitations of validation

Gemini live inference could not be confirmed. Requests encountered TLS trust errors and HTTP 503 from this environment; its configured key was not declared valid or invalid based on those failures. Fallback routing is covered by automated tests, but a successful real Gemini response remains outstanding.

Docker is not installed on this machine; the Dockerfile and Compose configuration were provided but not executed. No public hosting deployment, external mine-system integration, SMS/email notification, PDF OCR, regulatory accuracy validation, penetration test or high-volume load test was performed.

Policies and evidence used in the demonstration are synthetic. Citation matching does not prove semantic correctness, and injection screening is not a guarantee against every attack. Human review is mandatory for exceptions, and no equipment control is exposed.
