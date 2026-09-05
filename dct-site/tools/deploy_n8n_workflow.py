#!/usr/bin/env python3
"""Create or update the production DCT lead and Google Ads workflow on n8n.

The Google Ads conversion action IDs are public account metadata and are
provided at deployment time. OAuth credentials and the developer token remain
in the n8n container environment; this script never reads or prints them.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import urllib.request

BASE = "http://localhost:5678/api/v1"
NAME = "DCT Form Handler"
CUSTOMER_ID = "3639225242"
LOGIN_CUSTOMER_ID = "3814278874"
SMTP = {"smtp": {"id": "upVw1vzTxegbXV9E", "name": "Google Workspace SMTP"}}
BACKUP_DIR = pathlib.Path("/home/ben/infra/n8n/backups")


def key() -> str:
    for line in pathlib.Path("/home/ben/.secrets").read_text().splitlines():
        if line.startswith("N8N_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("N8N_API_KEY not found")


def api(method: str, path: str, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"X-N8N-API-KEY": key()}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = response.read()
    return json.loads(raw) if raw else {}


verify_code = r"""
const headers = $json.headers || {};
const supplied = String(headers['x-dct-token'] || '');
const expected = String($env.DCT_N8N_TOKEN || '');
if (!expected || !supplied || supplied !== expected) throw new Error('Unauthorized DCT webhook');
return $input.all();
"""


format_code = r"""
const lead = $json.body || {};
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const row = (label, value) => '<tr><th style="text-align:left;padding:7px 10px;background:#f3eef6;border-bottom:1px solid #ddd">' + esc(label) + '</th><td style="padding:7px 10px;border-bottom:1px solid #ddd">' + (esc(value) || '—') + '</td></tr>';
const isQa = String(lead.qa_test || '') === '1';
const name = String((lead.first_name || '') + ' ' + (lead.last_name || '')).trim();
const subject = (isQa ? '[TEST] ' : '') + 'New DCT lead - ' + (name || 'Website enquiry');
const details = [
  ['Lead Order ID', lead.lead_order_id], ['Operator', lead.operator || 'Help me compare'],
  ['Name', name], ['Email', lead.email], ['Phone', lead.phone],
  ['Destination', lead.destination], ['Departure city', lead.departure_city],
  ['Travel date', lead.travel_date], ['Duration', lead.duration], ['Guests', lead.guests],
  ['Budget', lead.budget], ['Pace', lead.pace], ['Notes', lead.notes],
  ['Contact preference', lead.contact_preference], ['Source page', lead.source_page],
  ['UTM source', lead.utm_source], ['UTM medium', lead.utm_medium],
  ['UTM campaign', lead.utm_campaign], ['UTM ID', lead.utm_id],
  ['UTM term', lead.utm_term], ['UTM content', lead.utm_content],
  ['Match type', lead.matchtype], ['Ad device', lead.gad_device], ['Network', lead.network],
  ['Ad group ID', lead.adgroupid], ['Target ID', lead.targetid],
  ['Physical location ID', lead.loc_physical], ['Interest location ID', lead.loc_interest],
  ['GCLID', lead.gclid], ['GBRAID', lead.gbraid], ['WBRAID', lead.wbraid],
  ['Click ID type', lead.click_id_type], ['Click ID', lead.click_id],
  ['Landing page', lead.landing_page], ['Referrer', lead.referrer],
  ['Device', lead.device_type], ['Browser language', lead.browser_language],
  ['Time on page', lead.time_on_page], ['Submitted at', lead.submitted_at]
];
const html = '<div style="font-family:Arial,sans-serif;color:#24142f;max-width:760px"><h2 style="color:#5b247a">' + esc(subject) + '</h2><table style="border-collapse:collapse;width:100%">' + details.map((item) => row(item[0], item[1])).join('') + '</table></div>';
return [{json: {...lead, is_qa: isQa, email_subject: subject, email_html: html}}];
"""


def build_ads_code(gclid_action_id: str, braid_action_id: str) -> str:
    return rf"""
const lead = $json;
const isQa = Boolean(lead.is_qa);
const validateOnly = isQa && String(lead.ads_validate_only || '') === '1';
if (isQa && !validateOnly) return [];

