#!/usr/bin/env python3
"""Replay one DCT GCLID conversion from a recorded n8n execution.

Run on the n8n VPS. The click identifier is read in memory from the historic
execution and is never printed. The caller must supply the expected Order ID;
the script refuses to upload if it does not match the execution exactly.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request


N8N_BASE = "http://localhost:5678/api/v1"
WORKFLOW_ID = "PmntlqBanV9ZMy3O"
CUSTOMER_ID = "3639225242"
LOGIN_CUSTOMER_ID = "3814278874"
GCLID_ACTION = f"customers/{CUSTOMER_ID}/conversionActions/7762251563"


def read_env(path: pathlib.Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip("\"'")
    return result


def n8n_key() -> str:
    return read_env(pathlib.Path("/home/ben/.secrets"))["N8N_API_KEY"]


def get_execution(execution_id: str) -> dict:
    request = urllib.request.Request(
        f"{N8N_BASE}/executions/{execution_id}?includeData=true",
        headers={"X-N8N-API-KEY": n8n_key()},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def first_json(runs: list[dict]) -> dict:
    try:
        return runs[0]["data"]["main"][0][0].get("json", {})
    except (IndexError, KeyError, TypeError, AttributeError):
        return {}


def access_token(env: dict[str, str]) -> str:
    body = urllib.parse.urlencode({
        "client_id": env["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": env["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": env["GOOGLE_ADS_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=body), timeout=30) as response:
        return json.load(response)["access_token"]


def google_error_codes(value: object) -> list[str]:
    return sorted(set(re.findall(
        r'"(?:conversionUploadError|requestError|authenticationError|authorizationError)":"([A-Z0-9_]+)"',
        json.dumps(value, separators=(",", ":")),
    )))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("execution_id")
    parser.add_argument("--order-id", required=True)
    parser.add_argument("--execute", action="store_true", help="record the conversion; otherwise validate only")
    args = parser.parse_args()

    execution = get_execution(args.execution_id)
    if execution.get("workflowId") != WORKFLOW_ID:
        raise SystemExit("Refusing: execution is not from the DCT form workflow")
    run_data = execution.get("data", {}).get("resultData", {}).get("runData", {})
    built = first_json(run_data.get("Build Ads Upload", []))
    conversions = built.get("google_ads_request", {}).get("conversions", [])
    if len(conversions) != 1:
        raise SystemExit("Refusing: execution does not contain exactly one conversion")
    conversion = dict(conversions[0])
    if built.get("ads_route") != "gclid" or not conversion.get("gclid"):
        raise SystemExit("Refusing: execution is not a GCLID conversion")
    if str(conversion.get("orderId") or "") != args.order_id:
        raise SystemExit("Refusing: supplied Order ID does not match the recorded conversion")

    conversion["conversionAction"] = GCLID_ACTION
    request_body = {
        "conversions": [conversion],
        "partialFailure": True,
        "validateOnly": not args.execute,
    }
    env = read_env(pathlib.Path("/home/ben/infra/n8n/.env"))
    token = access_token(env)
    request = urllib.request.Request(
        f"https://googleads.googleapis.com/v25/customers/{CUSTOMER_ID}:uploadClickConversions",
        data=json.dumps(request_body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "developer-token": env["GOOGLE_ADS_DEVELOPER_TOKEN"],
            "login-customer-id": LOGIN_CUSTOMER_ID,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        status = exc.code
        payload = json.loads(exc.read().decode("utf-8", errors="replace") or "{}")

    partial = payload.get("partialFailureError") or payload.get("partial_failure_error")
    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    accepted = status == 200 and not partial and (not args.execute or bool(results))
    print(json.dumps({
        "order_id": args.order_id,
        "action_id": "7762251563",
        "validate_only": not args.execute,
        "http_status": status,
        "accepted": accepted,
        "results_returned": len(results),
        "google_error_codes": google_error_codes(partial or payload.get("error") or payload),
        "partial_failure": bool(partial),
    }, separators=(",", ":")))
    return 0 if accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
