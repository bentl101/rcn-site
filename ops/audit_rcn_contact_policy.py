#!/usr/bin/env python3
"""Audit recent RCN executions against the deterministic contact policy.

The output deliberately omits raw phone numbers, email addresses, IPs, click
IDs, and lead-action tokens. Run on the n8n VPS next to
``patch_rcn_pacing_scorer.py``.
"""

from __future__ import annotations

import argparse
import json

import patch_rcn_pacing_scorer as patcher


def saved(run_data: dict, name: str) -> dict:
    return patcher.execution_node(run_data, name) or {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    api = patcher.N8nApi(patcher.load_key())
    rows = api.call(
        "GET", f"/executions?workflowId={patcher.WORKFLOW_ID}&limit={args.limit}"
    ).get("data", [])
    findings = []
    for row in rows:
        execution = api.call("GET", f"/executions/{row['id']}?includeData=true")
        run_data = execution.get("data", {}).get("resultData", {}).get("runData", {})
        signals = saved(run_data, "Build Signals")
        parsed = saved(run_data, "Parse Score")
        if not signals or not parsed:
            continue
        body = signals.get("body") or {}
        features = signals.get("_features") or {}
        parsed_body = parsed.get("body") or {}
        digits = "".join(ch for ch in str(body.get("phone") or "") if ch.isdigit())
        phone_missing = not digits
        phone_invalid = (
            phone_missing
            or features.get("phone_valid_shape") is False
            or features.get("phone_valid_veriphone") is False
            or features.get("phone_fictional") is True
            or features.get("phone_repeating") is True
        )
        email_invalid = (
            features.get("email_mx_valid") is False
            or features.get("email_mailbox_valid") is False
            or features.get("email_disposable") is True
            or features.get("email_disposable_reoon") is True
        )
        note = str(body.get("additional_info") or "")
        no_phone_note = any(
            phrase in note.lower()
            for phrase in ("do not phone", "don't phone", "dont phone", "no phone", "email only")
        )
        uploaded = bool(saved(run_data, "Upload Click Conversion"))
        if not (phone_invalid or email_invalid or no_phone_note):
            continue
        findings.append({
            "execution_id": str(row["id"]),
            "submitted_at": body.get("submitted_at"),
            "lead_order_id": body.get("lead_order_id"),
            "name": " ".join(
                value for value in (
                    str(body.get("first_name") or "").strip(),
                    str(body.get("last_name") or "").strip(),
                ) if value
            ),
            "phone_missing": phone_missing,
            "phone_shape": features.get("phone_valid_shape"),
            "phone_veriphone": features.get("phone_valid_veriphone"),
            "email_mx": features.get("email_mx_valid"),
            "email_mailbox": features.get("email_mailbox_valid"),
            "no_phone_note": no_phone_note,
            "score": parsed_body.get("lead_score"),
            "decision": parsed_body.get("decision"),
            "model": parsed_body.get("scorer_model"),
            "upload_node_ran": uploaded,
            "pacing_node_ran": bool(saved(run_data, "Build Lead Pacing Snapshot")),
        })
    print(json.dumps(findings, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
