#!/usr/bin/env python3
"""Enforce RCN's contact matrix and restore Codex-primary scoring.

Policy:
* usable phone: score normally, even when email is invalid;
* missing/invalid phone: deterministic review quarantine, never upload/pace;
* missing/invalid phone plus invalid email: deterministic spam suppression;
* verifier outages remain fail-open when the phone has a valid local shape.

Run on the n8n VPS. The script backs up the workflow, patches non-trigger
nodes/connections only, rebuilds today's person-level pacing, and verifies the
published definition after PUT.
"""

from __future__ import annotations

import copy
import json

import patch_rcn_pacing_scorer as patcher


CONTACT_OLD_CODE = r"""  const phoneUsable = features.phone_valid_veriphone === true ||
    (features.phone_valid_veriphone !== false && features.phone_valid_shape === true);
  const emailUsable = features.email_mx_valid !== false &&
    features.email_mailbox_valid !== false &&
    features.email_disposable !== true &&
    features.email_disposable_reoon !== true;
  const contactUsable = phoneUsable || emailUsable;
"""

CONTACT_NEW_CODE = ""

CONTACT_PRELUDE = r"""// Deterministic contact policy. Veriphone=true is authoritative for a
// valid international number; an outage is fail-open only when shape is valid.
const phoneDigits = String(lead.phone || '').replace(/\D+/g, '');
const phoneMissing = !phoneDigits;
const phoneDefinitivelyInvalid = phoneMissing ||
  features.phone_fictional === true ||
  features.phone_repeating === true ||
  features.phone_valid_veriphone === false ||
  (features.phone_valid_veriphone !== true && features.phone_valid_shape !== true);
const phoneUsable = !phoneDefinitivelyInvalid;
const emailRaw = String(lead.email || '').trim();
const emailShapeValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailRaw);
const emailDefinitivelyInvalid = !emailShapeValid ||
  features.email_mx_valid === false ||
  features.email_mailbox_valid === false ||
  features.email_disposable === true ||
  features.email_disposable_reoon === true;
const emailUsable = !emailDefinitivelyInvalid;
const contactUsable = phoneUsable || emailUsable;

"""

OLD_CONTACT_CAPS = r"""  // ── Phone verification (Veriphone) — invalid number caps to review tier ──
  // Fail-open: only a definitive false caps; null/unchecked never penalises.
  if (features.phone_valid_veriphone === false && !emailUsable && score > 50) {
    overrides.push('phone invalid (Veriphone)');
    score = 50;
  }
  // ── Email verification — dead domain (DoH MX) or no mailbox (Reoon) ──
  if ((features.email_mx_valid === false || features.email_mailbox_valid === false) && !phoneUsable && score > 50) {
    overrides.push(features.email_mx_valid === false ? 'email domain has no MX' : 'email mailbox undeliverable');
    score = 50;
  }
"""

NEW_CONTACT_CAPS = r"""  // ── Contact matrix — final deterministic authority ──
  // An invalid/missing phone always quarantines the lead. A valid email cannot
  // rescue it. If the email is also definitively invalid, suppress as spam.
  if (phoneDefinitivelyInvalid && emailDefinitivelyInvalid) {
    overrides.push('phone missing/invalid + email invalid (automatic spam)');
    if (score > 25) score = 25;
  } else if (phoneDefinitivelyInvalid) {
    overrides.push(phoneMissing ? 'phone missing (automatic quarantine)' : 'phone invalid (automatic quarantine)');
    if (score > 50) score = 50;
  }
  // Email-only invalidity never caps a lead when the phone is usable. It remains
  // visible as a scorer/audit warning while the trip itself is scored normally.
"""

