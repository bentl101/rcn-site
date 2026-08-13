#!/usr/bin/env python3
"""Apply post-cutover hardening to the live RCN n8n workflows.

This script is intentionally idempotent. It backs up both workflows, adds
email/phone alias dedupe and shared Ads campaign metadata to the lead workflow,
adds a durable manual-upload ledger to the action workflow, preserves static
data, and verifies that active and saved versions match after each PUT.
"""

from __future__ import annotations

import copy
import json
import pathlib
import urllib.parse
import urllib.request

import patch_rcn_pacing_scorer as patcher


ACTION_WORKFLOW_ID = "LpJaof03qyAbSGip"
ADS_CUSTOMER_ID = "5306933986"
ADS_API_VERSION = "v24"
CHANNEL_LABELS = {
    "SEARCH": "Search", "PERFORMANCE_MAX": "P-Max", "DEMAND_GEN": "Demand Gen",
    "DISCOVERY": "Demand Gen", "DISPLAY": "Display", "VIDEO": "Video",
    "SHOPPING": "Shopping", "MULTI_CHANNEL": "Multi-channel", "LOCAL": "Local",
    "APP": "App", "SMART": "Smart", "HOTEL": "Hotel", "TRAVEL": "Travel",
    "LOCAL_SERVICES": "Local Services",
}


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one {label} anchor, found {count}")
    return text.replace(old, new, 1)


def load_secrets() -> dict[str, str]:
    values = {}
    for line in pathlib.Path("/home/ben/.secrets").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"').strip("'")
    return values


