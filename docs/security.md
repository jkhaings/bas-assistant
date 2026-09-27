# Security: the fences, and what they answer

The demo is a public link with no login, so every visitor is anonymous and every control has to
hold without trusting the caller. The same controls apply to the internal deployment, with SSO
in place of the role switcher. This page lists what is built (session C) and where it lives.

## The fences

| Fence | Where | What it does | Tested by |
|---|---|---|---|
| Input: PII | `guardrails/input.redact`, called in `agent/turn.open_turn`, and in `/search` before the query embedding | Presidio (spaCy `en_core_web_sm`, plus a street-address pattern) replaces emails, phones, names, places and street addresses with `<ENTITY_TYPE>` before anything else happens. After that point only the redacted text exists: the cache key, the `requests` row, the graph checkpoints, the thread history and every model call. An `input_redacted` audit row records the count per entity type, never the values. | `tests/unit/test_input_fence.py`, red team `test_personal_data_in_a_question_is_redacted_before_storage_and_logs` |
| Input: injection and off-topic rail | `agent/nodes.screen` (patterns, $0), the router call (`llm/router.py`, `prompts/router.md`) | First, a narrow list of instruction-override phrasings, checked in code. Then the one `fast` router call also returns `is_injection`, `is_off_topic` and `reason`. Either rail sends the graph to `refuse`, which gives a fixed plain message and decision `refused` and writes an `input_refused` audit row (rail, kind, the model's reason). The model's reason is never shown. | `test_input_fence.py`, red team direct injection and off-topic cases |
| Input: abuse | `guardrails/limits.per_ip_limit` on `/ask`, `/ask/stream`, `/approve` and `/search` | A per-IP sliding window in Redis: 20 requests a minute by default (`IP_RATE_LIMIT`). Rejected attempts count, so a client that keeps hammering stays blocked. One `rate_limited` audit row per burst. Also the daily USD cap (503), the per-role daily allowance (429) and a spent LiteLLM virtual key (429). All of them answer `{reason, message, resets_at}`, and each writes an audit row. | `tests/unit/test_limits.py`, acceptance run in `outputs/HANDOFF_C.md` |
| Retrieval | `retrieval/store.py` (every query ANDs `acl_groups &&`), `agent/nodes.retrieve` | The SQL filter always uses the role's own groups. The retrieve node raises if the request's user context disagrees with its role. Passages reach the model as escaped `<passage id=… source_url=…>` blocks, and the system prompt says text inside them is data, never instructions. | `test_prompts.py::test_a_user_context_wider_than_its_role_never_reaches_the_retriever`, integration ACL tests, red team planted-document case |
| Model | `agent/prompts/*.md`, `llm/gateway.complete` | The system prompt holds invariants only. Temperature 0. Output is strict JSON schema. `max_tokens` caps: 120 router, 700 answer. A role without `create_ticket` is never told tickets exist. `PROMPT_VERSION` (a hash of the prompt files) is recorded on every request and eval run. | `test_memory.py`, `test_prompts.py` |
| Output | `guardrails/output.find_violations`, run by the `validate` node | Every citation must be a retrieved passage. Every followable link must be a retrieved passage's `source_url`, in any form: bare, `www.`, inline, reference-style, autolink, HTML. No images. No personal data (email, phone, person, street address) that the passages do not contain. On a violation, one retry with the violations listed; then decision `failed`, a fixed message and an `answer_rejected` audit row. | `tests/unit/test_validate.py`, red team exfiltration and planted-document cases |
| Action | `agent/nodes.propose_ticket`, `human_gate`, `agent/api.approve` | A ticket needs `create_ticket` in the role's tools. The graph pauses at a LangGraph `interrupt`. `/approve` needs both the admin token (constant-time compare) and a role holding `approve_ticket`; the admin token alone is not enough. A Redis lock stops a double resume. Nothing is filed without an approval. | `tests/unit/test_gate.py`, red team tool-abuse case |
| Audit | `audit.write_audit` | Append-only rows: `input_redacted`, `input_refused`, `decision` (every closed `/ask` request, cache hits included; `/search` stores its row without one), `rate_limited`, `daily_cap_reached`, `allowance_used`, `approve_refused`, `answer_rejected`, `ticket_*`. No raw question and no PII in `detail`. | every red-team case asserts an audit row for its request |

Logs are structured JSON. A regex safety net (`logging.RedactingFilter`) strips key shapes and
email addresses from every record. No code path logs the question, the headers or the settings.

## OWASP Top 10 for LLM applications (2025)

| Risk | Control here | Status |
|---|---|---|
| LLM01 Prompt injection | Direct: the pattern rail, then the router's `is_injection` flag, then `refuse`. Indirect: passages are escaped data blocks, the system prompt says so, and the output fence blocks the links and images an injected instruction would produce. | Built. Red team covers direct, indirect (a planted document) and exfiltration. |
| LLM02 Sensitive information disclosure | Presidio on the question before storage and models. The output PII check. The ACL filter in SQL, so support never receives engineer-only passages. Thread history is readable only by the role that started the thread. | Built |
| LLM03 Supply chain | Dependencies pinned in `uv.lock`, each justified in `docs/adr/0002`. The LiteLLM image is pinned by digest. gitleaks runs pre-commit. | Built. No SBOM or dependency audit in CI yet. |
| LLM04 Data and model poisoning | The corpus is public vendor documents only, crawled from an allowlist (`data/SOURCES.md`). A poisoned passage is still only data (see LLM01). | Partly: no integrity check on crawled content beyond content hashes |
| LLM05 Improper output handling | The output fence: citations are a subset of the retrieved ids, links are only source URLs, no images, schema validated, fail closed. The UI renders the answer only after `validate` passes (the stream sends nodes, not tokens). | Built |
| LLM06 Excessive agency | One action (propose a ticket), per-role tool allowlist, human gate, approval needs the admin token and the approve tool. `act` writes an internal table only (no Jira). | Built |
| LLM07 System prompt leakage | The prompt holds no secrets. Requests to reveal it are refused by the pattern rail. | Built |
| LLM08 Vector and embedding weaknesses | ACL filter in every retrieval query (vector and lexical), and again when chunks and parents are fetched by id. | Built |
| LLM09 Misinformation | Answers only from passages, with citations. `answerable: false` abstains with a fixed message. Golden set and RAGAS faithfulness (`make eval`). | Built. No production sampling of faithfulness yet. |
| LLM10 Unbounded consumption | Per-IP limit, per-role daily allowance, global daily USD cap, LiteLLM virtual-key budgets (a spent key answers 429), `max_tokens` on every call, history trimmed to 6 turns, exact-match cache. | Built |

## Deferred

- Presidio runs on `en_core_web_sm`. It misses some names and most bare city names, which the
  street-address pattern does not cover. A larger model or a transformer NER would catch more at
  image and CI cost.
- The output PII check skips place names: spaCy tags hostnames as places, and a city is not a
  personal-data leak.
- The red-team suite runs locally (`make redteam`), against live models. CI runs its unit
  mirror (fake LLM) on every PR, because CI makes no LLM calls.
- The per-IP limit keys on `request.client.host`. Behind Caddy (session E), uvicorn must trust
  the proxy's `X-Forwarded-For` (`FORWARDED_ALLOW_IPS`), or every visitor shares one address.
- No login: roles come from a header anyone can set. Only the admin token protects approvals.
  SSO (Entra ID) replaces the switcher in production.
- No dependency vulnerability scan, and no SBOM.
- LiteLLM spend logs keep per-call cost and metadata in the `litellm` database with no expiry.
  The app's checkpoints hold only redacted questions, but they have no expiry either.
