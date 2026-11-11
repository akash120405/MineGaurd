# Demonstration and syllabus mapping

This is a runnable implementation, not a static dashboard. Present the browser and code together. Allow approximately 12–15 minutes.

| Requirement | Implemented behavior | Evidence to show |
|---|---|---|
| Agent architecture | Three AutoGen RoutedAgent classes with typed messages | `app/agents.py`; activity trace |
| Reasoning / planning | Explicit five-step plan; LLM evidence interpretation plus deterministic measurement checks | Inspection detail |
| Tool calling | Agent invokes narrow evidence, retrieval, policy-evaluation and review-preparation tools | Tool names and timings in activity |
| API integration | Real Groq HTTP inference, Gemini fallback, authenticated inspection ingestion API | Provider checker, API docs, live workflow |
| Orchestration / automation | Submission creates a durable job; background worker starts it without another click | Queued → processing → review transition |
| Conversational interaction | Grounded policy Q&A, per-user persistent history | Ask MineGuard and reload |
| Python / AutoGen | Python FastAPI backend with actual AutoGen Core runtime | Imports and agent message handlers |
| Memory / state | SQLite evidence, jobs, policies, decisions, sessions and chat | Restart and show retained record |
| RAG | Lexical retrieval over curated rule text, exact source excerpts | Rule IDs, quotes and snapshots |
| Modular development | Separate models, tools, agents, providers, security, storage and API modules | Project structure |
| Multi-agent delegation | Analyst sends a package to Monitor; Monitor sends report to Escalation | Distinct traces with one job ID |
| Testing / debugging | Isolated end-to-end tests, sanitized failed-job status, admin retry | pytest and API validation errors |
| Hallucination detection | Reject nonexistent source IDs and nonmatching source/evidence quotes | Citation-gate test; rejected count |
| Responsible AI | Uncertainty shown, missing evidence cannot pass, no legal certification, no safety clearance | Policy notice and record recommendation |
| Prompt injection | Suspicious input screening, untrusted-data system prompt, restricted tools, no model approvals | Injection test scenario |
| Authentication / authorization | Salted passwords, HTTP-only sessions, CSRF, four roles, no self-approval | Inspector denied; separate reviewer succeeds |
| Secure tool use | Fixed provider endpoints, no dynamic SQL/URLs/shell from model, validated inputs | `tools.py`, `providers.py`, `models.py` |
| Auditability | Actor/time/action ledger with hash linking and report export | Audit screen and tamper-detection test |
| Observability | Agent latency, source count, provider status, failure and rejected-claim metadata | Agent activity and `/api/metrics` |
| Performance | Single bounded worker, 25-second provider timeout, one transient retry, 120-second workflow limit, WAL | Code and latency traces |
| Deployment | Running localhost service, nonroot Dockerfile, persistent volume and health check | `/health`, deployment guide |

## Presentation sequence

To demonstrate the corrective action workflow, approve a flagged inspection as reviewer, then open **Corrective actions** and assign a finding to an inspector with a due date. Sign in as the assigned inspector and submit closure evidence as text or import a text report. Return as reviewer and verify the evidence or send it back for more information. Verify that the decision appears in **Audit trail**.

To demonstrate mine access, use **Administration → Assign mine access** as admin to scope a non-admin account to the exact mine name in the inspection. Submit a second inspection with a different mine name from an admin account. The scoped account sees its own mine's records, while admin can see both. Existing accounts without a mine assignment retain workspace-wide access.

1. Explain the SIH problem: operational evidence is fragmented and every compliance conclusion needs traceable support.
2. Show the architecture and distinguish deterministic policy evaluation from AI interpretation.
3. Submit the demo breach scenario as inspector. Show the queue and three-agent trace.
4. Inspect exact source citations. Explain why citation matching alone cannot prove interpretation is correct.
5. Switch to reviewer and record an approval rationale. Explain the separation-of-duties check.
6. Show audit history, report export, conversational memory and policy management.
7. Run tests and demonstrate the prompt-injection and missing-measurement cases.
8. Explain operational limits candidly: demo policies, no real mine connector, Gemini connection unverified, single-node SQLite, no external notifications or operational automation.

## Suggested viva questions

- **Why multiple agents?** Each stage has a distinct responsibility and typed handoff; independent telemetry identifies where failure occurred.
- **Why deterministic checks?** Numeric policy evaluation must be reproducible. An LLM's fluent text is not sufficient evidence.
- **Why lexical RAG?** The small curated corpus does not require vector infrastructure. Retrieval is transparent, fast and testable; embeddings could help a larger verified corpus.
- **Can it guarantee no hallucinations?** No. It enforces exact citation matching and suppresses unsupported claims, but a valid quote can still support a wrong interpretation. Human review remains necessary.
- **Can it stop machinery?** No. No agent has operational control. It prepares review items and records decisions.
- **What happens during provider outage?** The system records the failure and tries Gemini after Groq. If both fail, deterministic checks continue with explicit AI-unavailable status.
- **What survives a restart?** Evidence, queued jobs, reports, decisions, audit and conversations. Single-process startup requeues interrupted jobs.
- **How would you scale?** Move state to PostgreSQL, use a leased external queue, introduce bounded parallel workers, tenant scoping, SSO and centralized telemetry.
