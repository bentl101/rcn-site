#!/usr/bin/env python3
"""Safely rescore one saved RCN lead and, when good, use its action workflow.

The temporary workflow contains only the saved Build Signals payload, the live
Codex scorer, and the live Parse Score node.  It cannot email, write CRM/Sheets,
or call Google Ads.  A good result is then submitted through the existing,
idempotent lead-action workflow so the normal audit row and Ads upload path are
used.  Temporary workflow/execution data are deleted in a finally block.
"""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import secrets
import sys
import time
import urllib.parse
import urllib.request
import uuid

import patch_rcn_pacing_scorer as patcher


ACTION_WORKFLOW_ID = "LpJaof03qyAbSGip"
SHEET_ID = "1XPz9neZsZyWtKN2pETvI_9Yb_wbSQHoC2ubBVL7pkHA"
SHEETS_CREDENTIAL = {
    "googleSheetsOAuth2Api": {
        "id": "YAn0z4KXSLPGMLum", "name": "Google Sheets account",
    }
}


def saved_node(execution: dict, name: str) -> dict:
    value = patcher.execution_node(
        execution.get("data", {}).get("resultData", {}).get("runData", {}), name
    )
    if not value:
        raise RuntimeError(f"Saved execution has no output for {name!r}")
    return value


def workflow_definition(main: dict, path: str, secret: str, signals: dict) -> dict:
    codex = copy.deepcopy(patcher.node(main, "Codex Score Lead"))
    codex.update({"id": "rcn-recovery-codex", "position": [520, 0]})
    parse = copy.deepcopy(patcher.node(main, "Parse Score"))
    parse.update({"id": "rcn-recovery-parse", "position": [760, 0]})
    webhook = {
        "parameters": {
            "httpMethod": "POST", "path": path,
            "responseMode": "onReceived", "options": {},
        },
        "id": "rcn-recovery-webhook", "name": "Recovery Webhook",
        "type": "n8n-nodes-base.webhook", "typeVersion": 2,
        "position": [0, 0], "webhookId": f"rcn-recovery-{uuid.uuid4()}",
    }
    prepare_code = f"""
const supplied = String(($json.headers || {{}})['x-rcn-recovery'] || '');
if (supplied !== {json.dumps(secret)}) return [];
return [{{json:{json.dumps(signals, ensure_ascii=False)}}}];
""".strip() + "\n"
    prepare = {
        "parameters": {"language": "javaScript", "jsCode": prepare_code},
        "id": "rcn-recovery-prepare", "name": "Build Signals",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [260, 0],
    }
    return {
        "name": f"RCN isolated scorer recovery {path[-8:]}",
        "nodes": [webhook, prepare, codex, parse],
        "connections": {
            "Recovery Webhook": {"main": [[{"node": "Build Signals", "type": "main", "index": 0}]]},
            "Build Signals": {"main": [[{"node": "Codex Score Lead", "type": "main", "index": 0}]]},
            "Codex Score Lead": {"main": [[{"node": "Parse Score", "type": "main", "index": 0}], []]},
        },
        "settings": {
            "executionOrder": "v1", "saveDataSuccessExecution": "all",
            "saveDataErrorExecution": "all", "saveExecutionProgress": False,
            "saveManualExecutions": False,
        },
    }


def call_webhook(path: str, secret: str) -> None:
    request = urllib.request.Request(
        f"http://localhost:5678/webhook/{path}", data=b"{}", method="POST",
        headers={"Content-Type": "application/json", "X-RCN-Recovery": secret},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"Recovery webhook returned HTTP {response.status}")


def wait_for_execution(api: patcher.N8nApi, workflow_id: str, timeout: int = 240) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = api.call("GET", f"/executions?workflowId={workflow_id}&limit=5").get("data", [])
        for row in rows:
            if row.get("status") in {"success", "error", "crashed", "canceled"}:
                return api.call("GET", f"/executions/{row['id']}?includeData=true")
        time.sleep(1)
    raise RuntimeError("Timed out waiting for isolated recovery score")