ERROR_CONTACT_OVERRIDE = r"""
// Scorer failure cannot bypass the contact matrix. The ordinary scorer-error
// outcome remains review, except the objectively both-invalid case is spam.
if (scorerError && phoneDefinitivelyInvalid) {
  if (emailDefinitivelyInvalid) {
    score = 25;
    decision = 'suppress';
    overrides.push('phone missing/invalid + email invalid (automatic spam)');
  } else {
    score = 50;
    decision = 'review';
    overrides.push(phoneMissing ? 'phone missing (automatic quarantine)' : 'phone invalid (automatic quarantine)');
  }
  parsed.reason_short = (parsed.reason_short || '') + ' [overrides: ' + overrides.join(' + ') + ']';
  parsed.risk_flags = (Array.isArray(parsed.risk_flags) ? parsed.risk_flags : []).concat(['hard_override']);
}

"""

OLD_PROMPT_CODEX = """- phone_valid_veriphone=false means the number is definitely invalid. That is a serious review signal, but do not suppress from phone alone.
- phone_valid_veriphone=null means verification was unavailable. Treat it as valid.
- email_mx_valid=false or email_mailbox_valid=false means the email may be unusable, but it is a warning rather than a reject if the phone is usable. Likewise, phone_valid_veriphone=false is a warning rather than a reject if email is usable.
- email_free_provider=true is neutral."""

OLD_PROMPT_OPENCODE = """- phone_valid_veriphone=false is a serious review signal, but do not suppress from phone alone.
- phone_valid_veriphone=null means verification was unavailable. Treat it as valid.
- email_mx_valid=false or email_mailbox_valid=false is a warning rather than an automatic reject if the phone is usable.
- email_free_provider=true is neutral."""

NEW_PROMPT = """- Missing phone, phone_valid_shape=false, or phone_valid_veriphone=false means automatic quarantine/review and must never be send_to_sales.
- If both phone and email are definitively invalid, classify as automatic spam/suppress.
- phone_valid_veriphone=null means verification was unavailable. Do not penalize a phone that still has phone_valid_shape=true.
- When the phone is usable, an invalid email is only a warning: score the trip normally and do not cap or suppress for email alone.
- A note such as \"do not phone\" does not rescue a missing/invalid number and does not penalize an otherwise valid number.
- email_free_provider=true is neutral."""


def patch_parse(workflow: dict) -> None:
    parse = patcher.node(workflow, "Parse Score")
    code = parse["parameters"]["jsCode"]
    if "phoneDefinitivelyInvalid" not in code:
        code = patcher.replace_once(code, CONTACT_OLD_CODE, CONTACT_NEW_CODE, "contact status definitions")
        code = patcher.replace_once(
            code, "if (scorerError) {\n", CONTACT_PRELUDE + "if (scorerError) {\n",
            "contact policy prelude",
        )
        code = patcher.replace_once(code, OLD_CONTACT_CAPS, NEW_CONTACT_CAPS, "contact hard caps")
        code = patcher.replace_once(
            code, "  const cleanBorderlineLead = contactUsable &&",
            "  const cleanBorderlineLead = phoneUsable &&",
            "clean borderline phone requirement",
        )
        code = patcher.replace_once(
            code, "const leadValue = computeLeadValue(lead, features, parsed, score, decision, overrides, destinationProfile);\n",
            ERROR_CONTACT_OVERRIDE + "const leadValue = computeLeadValue(lead, features, parsed, score, decision, overrides, destinationProfile);\n",
            "scorer-error contact override",
        )
    parse["parameters"]["jsCode"] = code


def patch_prompts(workflow: dict) -> None:
    codex = patcher.node(workflow, "Codex Score Lead")
    instructions = codex["parameters"]["scorerInstructions"]
    if NEW_PROMPT not in instructions:
        instructions = patcher.replace_once(
            instructions, OLD_PROMPT_CODEX, NEW_PROMPT, "Codex contact policy prompt"
        )
    codex["parameters"]["scorerInstructions"] = instructions

    builder = patcher.node(workflow, "Build OpenCode Go Score")
    code = builder["parameters"]["jsCode"]
    if NEW_PROMPT not in code:
        code = patcher.replace_once(
            code, OLD_PROMPT_OPENCODE, NEW_PROMPT, "OpenCode contact policy prompt"
        )
    code = code.replace("scorer_route:'opencode-go-primary'", "scorer_route:'opencode-go-fallback'")
    builder["parameters"]["jsCode"] = code