def fetch_campaign_metadata() -> dict[str, dict]:
    secrets_map = load_secrets()
    token_request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=urllib.parse.urlencode({
            "client_id": secrets_map["GOOGLE_ADS_CLIENT_ID"],
            "client_secret": secrets_map["GOOGLE_ADS_CLIENT_SECRET"],
            "refresh_token": secrets_map["GOOGLE_ADS_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        }).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(token_request, timeout=30) as response:
        access_token = json.load(response)["access_token"]
    endpoint = (
        f"https://googleads.googleapis.com/{ADS_API_VERSION}/customers/"
        f"{ADS_CUSTOMER_ID}/googleAds:search"
    )
    body = {
        "query": "SELECT campaign.id, campaign.name, campaign.advertising_channel_type FROM campaign"
    }
    rows = []
    while True:
        request = urllib.request.Request(
            endpoint, data=json.dumps(body).encode(), method="POST",
            headers={
                "Authorization": f"Bearer {access_token}",
                "developer-token": secrets_map["GOOGLE_ADS_DEVELOPER_TOKEN"],
                "login-customer-id": secrets_map.get("GOOGLE_ADS_MANAGER_ID", "3814278874"),
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 RCN-Workflow-Hardening",
            },
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            page = json.load(response)
        rows.extend(page.get("results", []))
        token = page.get("nextPageToken")
        if not token:
            break
        body["pageToken"] = token
    refreshed = patcher.dt.datetime.now(patcher.dt.timezone.utc).isoformat()
    metadata = {}
    for row in rows:
        campaign = row.get("campaign", {})
        campaign_id = str(campaign.get("id") or "")
        if not campaign_id:
            continue
        channel = str(campaign.get("advertisingChannelType") or "").upper()
        label = CHANNEL_LABELS.get(channel) or channel.replace("_", " ").title() or "Paid"
        metadata[campaign_id] = {
            "label": label,
            "name": str(campaign.get("name") or ""),
            "channel": channel,
            "refreshedAt": refreshed,
        }
    if not metadata:
        raise RuntimeError("Google Ads campaign metadata query returned no campaigns")
    return metadata


def seed_campaign_metadata(workflow: dict, metadata: dict[str, dict]) -> None:
    global_data = workflow.setdefault("staticData", {}).setdefault("global", {})
    global_data["rcnCampaignMetadata"] = copy.deepcopy(metadata)
    buckets = global_data.get("rcnDailyPacingCounter", {}).get("campaigns", {})
    for key, bucket in buckets.items():
        campaign_id = str(bucket.get("campaignId") or "")
        resolved = metadata.get(campaign_id)
        if resolved:
            bucket["label"] = resolved["label"]
            bucket["name"] = resolved["name"]


def rebuild_current_pacing(api: patcher.N8nApi, workflow: dict) -> None:
    """Refresh current-day people/aliases after re-fetching saved executions."""
    patcher.rebuild_today_people(api, workflow)


def patch_main(workflow: dict) -> dict:
    result = copy.deepcopy(workflow)
    snapshot = patcher.node(result, "Build Lead Pacing Snapshot")
    snapshot["parameters"]["jsCode"] = patcher.PACING_JS

    assign = patcher.node(result, "Assign Daily Lead Number")
    code = assign["parameters"]["jsCode"]
    old_identity = r"""const email = String(body.email || '').trim().toLowerCase();
const phone = String(body.phone || '').replace(/\D+/g, '');
const key = email ? `e:${email}` : (phone ? `p:${phone}` : `o:${body.lead_order_id || Date.now()}`);

store.rcnDailyLeadCounter.count += 1;
if (!store.rcnDailyLeadCounter.seen[key]) {
  store.rcnDailyLeadCounter.uniqueCount += 1;
  store.rcnDailyLeadCounter.seen[key] = store.rcnDailyLeadCounter.uniqueCount;
}

body.daily_lead_number = store.rcnDailyLeadCounter.count;
body.daily_unique_lead_number = store.rcnDailyLeadCounter.seen[key];
"""
    new_identity = r"""store.rcnDailyLeadCounter.seenAliases ||= {};
const email = String(body.email || '').trim().toLowerCase();
const phone = String(body.phone || '').replace(/\D+/g, '');
const aliases = [email ? `e:${email}` : '', phone ? `p:${phone}` : ''].filter(Boolean);
const matchedAlias = aliases.find((alias) => store.rcnDailyLeadCounter.seenAliases[alias] || store.rcnDailyLeadCounter.seen[alias]);
let dailyUniqueNumber = matchedAlias ? (store.rcnDailyLeadCounter.seenAliases[matchedAlias] || store.rcnDailyLeadCounter.seen[matchedAlias]) : 0;
store.rcnDailyLeadCounter.count += 1;
if (!dailyUniqueNumber) {
  store.rcnDailyLeadCounter.uniqueCount += 1;
  dailyUniqueNumber = store.rcnDailyLeadCounter.uniqueCount;
}
for (const alias of aliases) store.rcnDailyLeadCounter.seenAliases[alias] = dailyUniqueNumber;
const key = aliases[0] || `o:${body.lead_order_id || Date.now()}`;
store.rcnDailyLeadCounter.seen[key] = dailyUniqueNumber;
body.daily_lead_number = store.rcnDailyLeadCounter.count;
body.daily_unique_lead_number = dailyUniqueNumber;
"""
    if "rcnDailyLeadCounter.seenAliases" not in code:
        code = replace_once(code, old_identity, new_identity, "daily identity aliasing")
    if "store.rcnCampaignMetadata?.[campaignId]" not in code:
        code = replace_once(
            code,
            "const campaign = campaigns[campaignId];",
            "const cachedCampaign = /^\\d+$/.test(campaignId) ? "
            "(store.rcnCampaignMetadata?.[campaignId] || null) : null;\n"
            "const campaign = cachedCampaign || campaigns[campaignId];",
            "campaign metadata cache",
        )
    assign["parameters"]["jsCode"] = code

    pacing_email = patcher.node(result, "Build Pacing Email")
    code = pacing_email["parameters"]["jsCode"]
    start_marker = "const campaignRow = rows.find((row) => String(row.campaign?.id || '') === String(p.campaignId || ''));"
    end_marker = "\n\nconst cash"
    new = r"""const campaignRow = rows.find((row) => String(row.campaign?.id || '') === String(p.campaignId || ''));
const store = $getWorkflowStaticData('global');
store.rcnCampaignMetadata ||= {};
const labelForChannel = (value, fallback) => {
  const channel = String(value || '').toUpperCase();
  return channelLabels[channel]
    || channel.toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    || fallback;
};
for (const row of rows) {
  const id = String(row.campaign?.id || '');
  if (!id) continue;
  store.rcnCampaignMetadata[id] = {
    label: labelForChannel(row.campaign?.advertisingChannelType, 'Paid'),
    name: String(row.campaign?.name || ''),
    channel: String(row.campaign?.advertisingChannelType || ''),
    refreshedAt: new Date().toISOString(),
  };
  const bucket = store.rcnDailyPacingCounter?.campaigns?.[`id:${id}`];
  if (bucket) {
    bucket.label = store.rcnCampaignMetadata[id].label;
    bucket.name = store.rcnCampaignMetadata[id].name;
  }
}
if (campaignRow) {
  const channel = String(campaignRow.campaign?.advertisingChannelType || '').toUpperCase();
  p.label = labelForChannel(channel, p.label);
  p.campaignName = String(campaignRow.campaign?.name || '');
  const bucket = store.rcnDailyPacingCounter?.campaigns?.[p.campaignKey];
  if (bucket) {
    bucket.label = p.label;
    bucket.name = p.campaignName;
  }
}
"""
    if "store.rcnCampaignMetadata ||= {}" not in code:
        if code.count(start_marker) != 1 or code.count(end_marker) != 1:
            raise RuntimeError("Could not isolate the pacing metadata block")
        start = code.index(start_marker)
        end = code.index(end_marker, start)
        code = code[:start] + new + code[end:]
    pacing_email["parameters"]["jsCode"] = code
    return result


def patch_action(workflow: dict) -> dict:
    result = copy.deepcopy(workflow)
    parse = patcher.node(result, "Parse Manual Upload Result")
    code = parse["parameters"]["jsCode"]
    if "rcnManualUploadLedger" not in code:
        old = "return [{json:{...event, manual_action:accepted?'good_uploaded':'good_upload_failed', processed_at_utc:new Date().toISOString(), result:accepted?'uploaded':'upload_failed', ads_processed_at_utc:new Date().toISOString(), ads_result:accepted?'accepted':'failed', detail}}];"
        new = """const output = {...event, manual_action:accepted?'good_uploaded':'good_upload_failed', processed_at_utc:new Date().toISOString(), result:accepted?'uploaded':'upload_failed', ads_processed_at_utc:new Date().toISOString(), ads_result:accepted?'accepted':'failed', detail};
let scoring = {};
try { scoring = $('Read Scoring for Event').first().json || {}; } catch (_) {}
const store = $getWorkflowStaticData('global');
store.rcnManualUploadLedger ||= {};
const orderId = String(output.lead_order_id || '');
if (orderId) {
  store.rcnManualUploadLedger[orderId] = {
    lead_order_id: orderId,
    submitted_at: String(output.submitted_at || ''),
    email: String(scoring.email || ''),
    phone: String(scoring.phone || ''),
    manual_action: output.manual_action,
    ads_processed_at_utc: output.ads_processed_at_utc,
  };
}
return [{json:output}];"""
        code = replace_once(code, old, new, "manual upload ledger")
    parse["parameters"]["jsCode"] = code
    return result


def validate_main(workflow: dict) -> None:
    pacing = patcher.node(workflow, "Build Lead Pacing Snapshot")["parameters"]["jsCode"]
    assign = patcher.node(workflow, "Assign Daily Lead Number")["parameters"]["jsCode"]
    email = patcher.node(workflow, "Build Pacing Email")["parameters"]["jsCode"]
    for marker in ("seenAliases", "freshPerson ?", "^\\d+$"):
        if marker not in pacing:
            raise RuntimeError(f"Main workflow missing pacing marker {marker!r}")
    if "store.rcnCampaignMetadata?.[campaignId]" not in assign:
        raise RuntimeError("Main workflow does not use shared campaign metadata")
    if "rcnDailyLeadCounter.seenAliases" not in assign:
        raise RuntimeError("Main workflow daily lead counter does not use aliases")
    if "store.rcnCampaignMetadata ||= {}" not in email:
        raise RuntimeError("Main workflow does not populate shared campaign metadata")


def validate_action(workflow: dict) -> None:
    code = patcher.node(workflow, "Parse Manual Upload Result")["parameters"]["jsCode"]
    if "rcnManualUploadLedger" not in code:
        raise RuntimeError("Action workflow is missing the manual upload ledger")


def put_verified(api: patcher.N8nApi, workflow_id: str, patched: dict, validator) -> dict:
    validator(patched)
    api.call("PUT", f"/workflows/{workflow_id}", patcher.workflow_payload(patched))
    fresh = api.call("GET", f"/workflows/{workflow_id}")
    validator(fresh)
    if not fresh.get("active") or fresh.get("versionId") != fresh.get("activeVersionId"):
        raise RuntimeError(f"Workflow {workflow_id} is not active on its saved version")
    return fresh


def main() -> int:
    api = patcher.N8nApi(patcher.load_key())
    stamp = patcher.stamp()
    campaign_metadata = fetch_campaign_metadata()
    main_live = api.call("GET", f"/workflows/{patcher.WORKFLOW_ID}")
    action_live = api.call("GET", f"/workflows/{ACTION_WORKFLOW_ID}")
    patcher.write_json(
        patcher.BACKUP_DIR / f"rcn-before-final-hardening-{stamp}.json", main_live
    )
    patcher.write_json(
        patcher.BACKUP_DIR / f"rcn-actions-before-final-hardening-{stamp}.json", action_live
    )
    # Re-fetch immediately before each PUT to avoid writing an older staticData
    # snapshot if a lead/action arrived while candidates were being inspected.
    main_patched = patch_main(api.call("GET", f"/workflows/{patcher.WORKFLOW_ID}"))
    rebuild_current_pacing(api, main_patched)
    seed_campaign_metadata(main_patched, campaign_metadata)
    main_fresh = put_verified(api, patcher.WORKFLOW_ID, main_patched, validate_main)
    action_patched = patch_action(api.call("GET", f"/workflows/{ACTION_WORKFLOW_ID}"))
    action_fresh = put_verified(api, ACTION_WORKFLOW_ID, action_patched, validate_action)
    patcher.write_json(
        patcher.BACKUP_DIR / f"rcn-after-final-hardening-{stamp}.json", main_fresh
    )
    patcher.write_json(
        patcher.BACKUP_DIR / f"rcn-actions-after-final-hardening-{stamp}.json", action_fresh
    )
    print(json.dumps({
        "main": {"id": patcher.WORKFLOW_ID, "versionId": main_fresh.get("versionId")},
        "actions": {"id": ACTION_WORKFLOW_ID, "versionId": action_fresh.get("versionId")},
        "campaigns_cached": len(campaign_metadata),
        "backup_stamp": stamp,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