def update_workflow_definition(path: str, secret: str, fields: dict) -> dict:
    """One-shot Scoring-row update with no append or downstream branches."""
    webhook = {
        "parameters": {
            "httpMethod": "POST", "path": path,
            "responseMode": "onReceived", "options": {},
        },
        "id": "rcn-recovery-update-webhook", "name": "Update Webhook",
        "type": "n8n-nodes-base.webhook", "typeVersion": 2,
        "position": [0, 0], "webhookId": f"rcn-recovery-update-{uuid.uuid4()}",
    }
    prepare = {
        "parameters": {"language": "javaScript", "jsCode": f"""
const supplied = String(($json.headers || {{}})['x-rcn-recovery'] || '');
if (supplied !== {json.dumps(secret)}) return [];
return [{{json:{json.dumps(fields, ensure_ascii=False)}}}];
""".strip() + "\n"},
        "id": "rcn-recovery-update-prepare", "name": "Prepare Scoring Update",
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [260, 0],
    }
    # n8n's Sheets node expects its expression strings to begin with "={{".
    # A normal f-string would consume one brace and silently turn them into
    # literal text, so build the expressions without brace interpolation.
    values = {key: "={{ $json." + key + " }}" for key in fields}
    update = {
        "parameters": {
            "authentication": "oAuth2", "resource": "sheet", "operation": "update",
            "documentId": {"__rl": True, "value": SHEET_ID, "mode": "id"},
            "sheetName": {"__rl": True, "value": "Scoring", "mode": "name"},
            "columns": {
                "mappingMode": "defineBelow", "value": values,
                "matchingColumns": ["lead_order_id"], "schema": [],
            },
            "options": {"handlingExtraData": "ignoreIt", "cellFormat": "RAW"},
        },
        "id": "rcn-recovery-update-sheet", "name": "Update Recovered Scoring",
        "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5,
        "position": [520, 0], "credentials": copy.deepcopy(SHEETS_CREDENTIAL),
        "alwaysOutputData": True,
    }
    return {
        "name": f"RCN scorer audit update {path[-8:]}",
        "nodes": [webhook, prepare, update],
        "connections": {
            "Update Webhook": {"main": [[{"node": "Prepare Scoring Update", "type": "main", "index": 0}]]},
            "Prepare Scoring Update": {"main": [[{"node": "Update Recovered Scoring", "type": "main", "index": 0}]]},
        },
        "settings": {
            "executionOrder": "v1", "saveDataSuccessExecution": "all",
            "saveDataErrorExecution": "all", "saveExecutionProgress": False,
            "saveManualExecutions": False,
        },
    }


def apply_scoring_update(api: patcher.N8nApi, fields: dict) -> str:
    suffix = uuid.uuid4().hex
    path = f"rcn-scorer-audit-update-{suffix}"
    secret = secrets.token_urlsafe(36)
    workflow = update_workflow_definition(path, secret, fields)
    created = api.call("POST", "/workflows", patcher.workflow_payload(workflow))
    workflow_id = str(created["id"])
    execution_id = None
    try:
        api.call("POST", f"/workflows/{workflow_id}/activate")
        call_webhook(path, secret)
        execution = wait_for_execution(api, workflow_id, timeout=90)
        execution_id = str(execution.get("id") or "")
        if execution.get("status") != "success":
            error = execution.get("data", {}).get("resultData", {}).get("error", {}).get("message")
            raise RuntimeError(f"Scoring audit update failed: {error}")
        run_data = execution.get("data", {}).get("resultData", {}).get("runData", {})
        if "Update Recovered Scoring" not in run_data:
            raise RuntimeError("Scoring audit update node did not run")
        node_run = (run_data.get("Update Recovered Scoring") or [{}])[0]
        if node_run.get("error"):
            raise RuntimeError(
                "Scoring audit update failed: "
                + str(node_run.get("error", {}).get("message") or node_run["error"])
            )
        return execution_id
    finally:
        try:
            api.call("POST", f"/workflows/{workflow_id}/deactivate")
        except Exception as exc:
            print(f"WARNING: could not deactivate audit updater: {exc}", file=sys.stderr)
        if execution_id:
            try:
                api.call("DELETE", f"/executions/{execution_id}")
            except Exception as exc:
                print(f"WARNING: could not delete audit update execution: {exc}", file=sys.stderr)
        try:
            api.call("DELETE", f"/workflows/{workflow_id}")
        except Exception as exc:
            print(f"WARNING: could not delete audit update workflow: {exc}", file=sys.stderr)


