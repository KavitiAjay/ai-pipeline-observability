# AI-Powered dbt Pipeline Observability

When a dbt model fails in production, an engineer usually opens `run_results.json`, scrolls
through a wall of Snowflake error text, figures out the category of failure, and decides what
to do. This project automates that triage step with Snowflake Cortex.

After every dbt run, a Python job parses the results, sends each failure to a Cortex LLM, and
gets back a structured classification (root cause category, likely fix, severity). The output
is written back to a Snowflake table and posted to Slack so the on-call engineer sees a plain
language summary instead of raw logs.

## Why this matters

RAG and LLM features usually live far from the data platform. This keeps them inside it. The
LLM call is a single line of SQL through `SNOWFLAKE.CORTEX.COMPLETE`, the classifications are a
governed table, and the whole thing runs on the same warehouse as the pipeline it is watching.
It is an AI feature built the way a data engineer would build it.

## Architecture

1. dbt runs and writes `target/run_results.json`.
2. `scripts/analyze_failures.py` reads that file and pulls out failed nodes.
3. Each failure is classified by Cortex `COMPLETE` using a structured JSON prompt.
4. Results land in `ANALYTICS.OBSERVABILITY.DBT_FAILURE_ANALYSIS`.
5. A digest is posted to a Slack channel.

## Stack

Snowflake, Snowflake Cortex, dbt Core, Python, Slack, GitHub Actions.

## Run it

1. Create the Snowflake objects in `snowflake/setup.sql`.
2. Set the environment variables in `.env.example`.
3. `cd dbt && dbt build` (failures are expected on the seeded bad model, that is the point).
4. `python scripts/analyze_failures.py`.

The included `dbt/models/staging/stg_orders.sql` is intentionally broken so you can watch the
analyzer classify a real failure on the first run.

## What to highlight in interviews

The interesting design choice is treating the LLM output as a typed column, not free text. The
prompt forces JSON, the loader validates it, and downstream you can query failures by category
the same way you would query any other table. That is the difference between a demo and
something you would actually put in front of an on-call rotation.
