"""Grafana: views behind every Postgres panel, a read-only role for them, budget rows.

Anonymous Grafana viewers can send any SQL through the data source, so Grafana connects as
`grafana_reader`, which can read these aggregate views and nothing else. No view exposes a
question, an answer, a flag reason or an email address. `make grafana-db-user` gives the
role its login password from the environment.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-27
"""

from __future__ import annotations

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None

# In creation order: later views read dash_questions.
VIEWS: dict[str, str] = {
    # Closed /ask turns. /search diagnostics are left out: they never have a route, and the
    # only /ask rows without one are those that failed before routing.
    "dash_questions": """
        SELECT r.id, r.thread_id, r.user_id, u.role, u.team, r.route, r.decision,
               r.latency_ms, r.retrieval_ms, r.rerank_ms, r.created_at
        FROM requests r JOIN users u ON u.id = r.user_id
        WHERE r.decision IS NOT NULL AND (r.route IS NOT NULL OR r.decision = 'failed')
    """,
    "dash_spend_today": """
        WITH spend AS (
            SELECT coalesce(sum(usd), 0) AS usd FROM usage
            WHERE created_at >= date_trunc('day', now(), 'UTC')
        ), cap AS (
            SELECT max(usd_limit) AS usd FROM budgets WHERE scope = 'global' AND period = 'daily'
        )
        SELECT spend.usd AS spend_usd, cap.usd AS cap_usd,
               round(100 * spend.usd / nullif(cap.usd, 0), 1) AS pct_of_cap
        FROM spend, cap
    """,
    # Projection is linear in the days elapsed (at least one, so the first hours stay sane).
    "dash_spend_month": """
        WITH spend AS (
            SELECT coalesce(sum(usd), 0) AS usd FROM usage
            WHERE created_at >= date_trunc('month', now(), 'UTC')
        ), budget AS (
            SELECT max(usd_limit) AS usd FROM budgets
            WHERE scope = 'global' AND period = 'monthly'
        ), clock AS (
            SELECT greatest(extract(epoch FROM now() - date_trunc('month', now(), 'UTC'))
                            / 86400, 1) AS days_elapsed,
                   extract(day FROM date_trunc('month', now() AT TIME ZONE 'UTC')
                                    + interval '1 month' - interval '1 day') AS days_in_month
        )
        SELECT spend.usd AS spend_usd, budget.usd AS budget_usd,
               round(100 * spend.usd / nullif(budget.usd, 0), 1) AS pct_of_budget,
               round(spend.usd / clock.days_elapsed * clock.days_in_month, 4) AS projected_usd
        FROM spend, budget, clock
    """,
    # Every question's cost divided by the questions that got an answer.
    "dash_cost_daily": """
        SELECT date_trunc('day', q.created_at, 'UTC') AS day,
               count(*) AS questions,
               count(*) FILTER (WHERE q.decision = 'answered') AS answers,
               coalesce(sum(c.usd), 0) AS usd,
               round(coalesce(sum(c.usd), 0)
                     / nullif(count(*) FILTER (WHERE q.decision = 'answered'), 0), 6)
                   AS usd_per_answer
        FROM dash_questions q
        LEFT JOIN (SELECT request_id, sum(usd) AS usd FROM usage GROUP BY request_id) c
               ON c.request_id = q.id
        GROUP BY 1
    """,
    # All model spend, ingestion embeddings included.
    "dash_cost_by_model_stage": """
        SELECT date_trunc('day', created_at, 'UTC') AS day, model, stage,
               sum(usd) AS usd, sum(input_tokens) AS input_tokens,
               sum(output_tokens) AS output_tokens, count(*) AS calls
        FROM usage GROUP BY 1, 2, 3
    """,
    "dash_cost_by_user": """
        SELECT date_trunc('day', q.created_at, 'UTC') AS day, q.role, q.team,
               count(DISTINCT q.id) AS questions, coalesce(sum(u.usd), 0) AS usd
        FROM dash_questions q LEFT JOIN usage u ON u.request_id = q.id
        GROUP BY 1, 2, 3
    """,
    "dash_cache_daily": """
        SELECT date_trunc('day', q.created_at, 'UTC') AS day,
               count(*) AS questions, count(h.request_id) AS cache_hits,
               round(100.0 * count(h.request_id) / count(*), 1) AS hit_rate_pct
        FROM dash_questions q
        LEFT JOIN (SELECT DISTINCT request_id FROM usage WHERE cache_hit) h
               ON h.request_id = q.id
        GROUP BY 1
    """,
    "dash_decisions_daily": """
        SELECT date_trunc('day', created_at, 'UTC') AS day, count(*) AS questions,
               count(*) FILTER (WHERE decision = 'answered') AS answered,
               count(*) FILTER (WHERE decision = 'abstained') AS abstained,
               count(*) FILTER (WHERE decision = 'refused') AS refused,
               count(*) FILTER (WHERE decision = 'failed') AS failed,
               count(*) FILTER (WHERE decision = 'paused') AS paused,
               round(100.0 * count(*) FILTER (WHERE decision = 'abstained') / count(*), 1)
                   AS abstain_rate_pct,
               round(100.0 * count(*) FILTER (WHERE decision = 'refused') / count(*), 1)
                   AS refusal_rate_pct,
               round(100.0 * count(*) FILTER (WHERE decision = 'failed') / count(*), 1)
                   AS failure_rate_pct
        FROM dash_questions GROUP BY 1
    """,
    # Cache hits never reach the reranker, so rerank percentiles only count turns that did.
    "dash_latency_hourly": """
        SELECT date_trunc('hour', created_at, 'UTC') AS hour, count(*) AS questions,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50_latency_ms,
               percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY rerank_ms)
                   FILTER (WHERE rerank_ms > 0) AS p50_rerank_ms,
               percentile_cont(0.95) WITHIN GROUP (ORDER BY rerank_ms)
                   FILTER (WHERE rerank_ms > 0) AS p95_rerank_ms,
               percentile_cont(0.95) WITHIN GROUP (ORDER BY retrieval_ms)
                   FILTER (WHERE rerank_ms > 0) AS p95_retrieval_ms
        FROM dash_questions GROUP BY 1
    """,
    "dash_adoption_weekly": """
        SELECT date_trunc('week', created_at, 'UTC') AS week,
               count(DISTINCT user_id) AS active_users, count(*) AS questions,
               round(count(*)::numeric / count(DISTINCT user_id), 1) AS questions_per_user
        FROM dash_questions GROUP BY 1
    """,
    "dash_tickets_daily": """
        SELECT date_trunc('day', q.created_at, 'UTC') AS day, count(*) AS questions,
               count(t.id) AS tickets,
               round(100.0 * count(t.id) / count(*), 1) AS escalation_rate_pct
        FROM dash_questions q LEFT JOIN tickets t ON t.request_id = q.id
        GROUP BY 1
    """,
    "dash_tickets_status": """
        SELECT status, count(*) AS tickets FROM tickets GROUP BY 1
    """,
    # The cover letter's first number, as a share of answered questions (docs/ARCHITECTURE §10).
    # Each answer counts once, with its latest vote.
    "dash_feedback_weekly": """
        SELECT date_trunc('week', q.created_at, 'UTC') AS week,
               count(*) AS answered, count(f.value) AS votes,
               count(*) FILTER (WHERE f.value = 'used_as_is') AS used_as_is,
               count(*) FILTER (WHERE f.value = 'used_with_edits') AS used_with_edits,
               count(*) FILTER (WHERE f.value = 'not_used') AS not_used,
               round(100.0 * count(*) FILTER (WHERE f.value = 'used_as_is') / count(*), 1)
                   AS used_as_is_pct
        FROM dash_questions q
        LEFT JOIN (SELECT DISTINCT ON (request_id) request_id, value FROM feedback
                   ORDER BY request_id, created_at DESC) f ON f.request_id = q.id
        WHERE q.decision = 'answered'
        GROUP BY 1
    """,
    # The second number: answers flagged at least once. Reasons stay out: the dashboard is public.
    "dash_flags_weekly": """
        SELECT date_trunc('week', q.created_at, 'UTC') AS week, count(*) AS answered,
               count(*) FILTER (WHERE EXISTS (SELECT FROM flags fl WHERE fl.request_id = q.id))
                   AS flagged,
               round(100.0 * count(*) FILTER (
                   WHERE EXISTS (SELECT FROM flags fl WHERE fl.request_id = q.id)) / count(*), 1)
                   AS flagged_pct
        FROM dash_questions q
        WHERE q.decision = 'answered'
        GROUP BY 1
    """,
    # One row per metric of the latest run of each kind. Scores are read from
    # scores->'overall' when it is an object, else from the top level; non-numbers are skipped.
    "dash_eval_latest": """
        SELECT e.kind, e.created_at, e.corpus_version, e.prompt_version, e.cost_usd,
               s.key AS metric, (s.value #>> '{}')::numeric AS value
        FROM (SELECT DISTINCT ON (kind) * FROM eval_runs ORDER BY kind, created_at DESC) e
        CROSS JOIN LATERAL jsonb_each(
            CASE WHEN jsonb_typeof(e.scores -> 'overall') = 'object'
                 THEN e.scores -> 'overall' ELSE e.scores END
        ) s
        WHERE jsonb_typeof(s.value) = 'number'
    """,
}

