"""Parse dbt run_results.json, classify failures with Snowflake Cortex, store and notify.

Run after `dbt build`. Expects a Snowflake connection via environment variables and an
optional Slack webhook. Designed to be the kind of script you would actually schedule, so it
validates the model output instead of trusting it.
"""

import json
import os
import sys
from pathlib import Path

import snowflake.connector
import requests

RUN_RESULTS = Path(os.getenv("DBT_RUN_RESULTS", "dbt/target/run_results.json"))
CORTEX_MODEL = os.getenv("CORTEX_MODEL", "mistral-large2")
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")  # optional

PROMPT = (
    "You are a dbt failure triage assistant. Classify the failure and respond ONLY with "
    "JSON of shape {{\"category\": str, \"likely_fix\": str, \"severity\": str}}. "
    "category is one of SCHEMA_DRIFT, PERMISSION, DATA_QUALITY, SYNTAX, RESOURCE, OTHER. "
    "severity is one of LOW, MEDIUM, HIGH. Failure message:\n{msg}"
)

VALID_CATEGORIES = {
    "SCHEMA_DRIFT", "PERMISSION", "DATA_QUALITY", "SYNTAX", "RESOURCE", "OTHER",
}
VALID_SEVERITY = {"LOW", "MEDIUM", "HIGH"}


def connect():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.getenv("SNOWFLAKE_ROLE", "SYSADMIN"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "DE_WH"),
        database="ANALYTICS",
        schema="OBSERVABILITY",
    )


def load_failures(path: Path):
    if not path.exists():
        print(f"No run_results at {path}; nothing to analyze.")
        return []
    data = json.loads(path.read_text())
    failures = []
    for r in data.get("results", []):
        if r.get("status") in {"error", "fail"}:
            failures.append(
                {
                    "node": r.get("unique_id", "unknown"),
                    "status": r.get("status"),
                    "message": (r.get("message") or "")[:4000],
                }
            )
    return failures


def classify(cur, message: str) -> dict:
    """Send one failure to Cortex and validate the JSON it returns."""
    cur.execute(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s)",
        (CORTEX_MODEL, PROMPT.format(msg=message)),
    )
    raw = cur.fetchone()[0]
    try:
        parsed = json.loads(raw.strip().strip("`").replace("json", "", 1))
    except (json.JSONDecodeError, AttributeError):
        return {"category": "OTHER", "likely_fix": "Model returned non-JSON output.",
                "severity": "MEDIUM"}
    cat = str(parsed.get("category", "OTHER")).upper()
    sev = str(parsed.get("severity", "MEDIUM")).upper()
    return {
        "category": cat if cat in VALID_CATEGORIES else "OTHER",
        "likely_fix": str(parsed.get("likely_fix", ""))[:1000],
        "severity": sev if sev in VALID_SEVERITY else "MEDIUM",
    }


def store(cur, run_id, node, status, message, result):
    cur.execute(
        """INSERT INTO DBT_FAILURE_ANALYSIS
           (run_id, node_name, status, raw_message, category, likely_fix, severity)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (run_id, node, status, message,
         result["category"], result["likely_fix"], result["severity"]),
    )


def notify_slack(summaries):
    if not SLACK_WEBHOOK or not summaries:
        return
    lines = [f"*dbt run had {len(summaries)} failure(s)*"]
    for s in summaries:
        lines.append(
            f"`{s['node']}` -> *{s['category']}* ({s['severity']}). {s['likely_fix']}"
        )
    requests.post(SLACK_WEBHOOK, json={"text": "\n".join(lines)}, timeout=10)


def main():
    failures = load_failures(RUN_RESULTS)
    if not failures:
        print("No failures to analyze. Pipeline is healthy.")
        return 0

    run_id = os.getenv("GITHUB_RUN_ID", "local")
    summaries = []
    conn = connect()
    try:
        cur = conn.cursor()
        for f in failures:
            result = classify(cur, f["message"])
            store(cur, run_id, f["node"], f["status"], f["message"], result)
            summaries.append({"node": f["node"], **result})
            print(f"{f['node']} -> {result['category']} ({result['severity']})")
        conn.commit()
    finally:
        conn.close()

    notify_slack(summaries)
    return 0


if __name__ == "__main__":
    sys.exit(main())