const genericType = String(lead.click_id_type || '').toLowerCase();
const genericId = String(lead.click_id || '').trim();
let gclid = String(lead.gclid || (genericType === 'gclid' ? genericId : '')).trim();
let gbraid = String(lead.gbraid || (genericType === 'gbraid' ? genericId : '')).trim();
let wbraid = String(lead.wbraid || (genericType === 'wbraid' ? genericId : '')).trim();
if (!gclid && !gbraid && !wbraid) return [];

// Google forbids GBRAID and WBRAID together. Prefer the type that the browser
// identified explicitly; otherwise GBRAID wins deterministically.
if (gbraid && wbraid) {{
  if (genericType === 'wbraid') gbraid = '';
  else wbraid = '';
}}
const braidType = gbraid ? 'gbraid' : (wbraid ? 'wbraid' : '');
const braidValue = gbraid || wbraid;
const actionId = braidValue ? '{braid_action_id}' : '{gclid_action_id}';

const parsed = new Date(String(lead.submitted_at || ''));
const when = Number.isNaN(parsed.getTime()) ? new Date() : parsed;
const iso = when.toISOString();
const conversionDateTime = iso.slice(0, 10) + ' ' + iso.slice(11, 19) + '+00:00';
const conversion = {{
  conversionAction: 'customers/{CUSTOMER_ID}/conversionActions/' + actionId,
  conversionDateTime,
  conversionValue: 50,
  currencyCode: 'CAD',
  orderId: String(lead.lead_order_id || '')
}};
if (gclid) conversion.gclid = gclid;
if (braidType) conversion[braidType] = braidValue;

// Enhanced-conversion identifiers are deliberately gated. The PHP handler
// does not set ads_ecl_allowed until DCT approves the disclosure and Google
// Customer Data Terms; click-ID uploads work without it.
if (String(lead.ads_ecl_allowed || '') === '1') {{
  const identifiers = [];
  if (lead.hashed_email) identifiers.push({{hashedEmail: String(lead.hashed_email)}});
  if (lead.hashed_phone) identifiers.push({{hashedPhoneNumber: String(lead.hashed_phone)}});
  if (identifiers.length) conversion.userIdentifiers = identifiers;
}}

return [{{json: {{
  ...lead,
  ads_route: braidValue ? 'braid' : 'gclid',
  ads_action_id: actionId,
  ads_validate_only: validateOnly,
  ads_conversion_datetime: conversionDateTime,
  google_ads_request: {{
    conversions: [conversion],
    partialFailure: true,
    validateOnly
  }}
}}}}];
"""


parse_ads_code = r"""
const request = $('Build Ads Upload').first().json;
const response = $json || {};
const partial = response.partialFailureError || response.partial_failure_error || null;
const rpc = response.error || null;
const nodeError = response.errorMessage || response.message || null;
const failure = partial || rpc || nodeError;
const results = Array.isArray(response.results) ? response.results : [];
const accepted = !failure && (request.ads_validate_only || results.length > 0);
const errorText = failure
  ? (typeof failure === 'string' ? failure : JSON.stringify(failure))
  : '';
