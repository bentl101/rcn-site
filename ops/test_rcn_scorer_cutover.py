#!/usr/bin/env python3
"""Create a temporary n8n webhook to test Codex and OpenCode Go scorer paths.

The workflow has no CRM, email, Sheets, or Google Ads nodes. It is activated,
called twice with synthetic feature-only data, verified, then removed.
"""

from __future__ import annotations

import copy
import json
import secrets
import sys
import time
import urllib.error
import urllib.request
import uuid

import patch_rcn_pacing_scorer as patcher


def code_node(name: str, node_id: str, position: list[int], code: str, on_error=None) -> dict:
    result = {
        "parameters": {"language": "javaScript", "jsCode": code.strip() + "\n"},
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
    }
    if on_error:
        result["onError"] = on_error
    return result


def build_workflow(main: dict, path: str, secret: str) -> dict:
    codex = copy.deepcopy(patcher.node(main, "Codex Score Lead"))
    codex.update({"id": "rcn-test-codex", "position": [520, -80]})
    codex["parameters"]["model"] = "gpt-5.5"
    codex["parameters"]["reasoningEffort"] = "high"
    codex["parameters"]["codexBin"] = "/home/node/.n8n/codex/codex-runner-isolated"
    codex["parameters"].setdefault("options", {})["timeoutSeconds"] = 180

    webhook = {
        "parameters": {"httpMethod": "POST", "path": path, "responseMode": "onReceived", "options": {}},
        "id": "rcn-test-webhook",
        "name": "Test Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [0, 0],
        "webhookId": f"rcn-test-{uuid.uuid4()}",
    }
    build_signals = code_node(
        "Build Signals", "rcn-test-build-signals", [390, 0],
        "return $input.all();",
    )
    prepare = code_node(
        "Prepare Test",
        "rcn-test-prepare",
        [260, 0],
        f"""
const supplied = String(($json.headers || {{}})['x-rcn-test'] || '');
if (supplied !== {json.dumps(secret)}) return [];
const request = $json.body || {{}};
return [{{json:{{
  mode:String(request.mode || 'codex'),
  body:{{lead_order_id:'RCN-SYNTHETIC-SCORER-TEST'}},
  _features:{{
    name:'Synthetic Test', destination:'danube', supported_destination:true,
    preferred_operator:'Scenic', budget:'Under $2,000', duration:'7 nights',
    guests:'2', months_until_travel:1, phone_valid_shape:true,
    phone_valid_veriphone:true, email_mx_valid:true, email_mailbox_valid:true,
    email_free_provider:true, honeypot_filled:false, name_repeated:false,
    referrer_suspicious:false, time_on_page_seconds:149
  }}
}}}}];
""",
    )
    route = {
        "parameters": {
            "options": {},
            "conditions": {
                "options": {"leftValue": "", "caseSensitive": True, "typeValidation": "loose"},
                "combinator": "and",
                "conditions": [{
                    "id": "rcn-test-mode",
                    "leftValue": "={{ $json.mode }}",
                    "rightValue": "codex",
                    "operator": {"type": "string", "operation": "equals", "name": "filter.operator.equals"},
                }],
            },
        },
        "id": "rcn-test-route",
        "name": "IF Codex Path",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [400, 0],
    }
    build_fallback = patcher.build_opencode_prompt_node([520, 160])
    execute_fallback = patcher.execute_opencode_node([760, 160])
    normalize_fallback = patcher.normalize_opencode_node([1000, 160])
    finish_codex = code_node(
        "Finish Codex Test", "rcn-test-finish-codex", [760, -80],
        """
const value = $input.first().json || {};
const content = value.choices?.[0]?.message?.content || '';
const parsed = JSON.parse(content);
if (!Number.isFinite(Number(parsed.lead_score))) throw new Error('Codex score missing');
return [{json:{path:'codex', model:value._scorer_model, score:Number(parsed.lead_score), decision:parsed.decision}}];
""",
    )
    finish_fallback = code_node(
        "Finish Fallback Test", "rcn-test-finish-fallback", [1240, 160],
        """
const value = $input.first().json || {};
const content = value.choices?.[0]?.message?.content || '';
const parsed = JSON.parse(content);
if (!Number.isFinite(Number(parsed.lead_score))) throw new Error('Fallback score missing');
return [{json:{path:'opencode-go', model:value._scorer_model, score:Number(parsed.lead_score), decision:parsed.decision}}];
""",
    )
    return {
        "name": f"RCN scorer cutover test {path[-8:]}",
        "nodes": [webhook, prepare, build_signals, route, codex, build_fallback, execute_fallback,
                  normalize_fallback, finish_codex, finish_fallback],
        "connections": {
            "Test Webhook": {"main": [[{"node": "Prepare Test", "type": "main", "index": 0}]]},
            "Prepare Test": {"main": [[{"node": "Build Signals", "type": "main", "index": 0}]]},
            "Build Signals": {"main": [[{"node": "IF Codex Path", "type": "main", "index": 0}]]},
            "IF Codex Path": {"main": [
                [{"node": "Codex Score Lead", "type": "main", "index": 0}],
                [{"node": "Build OpenCode Fallback", "type": "main", "index": 0}],
            ]},
            "Codex Score Lead": {"main": [[{"node": "Finish Codex Test", "type": "main", "index": 0}], []]},
            "Build OpenCode Fallback": {"main": [[{"node": "Call OpenCode Go Fallback", "type": "main", "index": 0}]]},
            "Call OpenCode Go Fallback": {"main": [[{"node": "Normalize OpenCode Fallback", "type": "main", "index": 0}], []]},
            "Normalize OpenCode Fallback": {"main": [[{"node": "Finish Fallback Test", "type": "main", "index": 0}], []]},
        },
        "settings": {
            "executionOrder": "v1", "saveDataSuccessExecution": "all",
            "saveDataErrorExecution": "all", "saveExecutionProgress": False,
            "saveManualExecutions": False,
        },
    }


