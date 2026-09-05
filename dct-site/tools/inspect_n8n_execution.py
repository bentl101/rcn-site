#!/usr/bin/env python3
"""Print a non-sensitive QA summary for one DCT n8n execution.

Run this on the n8n VPS. It deliberately reports identifier presence and
error classifications without printing lead PII, click IDs, access tokens, or
other secrets.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import urllib.request


BASE = "http://localhost:5678/api/v1"
WORKFLOW_ID = "PmntlqBanV9ZMy3O"


def api_key() -> str:
    for line in pathlib.Path("/home/ben/.secrets").read_text().splitlines():
        if line.startswith("N8N_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("N8N_API_KEY not found")


def get_execution(execution_id: str) -> dict:
    request = urllib.request.Request(
        f"{BASE}/executions/{execution_id}?includeData=true",
        headers={"X-N8N-API-KEY": api_key()},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def first_json(runs: list[dict]) -> dict:
    try:
        return runs[0]["data"]["main"][0][0].get("json", {})
    except (IndexError, KeyError, TypeError, AttributeError):
        return {}


def error_codes(value: object) -> list[str]:
    encoded = json.dumps(value, separators=(",", ":"))
    names = re.findall(
        r'"(?:conversionUploadError|requestError|authenticationError|authorizationError)":"([A-Z0-9_]+)"',
        encoded,
    )
    return sorted(set(names))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("execution_id")
    args = parser.parse_args()

    execution = get_execution(args.execution_id)
    if execution.get("workflowId") != WORKFLOW_ID:
        raise SystemExit(f"Execution is not for DCT workflow {WORKFLOW_ID}")

    run_data = execution.get("data", {}).get("resultData", {}).get("runData", {})
    nodes: dict[str, dict] = {}
    for name, runs in run_data.items():
        first = runs[0] if runs else {}
        item = first_json(runs)
        summary: dict[str, object] = {
            "status": first.get("executionStatus"),
            "duration_ms": first.get("executionTime"),
        }
        if first.get("error"):
            summary["node_error_codes"] = error_codes(first["error"])

        if name == "Format Lead Email":
            summary.update(
                lead_order_id=item.get("lead_order_id"),
                is_qa=item.get("is_qa"),
            )
        elif name == "Build Ads Upload":
            conversions = item.get("google_ads_request", {}).get("conversions", [])
            conversion = conversions[0] if conversions else {}
            summary.update(
                lead_order_id=item.get("lead_order_id"),
                route=item.get("ads_route"),
                action_id=item.get("ads_action_id"),
                validate_only=item.get("ads_validate_only"),
                has_gclid=bool(conversion.get("gclid")),
                has_gbraid=bool(conversion.get("gbraid")),
                has_wbraid=bool(conversion.get("wbraid")),
                user_identifier_count=len(conversion.get("userIdentifiers", [])),
            )
        elif name == "Get Google OAuth Token":
            summary["received_access_token"] = bool(item.get("access_token"))
        elif name == "Upload Click Conversion":
            partial = item.get("partialFailureError") or item.get("partial_failure_error")
            summary.update(
                has_partial_failure=bool(partial),
                google_error_codes=error_codes(partial or item.get("error") or item),
                results_returned=len(item.get("results", [])) if isinstance(item.get("results"), list) else 0,
                job_id_present=bool(item.get("jobId") or item.get("job_id")),
            )
        elif name == "Parse Ads Upload":
            summary.update(
                lead_order_id=item.get("lead_order_id"),
                accepted=item.get("ads_upload_accepted"),
                results_returned=item.get("ads_results_returned"),
                google_error_codes=error_codes(item.get("ads_upload_error", "")),
            )
        elif name in {"Send Email Notification", "Send Ads Failure Alert"}:
            accepted = item.get("accepted", [])
            rejected = item.get("rejected", [])
            summary.update(
                accepted_count=len(accepted) if isinstance(accepted, list) else None,
                rejected_count=len(rejected) if isinstance(rejected, list) else None,
            )
        nodes[name] = summary

    print(json.dumps({
        "execution_id": execution.get("id"),
        "workflow_id": execution.get("workflowId"),
        "status": execution.get("status"),
        "started_at": execution.get("startedAt"),
        "stopped_at": execution.get("stoppedAt"),
        "nodes": nodes,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