def patch_route(workflow: dict) -> None:
    c = workflow["connections"]
    c["Build Signals"] = {
        "main": [[{"node": "Codex Score Lead", "type": "main", "index": 0}]]
    }
    c["Codex Score Lead"] = {"main": [
        [{"node": "Parse Score", "type": "main", "index": 0}],
        [{"node": "Build OpenCode Go Score", "type": "main", "index": 0}],
    ]}
    c["OpenCode Go Score"] = {"main": [
        [{"node": "Normalize OpenCode Go Score", "type": "main", "index": 0}],
        [{"node": "Normalize Scorer Error", "type": "main", "index": 0}],
    ]}
    c["Normalize OpenCode Go Score"] = {"main": [
        [{"node": "Parse Score", "type": "main", "index": 0}],
        [{"node": "Normalize Scorer Error", "type": "main", "index": 0}],
    ]}
    c.pop("Prepare Codex Fallback", None)

    error_node = patcher.node(workflow, "Normalize Scorer Error")
    error_code = error_node["parameters"]["jsCode"]
    error_code = error_code.replace("OpenCode Go primary and Codex fallback", "Codex primary and OpenCode Go fallback")
    error_code = error_code.replace("OpenCode Go and Codex were unavailable", "Codex and OpenCode Go were unavailable")
    error_code = error_code.replace("fail-open:opencode-go-codex", "fail-open:codex-opencode-go")
    error_node["parameters"]["jsCode"] = error_code


def validate(workflow: dict) -> None:
    parse = patcher.node(workflow, "Parse Score")["parameters"]["jsCode"]
    if "phone missing/invalid + email invalid (automatic spam)" not in parse:
        raise RuntimeError("Both-invalid suppression is missing")
    if "phone invalid (automatic quarantine)" not in parse:
        raise RuntimeError("Invalid-phone quarantine is missing")
    if "const cleanBorderlineLead = phoneUsable &&" not in parse:
        raise RuntimeError("Invalid phone can still receive the low send threshold")
    if workflow["connections"]["Build Signals"]["main"][0][0]["node"] != "Codex Score Lead":
        raise RuntimeError("Codex is not the primary scorer")
    if workflow["connections"]["Codex Score Lead"]["main"][1][0]["node"] != "Build OpenCode Go Score":
        raise RuntimeError("OpenCode Go is not the Codex fallback")
    if patcher.node(workflow, "Webhook")["parameters"].get("path") != "rcn-form":
        raise RuntimeError("Webhook trigger changed unexpectedly")


def main() -> int:
    api = patcher.N8nApi(patcher.load_key())
    current = api.call("GET", f"/workflows/{patcher.WORKFLOW_ID}")
    before_version = current.get("versionId")
    run_stamp = patcher.stamp()
    before = patcher.BACKUP_DIR / f"rcn-before-contact-policy-{run_stamp}.json"
    after = patcher.BACKUP_DIR / f"rcn-after-contact-policy-{run_stamp}.json"
    patcher.write_json(before, current)

    updated = copy.deepcopy(current)
    patch_parse(updated)
    patch_prompts(updated)
    patch_route(updated)
    pacing = patcher.rebuild_today_people(api, updated)
    validate(updated)
    api.call("PUT", f"/workflows/{patcher.WORKFLOW_ID}", patcher.workflow_payload(updated))
    fresh = api.call("GET", f"/workflows/{patcher.WORKFLOW_ID}")
    validate(fresh)
    if not fresh.get("active") or fresh.get("versionId") != fresh.get("activeVersionId"):
        raise RuntimeError("Patched workflow is not the published active version")
    patcher.write_json(after, fresh)
    print(json.dumps({
        "workflow_id": patcher.WORKFLOW_ID,
        "active": fresh.get("active"),
        "before_version": before_version,
        "after_version": fresh.get("versionId"),
        "before_backup": str(before),
        "after_backup": str(after),
        "scorer_route": "Codex -> OpenCode Go -> deterministic fallback",
        "pacing": {
            "date": pacing["date"],
            "unique_people": pacing["uniqueCount"],
            "campaigns": pacing["campaigns"],
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