return [{json: {
  ...request,
  ads_upload_accepted: accepted,
  ads_upload_error: errorText,
  ads_results_returned: results.length,
  ads_raw_response: response
}}];
"""


alert_code = r"""
const item = $json;
if (item.ads_upload_accepted) return [];
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const label = item.ads_validate_only ? 'DCT Google Ads validation rejected' : 'DCT Google Ads upload failed';
const subject = (item.ads_validate_only ? '[TEST] ' : '[ACTION REQUIRED] ') + label + ' - ' + String(item.lead_order_id || 'unknown order');
const html = '<div style="font-family:Arial,sans-serif"><h2>' + esc(label) + '</h2><p><strong>Order ID:</strong> ' + esc(item.lead_order_id) + '</p><p><strong>Route:</strong> ' + esc(item.ads_route) + '</p><p><strong>Action ID:</strong> ' + esc(item.ads_action_id) + '</p><p><strong>Error:</strong></p><pre style="white-space:pre-wrap">' + esc(item.ads_upload_error || 'No result returned') + '</pre></div>';
return [{json: {...item, ads_alert_subject: subject, ads_alert_html: html}}];
"""


def workflow(gclid_action_id: str, braid_action_id: str) -> dict:
    nodes = [
        {
            "parameters": {"httpMethod": "POST", "path": "dct-form", "responseMode": "onReceived", "options": {}},
            "id": "dct-webhook", "name": "DCT Webhook", "type": "n8n-nodes-base.webhook",
            "typeVersion": 2, "position": [-700, 0], "webhookId": "dct-form-webhook",
        },
        {
            "parameters": {"language": "javaScript", "jsCode": verify_code.strip() + "\n"},
            "id": "verify-token", "name": "Verify Token", "type": "n8n-nodes-base.code",
            "typeVersion": 2, "position": [-480, 0],
        },
        {
            "parameters": {"language": "javaScript", "jsCode": format_code.strip() + "\n"},
            "id": "format-email", "name": "Format Lead Email", "type": "n8n-nodes-base.code",
            "typeVersion": 2, "position": [-250, 0],
        },
        {
            "parameters": {
                "fromEmail": "ben@copperchunk.com",
                "toEmail": "={{ $json.is_qa ? 'btl101@gmail.com' : 'sales@discountcoachtours.ca, btl101@gmail.com' }}",
                "subject": "={{ $json.email_subject }}", "emailFormat": "html",
                "html": "={{ $json.email_html }}", "options": {"replyTo": "={{ $json.email }}"},
            },
            "id": "send-email", "name": "Send Email Notification", "type": "n8n-nodes-base.emailSend",
            "typeVersion": 2.1, "position": [20, -180], "credentials": SMTP,
            "onError": "continueRegularOutput",
        },
        {
            "parameters": {"language": "javaScript", "jsCode": build_ads_code(gclid_action_id, braid_action_id).strip() + "\n"},
            "id": "build-ads-upload", "name": "Build Ads Upload", "type": "n8n-nodes-base.code",
            "typeVersion": 2, "position": [20, 80],
        },
        {
            "parameters": {
                "method": "POST", "url": "https://oauth2.googleapis.com/token",
                "authentication": "none", "sendBody": True, "contentType": "form-urlencoded",
                "specifyBody": "keypair",
                "bodyParameters": {"parameters": [
                    {"name": "client_id", "value": "={{ $env.GOOGLE_ADS_CLIENT_ID }}"},
                    {"name": "client_secret", "value": "={{ $env.GOOGLE_ADS_CLIENT_SECRET }}"},
                    {"name": "refresh_token", "value": "={{ $env.GOOGLE_ADS_REFRESH_TOKEN }}"},
                    {"name": "grant_type", "value": "refresh_token"},
                ]},
                "options": {"timeout": 15000},
            },
            "id": "get-google-token", "name": "Get Google OAuth Token",
            "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
            "position": [260, 80], "onError": "continueRegularOutput",
        },
        {
            "parameters": {
                "method": "POST",
                "url": f"https://googleads.googleapis.com/v25/customers/{CUSTOMER_ID}:uploadClickConversions",
                "authentication": "none", "sendHeaders": True,
                "headerParameters": {"parameters": [
                    {"name": "Authorization", "value": "={{ 'Bearer ' + $json.access_token }}"},
                    {"name": "developer-token", "value": "={{ $env.GOOGLE_ADS_DEVELOPER_TOKEN }}"},
                    {"name": "login-customer-id", "value": LOGIN_CUSTOMER_ID},
                    {"name": "Content-Type", "value": "application/json"},
                ]},
                "sendBody": True, "specifyBody": "json",
                "jsonBody": "={{ $('Build Ads Upload').first().json.google_ads_request }}",
                "options": {"timeout": 15000, "response": {"response": {"neverError": True}}},
            },
            "id": "upload-click-conversion", "name": "Upload Click Conversion",
            "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
            "position": [500, 80], "onError": "continueRegularOutput",
        },
        {
            "parameters": {"language": "javaScript", "jsCode": parse_ads_code.strip() + "\n"},
            "id": "parse-ads-upload", "name": "Parse Ads Upload", "type": "n8n-nodes-base.code",
            "typeVersion": 2, "position": [740, 80], "onError": "continueRegularOutput",
        },
        {
            "parameters": {"language": "javaScript", "jsCode": alert_code.strip() + "\n"},
            "id": "build-ads-alert", "name": "Build Ads Failure Alert", "type": "n8n-nodes-base.code",
            "typeVersion": 2, "position": [980, 80],
        },
        {
            "parameters": {
                "fromEmail": "ben@copperchunk.com", "toEmail": "btl101@gmail.com",
                "subject": "={{ $json.ads_alert_subject }}", "emailFormat": "html",
                "html": "={{ $json.ads_alert_html }}", "options": {},
            },
            "id": "send-ads-alert", "name": "Send Ads Failure Alert",
            "type": "n8n-nodes-base.emailSend", "typeVersion": 2.1,
            "position": [1220, 80], "credentials": SMTP, "onError": "continueRegularOutput",
        },
    ]
    connections = {
        "DCT Webhook": {"main": [[{"node": "Verify Token", "type": "main", "index": 0}]]},
        "Verify Token": {"main": [[{"node": "Format Lead Email", "type": "main", "index": 0}]]},
        "Format Lead Email": {"main": [[
            {"node": "Send Email Notification", "type": "main", "index": 0},
            {"node": "Build Ads Upload", "type": "main", "index": 0},
        ]]},
        "Build Ads Upload": {"main": [[{"node": "Get Google OAuth Token", "type": "main", "index": 0}]]},
        "Get Google OAuth Token": {"main": [[{"node": "Upload Click Conversion", "type": "main", "index": 0}]]},
        "Upload Click Conversion": {"main": [[{"node": "Parse Ads Upload", "type": "main", "index": 0}]]},
        "Parse Ads Upload": {"main": [[{"node": "Build Ads Failure Alert", "type": "main", "index": 0}]]},
        "Build Ads Failure Alert": {"main": [[{"node": "Send Ads Failure Alert", "type": "main", "index": 0}]]},
    }
    return {
        "name": NAME, "nodes": nodes, "connections": connections,
        "settings": {"executionOrder": "v1", "saveDataSuccessExecution": "all", "saveDataErrorExecution": "all"},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gclid-action-id", default=os.getenv("DCT_GOOGLE_ADS_GCLID_ACTION_ID", ""))
    parser.add_argument("--braid-action-id", default=os.getenv("DCT_GOOGLE_ADS_BRAID_ACTION_ID", ""))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.gclid_action_id.isdigit() or not args.braid_action_id.isdigit():
        raise SystemExit("Both numeric --gclid-action-id and --braid-action-id are required")

    existing = next((item for item in api("GET", "/workflows?limit=250").get("data", []) if item.get("name") == NAME), None)
    desired = workflow(args.gclid_action_id, args.braid_action_id)
    if existing:
        workflow_id = existing["id"]
        before = api("GET", f"/workflows/{workflow_id}")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = BACKUP_DIR / f"dct-form-handler-before-ads-{stamp}.json"
        backup.write_text(json.dumps(before, indent=2), encoding="utf-8")
        api("PUT", f"/workflows/{workflow_id}", desired)
        if not existing.get("active"):
            api("POST", f"/workflows/{workflow_id}/activate")
    else:
        created = api("POST", "/workflows", desired)
        workflow_id = created["id"]
        backup = None
        api("POST", f"/workflows/{workflow_id}/activate")

    fresh = api("GET", f"/workflows/{workflow_id}")
    node_names = {node.get("name") for node in fresh.get("nodes", [])}
    required = {"DCT Webhook", "Verify Token", "Send Email Notification", "Build Ads Upload",
                "Get Google OAuth Token", "Upload Click Conversion", "Parse Ads Upload"}
    missing = sorted(required - node_names)
    if missing or not fresh.get("active"):
        raise RuntimeError(f"Post-PUT verification failed; missing={missing}, active={fresh.get('active')}")
    print(json.dumps({
        "id": workflow_id, "name": fresh.get("name"), "active": fresh.get("active"),
        "node_count": len(fresh.get("nodes", [])), "gclid_action_id": args.gclid_action_id,
        "braid_action_id": args.braid_action_id,
        "backup": str(backup) if backup else None,
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