def post(path: str, secret: str, mode: str) -> None:
    request = urllib.request.Request(
        f"http://localhost:5678/webhook/{path}",
        data=json.dumps({"mode": mode}).encode(),
        headers={"Content-Type": "application/json", "X-RCN-Test": secret},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"test webhook returned HTTP {response.status}")


def wait_execution(api: patcher.N8nApi, workflow_id: str, seen: set[str], timeout: int = 240) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = api.call("GET", f"/executions?workflowId={workflow_id}&limit=10").get("data", [])
        for row in rows:
            execution_id = str(row.get("id") or "")
            if execution_id and execution_id not in seen and row.get("status") in {"success", "error", "crashed", "canceled"}:
                return api.call("GET", f"/executions/{execution_id}?includeData=true")
        time.sleep(1)
    raise RuntimeError("timed out waiting for scorer test")


def result(execution: dict, node_name: str) -> dict:
    if execution.get("status") != "success":
        message = execution.get("data", {}).get("resultData", {}).get("error", {}).get("message")
        raise RuntimeError(f"execution {execution.get('id')} failed: {message}")
    run_data = execution.get("data", {}).get("resultData", {}).get("runData", {})
    value = patcher.execution_node(run_data, node_name)
    if not value:
        diagnostics = {}
        for name, runs in run_data.items():
            run = (runs or [{}])[0]
            error = (run.get("error") or {}).get("message")
            outputs = run.get("data", {}).get("main") or []
            output_json = []
            for branch in outputs:
                for item in branch or []:
                    value_json = item.get("json") or {}
                    output_json.append({
                        key: value_json.get(key)
                        for key in ("error", "path", "model", "score", "decision")
                        if key in value_json
                    })
            diagnostics[name] = {"error": error, "outputs": output_json}
        raise RuntimeError(
            f"execution {execution.get('id')} did not reach {node_name}: "
            + json.dumps(diagnostics, ensure_ascii=False)
        )
    return value


def diagnostic_results(execution: dict) -> list[dict]:
    run_data = execution.get("data", {}).get("resultData", {}).get("runData", {})
    values = []
    for node_name in ("Finish Codex Test", "Finish Fallback Test"):
        item = patcher.execution_node(run_data, node_name)
        if item:
            values.append({"execution_id": str(execution.get("id")), **item})
    return values


def main() -> int:
    api = patcher.N8nApi(patcher.load_key())
    main_workflow = api.call("GET", f"/workflows/{patcher.WORKFLOW_ID}")
    suffix = uuid.uuid4().hex
    path = f"rcn-scorer-cutover-test-{suffix}"
    secret = secrets.token_urlsafe(36)
    workflow = build_workflow(main_workflow, path, secret)
    created = api.call("POST", "/workflows", patcher.workflow_payload(workflow))
    workflow_id = created["id"]
    executions: list[str] = []
    try:
        api.call("POST", f"/workflows/{workflow_id}/activate")
        seen: set[str] = set()
        outputs = []
        for mode, finish_node in (("codex", "Finish Codex Test"), ("fallback", "Finish Fallback Test")):
            post(path, secret, mode)
            execution = wait_execution(api, workflow_id, seen)
            execution_id = str(execution["id"])
            seen.add(execution_id)
            executions.append(execution_id)
            try:
                outputs.append({"execution_id": execution_id, **result(execution, finish_node)})
            except Exception:
                print(json.dumps({
                    "failed_execution": execution_id,
                    "status": execution.get("status"),
                    "partial_results": diagnostic_results(execution),
                    "last_node": execution.get("data", {}).get("resultData", {}).get("lastNodeExecuted"),
                    "error": execution.get("data", {}).get("resultData", {}).get("error", {}).get("message"),
                }, indent=2), file=sys.stderr)
                raise
        print(json.dumps({"workflow_id": workflow_id, "tests": outputs}, indent=2))
    finally:
        try:
            api.call("POST", f"/workflows/{workflow_id}/deactivate")
        except Exception as exc:
            print(f"WARNING: could not deactivate test workflow: {exc}", file=sys.stderr)
        for execution_id in executions:
            try:
                api.call("DELETE", f"/executions/{execution_id}")
            except Exception as exc:
                print(f"WARNING: could not delete test execution {execution_id}: {exc}", file=sys.stderr)
        try:
            api.call("DELETE", f"/workflows/{workflow_id}")
        except Exception as exc:
            print(f"WARNING: could not delete test workflow: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