def submit_good_action(order_id: str, token: str) -> int:
    data = urllib.parse.urlencode({
        "oid": order_id, "action": "good", "token": token, "confirm": "yes",
    }).encode()
    request = urllib.request.Request(
        "https://n8.copperchunk.com/webhook/rcn-lead-action-confirm",
        data=data, method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 RCN-Scorer-Recovery",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()
        return response.status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("execution_json", type=pathlib.Path)
    parser.add_argument("--apply-good", action="store_true",
                        help="Queue the normal audited good-lead action when Codex sends to sales")
    parser.add_argument("--update-audit-only", action="store_true",
                        help="Rescore and update the existing Scoring row without queuing an action")
    args = parser.parse_args()
    execution = json.loads(args.execution_json.read_text(encoding="utf-8"))
    signals = saved_node(execution, "Build Signals")
    token_node = saved_node(execution, "Generate Lead Action Token")
    order_id = str((signals.get("body") or {}).get("lead_order_id") or "")
    token = str(token_node.get("lead_action_token") or "")
    if not order_id or len(token) < 40:
        raise RuntimeError("Saved lead is missing order ID or action token")

    api = patcher.N8nApi(patcher.load_key())
    main_workflow = api.call("GET", f"/workflows/{patcher.WORKFLOW_ID}")
    suffix = uuid.uuid4().hex
    path = f"rcn-isolated-score-recovery-{suffix}"
    secret = secrets.token_urlsafe(36)
    workflow = workflow_definition(main_workflow, path, secret, signals)
    created = api.call("POST", "/workflows", patcher.workflow_payload(workflow))
    workflow_id = str(created["id"])
    execution_id = None
    try:
        api.call("POST", f"/workflows/{workflow_id}/activate")
        call_webhook(path, secret)
        recovery_execution = wait_for_execution(api, workflow_id)
        execution_id = str(recovery_execution.get("id") or "")
        parsed = saved_node(recovery_execution, "Parse Score")
        body = parsed.get("body") or {}
        output = {
            "source_execution_id": str(execution.get("id") or ""),
            "recovery_execution_id": execution_id,
            "lead_order_id": order_id,
            "scorer_model": body.get("scorer_model"),
            "lead_score": body.get("lead_score"),
            "decision": body.get("decision"),
            "destination_validity": body.get("destination_validity"),
            "confidence": body.get("confidence"),
            "reason_short": body.get("reason_short"),
            "action_queued": False,
        }
        if args.apply_good and body.get("decision") == "send_to_sales":
            output["action_http_status"] = submit_good_action(order_id, token)
            output["action_queued"] = output["action_http_status"] == 200
        if args.apply_good or args.update_audit_only:
            # The action worker writes manual_action asynchronously. This
            # update deliberately excludes manual_action so it cannot race or
            # erase the worker's audited upload state.
            audit_fields = {
                "lead_order_id": order_id,
                "lead_score": body.get("lead_score"),
                "lead_quality": body.get("lead_quality"),
                "decision": body.get("decision"),
                "destination_validity": body.get("destination_validity"),
                "confidence": body.get("confidence"),
                "reason_short": body.get("reason_short"),
                "risk_flags": ", ".join(body.get("risk_flags") or []),
                "sales_note": body.get("sales_note"),
                "scorer_latency_ms": body.get("scorer_latency_ms"),
                "scorer_error": body.get("scorer_error"),
                "scored_at": body.get("scored_at"),
                "value_multiplier": body.get("value_multiplier"),
                "conversion_value_cad": body.get("conversion_value_cad"),
                "value_reason": body.get("value_reason"),
            }
            output["audit_update_execution_id"] = apply_scoring_update(api, audit_fields)
        print(json.dumps(output, indent=2, ensure_ascii=False))
    finally:
        try:
            api.call("POST", f"/workflows/{workflow_id}/deactivate")
        except Exception as exc:
            print(f"WARNING: could not deactivate recovery workflow: {exc}", file=sys.stderr)
        if execution_id:
            try:
                api.call("DELETE", f"/executions/{execution_id}")
            except Exception as exc:
                print(f"WARNING: could not delete recovery execution: {exc}", file=sys.stderr)
        try:
            api.call("DELETE", f"/workflows/{workflow_id}")
        except Exception as exc:
            print(f"WARNING: could not delete recovery workflow: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
