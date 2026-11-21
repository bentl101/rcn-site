#!/usr/bin/env python3
"""Publish optional-trip-detail scoring on the two existing intake workflows."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile

from patch_rcn_pacing_scorer import N8nApi, load_key, node, replace_once, workflow_payload


WORKFLOWS = {
    "rcn": ("zYw4HtTy1OTH7jUy", "Codex Score Lead", "Build Anthropic Score", "Parse Score"),
    "dct": ("PmntlqBanV9ZMy3O", "Codex Score DCT Lead", "Build DCT Fallback Request", "Parse DCT Score"),
}
POLICY = (
    "\nTrip details and last name are optional. Blank answers are unknown and are "
    "never evidence of spam or invalid information. Use any trip intent in the "
    "notes when destination is blank. If neither destination nor notes were "
    "provided, classify the destination as plausible and recommend follow-up "
    "for a contactable enquiry. Score explicit off-product or suspicious answers "
    "under the existing rules."
)


def patch(workflow, site):
    _, primary_name, fallback_name, parser_name = WORKFLOWS[site]
    primary = node(workflow, primary_name)["parameters"]
    fallback = node(workflow, fallback_name)["parameters"]
    parser = node(workflow, parser_name)["parameters"]
    prompt = primary["scorerInstructions"]
    if POLICY in prompt:
        raise ValueError("Optional trip policy is already present")
    fallback["jsCode"] = replace_once(
        fallback["jsCode"], json.dumps(prompt), json.dumps(prompt + POLICY), fallback_name
    )
    primary["scorerInstructions"] += POLICY

    if site == "rcn":
        anchor = "  const destinationIsPlausible ="
        addition = """  if (!String(lead.destination || '').trim() && !String(lead.additional_info || '').trim() &&
      phoneUsable && emailUsable && !features.honeypot_filled && !features.name_repeated) {
    score = 50;
    parsed.destination_validity = 'plausible';
    parsed.reason_short = 'No itinerary or notes provided. Follow up to confirm cruise preferences.';
  }
"""
    else:
        anchor = "const flags ="
        addition = """if (!error && !String(lead.destination || '').trim() && !String(lead.notes || lead.additional_info || '').trim() &&
    f.phone_valid_shape && f.email_valid_shape && !f.honeypot_filled && !f.name_repeated) {
  score = 50;
  p.destination_validity = 'plausible';
  p.reason_short = 'No destination or notes provided. Follow up to confirm tour preferences.';
}
"""
    parser["jsCode"] = replace_once(parser["jsCode"], anchor, addition + anchor, parser_name)
    return parser["jsCode"]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("site", choices=WORKFLOWS)
    cli.add_argument("expected_version")
    cli.add_argument("--apply", action="store_true")
    args = cli.parse_args()
    workflow_id, _, fallback, parser = WORKFLOWS[args.site]
    api = N8nApi(load_key())
    path = "/workflows/" + workflow_id
    before = api.call("GET", path)
    if not before["active"] or before["versionId"] != args.expected_version:
        raise RuntimeError("Active workflow version changed. Inspect the current scoring nodes.")
    candidate = workflow_payload(before)
    patch(candidate, args.site)
    for name in (fallback, parser):
        js = node(candidate, name)["parameters"]["jsCode"]
        subprocess.run(["node", "-e", "new Function(" + json.dumps(js) + ")"], check=True)
    if not args.apply:
        print(f"{args.site}: candidate parsed successfully")
        return

    backup_root = Path("/home/ben/infra/n8n/workflow-backups")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = Path(tempfile.mkdtemp(prefix=f"{args.site}-optional-trip-{stamp}-", dir=backup_root))
    (backup / "before.json").write_text(json.dumps(before))
    current = api.call("GET", path)
    if current["versionId"] != before["versionId"]:
        raise RuntimeError("Concurrent workflow edit")
    if "staticData" in current:
        candidate["staticData"] = current["staticData"]
    api.call("PUT", path, candidate)
    after = api.call("GET", path)
    if after.get("activeVersionId") != after["versionId"]:
        api.call("POST", path + "/activate")
        after = api.call("GET", path)
    (backup / "after.json").write_text(json.dumps(after))
    if not after["active"] or after.get("activeVersionId") != after["versionId"]:
        raise RuntimeError("Scorer update was saved but not published")
    if any(after[key] != candidate[key] for key in ("nodes", "connections")):
        raise RuntimeError("Scorer update differs from proposed nodes or connections")
    print(f"{args.site}: verified active {after['versionId']}; backup {backup}")


if __name__ == "__main__":
    main()