READER = "grafana_reader"
# dash_questions holds request, thread and user ids, which open other visitors' history and
# receipts through the API. The other views read it with their owner's rights.
READABLE = [name for name in VIEWS if name != "dash_questions"]


def upgrade() -> None:
    for name, query in VIEWS.items():
        op.execute(f"CREATE VIEW {name} AS {query}")
    # Roles are cluster-wide and bas_test shares the server, hence the existence check.
    op.execute(
        f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{READER}') "
        f"THEN CREATE ROLE {READER} NOLOGIN; END IF; END $$"
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {READER}")
    op.execute(f"GRANT SELECT ON {', '.join(READABLE)} TO {READER}")
    # A public SQL surface: bound what one anonymous viewer can hold or run, and leave no
    # temp tables to fill the disk with (the app and LiteLLM connect as the owner).
    op.execute(f"ALTER ROLE {READER} CONNECTION LIMIT 5")
    op.execute(f"ALTER ROLE {READER} SET statement_timeout = '5s'")
    op.execute(
        "DO $$ BEGIN EXECUTE format('REVOKE TEMP ON DATABASE %I FROM PUBLIC', "
        "current_database()); END $$"
    )
    # The daily row is rewritten from DAILY_USD_CAP at every app start; the monthly one is
    # the app's LiteLLM virtual-key budget (llm/provision.py).
    op.execute(
        "INSERT INTO budgets (id, scope, period, usd_limit) VALUES "
        "(gen_random_uuid(), 'global', 'daily', 3), (gen_random_uuid(), 'global', 'monthly', 5)"
    )


def downgrade() -> None:
    op.execute("DELETE FROM budgets WHERE scope = 'global'")
    for name in reversed(VIEWS):
        op.execute(f"DROP VIEW {name}")
    # The role stays: it is cluster-wide and may hold grants in another database.
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {READER}")
    op.execute(
        "DO $$ BEGIN EXECUTE format('GRANT TEMP ON DATABASE %I TO PUBLIC', "
        "current_database()); END $$"
    )
