#!/usr/bin/env python3
"""Queue Ads retractions and correct Scoring rows for contact misroutes.

This uses the existing signed/idempotent lead-action workflow. The action
worker schedules the one-way Google Ads retraction no earlier than the normal
24-hour safety window. Raw contact data and action tokens are never printed.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request

import patch_rcn_pacing_scorer as patcher
from recover_rcn_scorer_lead import apply_scoring_update


def saved(execution: dict, name: str) -> dict:
    value = patcher.execution_node(
        execution.get("data", {}).get("resultData", {}).get("runData", {}), name
    )
    if not value:
        raise RuntimeError(f"Execution {execution.get('id')} has no {name} output")
    return value


def submit_bad(order_id: str, token: str) -> int:
    payload = urllib.parse.urlencode({
        "oid": order_id, "action": "bad", "token": token, "confirm": "yes",
    }).encode()
    request = urllib.request.Request(
        "https://n8.copperchunk.com/webhook/rcn-lead-action-confirm",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 RCN-Contact-Policy-Correction",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()
        return response.status


def corrected_fields(execution: dict) -> dict:
    signals = saved(execution, "Build Signals")
    parsed = saved(execution, "Parse Score")
    body = signals.get("body") or {}
    features = signals.get("_features") or {}
    parsed_body = parsed.get("body") or {}
    if not patcher.phone_is_quarantined(body, features):
        raise RuntimeError(f"Execution {execution.get('id')} is not a phone quarantine")
    email_invalid = (
        features.get("email_mx_valid") is False
        or features.get("email_mailbox_valid") is False
        or features.get("email_disposable") is True
        or features.get("email_disposable_reoon") is True
    )
    both_invalid = email_invalid
    score = min(int(parsed_body.get("lead_score") or 100), 25 if both_invalid else 50)
    decision = "suppress" if both_invalid else "review"
    quality = "bad" if both_invalid else "questionable"
    reason = str(parsed_body.get("reason_short") or "").strip()
    suffix = (
        "[contact policy correction: phone missing/invalid + email invalid -> automatic spam]"
        if both_invalid
        else "[contact policy correction: phone missing/invalid -> quarantine]"
    )
    flags = list(parsed_body.get("risk_flags") or [])
    for flag in (["contact_both_invalid", "hard_override"] if both_invalid else ["phone_missing_or_invalid", "hard_override"]):
        if flag not in flags:
            flags.append(flag)
    return {
        "lead_order_id": str(body.get("lead_order_id") or ""),
        "lead_score": score,
        "lead_quality": quality,
        "decision": decision,
        "destination_validity": parsed_body.get("destination_validity"),
        "confidence": parsed_body.get("confidence"),
        "reason_short": f"{reason} {suffix}".strip(),
        "risk_flags": ", ".join(flags),
        "sales_note": parsed_body.get("sales_note"),
        "scorer_latency_ms": parsed_body.get("scorer_latency_ms"),
        "scorer_error": parsed_body.get("scorer_error"),
        "scored_at": parsed_body.get("scored_at"),
        "value_multiplier": parsed_body.get("value_multiplier"),
        "conversion_value_cad": parsed_body.get("conversion_value_cad"),
        "value_reason": parsed_body.get("value_reason"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("execution_ids", nargs="+")
    parser.add_argument("--prepare-retraction", action="store_true",
                        help="Restore upload evidence, clear prior action state, and submit bad")
    parser.add_argument("--finalize-audit", action="store_true",
                        help="Set the corrected review/suppress decision after queue verification")
    args = parser.parse_args()
    api = patcher.N8nApi(patcher.load_key())
    results = []
    for execution_id in args.execution_ids:
        execution = api.call("GET", f"/executions/{execution_id}?includeData=true")
        fields = corrected_fields(execution)
        token = str(saved(execution, "Generate Lead Action Token").get("lead_action_token") or "")
        if not fields["lead_order_id"] or len(token) < 40:
            raise RuntimeError(f"Execution {execution_id} lacks an order ID or signed action token")
        item = {
            "execution_id": str(execution_id),
            "lead_order_id": fields["lead_order_id"],
            "corrected_score": fields["lead_score"],
            "corrected_decision": fields["decision"],
            "applied": False,
        }
        if args.prepare_retraction:
            item["restore_execution_id"] = apply_scoring_update(api, {
                "lead_order_id": fields["lead_order_id"],
                "decision": "send_to_sales",
                "manual_action": "",
            })
            item["action_http_status"] = submit_bad(fields["lead_order_id"], token)
            if item["action_http_status"] != 200:
                raise RuntimeError(f"Action workflow returned HTTP {item['action_http_status']}")
            item["prepared"] = True
        elif args.finalize_audit:
            item["audit_update_execution_id"] = apply_scoring_update(api, fields)
            item["audit_finalized"] = True
        results.append(item)
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
