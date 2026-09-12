#!/usr/bin/env python3
"""Deploy the DCT lead sheet, email-action links, and safe Ads retractions.

Run this on the n8n VPS. The script reads only the n8n API key from the VPS
and keeps Google Ads/OAuth secrets in n8n's environment expressions.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import pathlib
import urllib.error
import urllib.request


N8N_BASE = "http://localhost:5678/api/v1"
MAIN_WORKFLOW_ID = "PmntlqBanV9ZMy3O"
MAIN_WORKFLOW_NAME = "DCT Form Handler"
ACTION_WORKFLOW_NAME = "DCT Lead Email Actions"
SHEET_ID = "1dY5JczBg7qkxMov1HmbPRlOpwPrrKwSndh5NiYXfVTY"
DATA_MANAGER_SHEET_ID = "12NZo1KjNDeuMUk-0f0AirO5lNZD0AssWf41kRTUXGh8"
DATA_MANAGER_SHEET_TAB = "Conversions"
DATA_MANAGER_ACTION_NAME = "DCT - Submit Lead Form (Data Manager - GCLID)"
SHEETS_CREDENTIAL = {
    "googleSheetsOAuth2Api": {
        "id": "YAn0z4KXSLPGMLum",
        "name": "Google Sheets account",
    }
}
CUSTOMER_ID = "3639225242"
LOGIN_CUSTOMER_ID = "3814278874"
GCLID_ACTION_ID = "7762251563"
BRAID_ACTION_ID = "7748270854"
ACTION_BASE_URL = "https://n8.copperchunk.com/webhook/dct-lead-action"
ACTION_POST_URL = "https://n8.copperchunk.com/webhook/dct-lead-action-confirm"
BACKUP_DIR = pathlib.Path("/home/ben/infra/n8n/workflow-backups")


def load_key() -> str:
    path = pathlib.Path("/home/ben/.secrets")
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("N8N_API_KEY=") and line.split("=", 1)[1].strip():
            return line.split("=", 1)[1].strip()
    raise RuntimeError("N8N_API_KEY is missing from /home/ben/.secrets")


class N8nApi:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def call(self, method: str, path: str, payload=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"X-N8N-API-KEY": self.api_key}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(N8N_BASE + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"n8n API {method} {path} failed: HTTP {exc.code}: {body}") from exc


def stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: pathlib.Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def code_node(name: str, node_id: str, position, js_code: str, *, on_error=None):
    node = {
        "parameters": {"language": "javaScript", "jsCode": js_code.strip() + "\n"},
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": list(position),
    }
    if on_error:
        node["onError"] = on_error
    return node


def crypto_node(name: str, node_id: str, position, parameters, *, on_error=None):
    node = {
        "parameters": parameters,
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.crypto",
        "typeVersion": 1,
        "position": list(position),
    }
    if on_error:
        node["onError"] = on_error
    return node


def webhook_node(name: str, node_id: str, position, method: str, path: str):
    return {
        "parameters": {"httpMethod": method, "path": path, "responseMode": "responseNode", "options": {}},
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": list(position),
        "webhookId": node_id,
    }


def schedule_node(name: str, node_id: str, position, minutes: int):
    return {
        "parameters": {"rule": {"interval": [{"field": "minutes", "minutesInterval": minutes}]}},
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": list(position),
    }


def if_node(name: str, node_id: str, position, left_value: str, right_value: str):
    return {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                "conditions": [{
                    "id": node_id + "-condition",
                    "leftValue": left_value,
                    "rightValue": right_value,
                    "operator": {"type": "string", "operation": "equals", "name": "filter.operator.equals"},
                }],
                "combinator": "and",
            },
            "options": {},
        },
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": list(position),
    }


def sheet_ref(value: str):
    return {"__rl": True, "value": value, "mode": "id"}


def sheet_name(value: str):
    return {"__rl": True, "value": value, "mode": "name"}


def sheet_read_node(name: str, node_id: str, position, tab: str, range_a1: str, *, document_id=SHEET_ID, lookup_column=None, lookup_value=None, always_output=False, on_error=None):
    parameters = {
        "authentication": "oAuth2",
        "resource": "sheet",
        "operation": "read",
        "documentId": sheet_ref(document_id),
        "sheetName": sheet_name(tab),
        "options": {
            "dataLocationOnSheet": {"values": {"rangeDefinition": "specifyRangeA1", "range": range_a1}},
            "outputFormatting": {"values": {"general": "FORMATTED_VALUE", "date": "FORMATTED_STRING"}},
            "returnFirstMatch": bool(lookup_column),
        },
    }
    if lookup_column:
        parameters["filtersUI"] = {"values": [{"lookupColumn": lookup_column, "lookupValue": lookup_value or ""}]}
        parameters["combineFilters"] = "AND"
    node = {
        "parameters": parameters,
        "id": node_id,
        "name": name,
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": list(position),
        "credentials": copy.deepcopy(SHEETS_CREDENTIAL),
    }
    if always_output:
        node["alwaysOutputData"] = True
    if on_error:
        node["onError"] = on_error
    return node


def sheet_append_node(name: str, node_id: str, position, tab: str, *, document_id=SHEET_ID):
    return {
        "parameters": {
            "authentication": "oAuth2", "resource": "sheet", "operation": "append",
            "documentId": sheet_ref(document_id), "sheetName": sheet_name(tab),
            "columns": {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []},
            "options": {"handlingExtraData": "ignoreIt", "cellFormat": "RAW"},
        },
        "id": node_id, "name": name, "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5,
        "position": list(position), "credentials": copy.deepcopy(SHEETS_CREDENTIAL),
        "onError": "continueRegularOutput",
    }


def sheet_update_node(name: str, node_id: str, position, tab: str, matching: str, fields: dict, *, document_id=SHEET_ID):
    values = {matching: "={{ $json.%s }}" % matching}
    values.update({key: "={{ $json.%s }}" % key for key in fields})
    return {
        "parameters": {
            "authentication": "oAuth2", "resource": "sheet", "operation": "update",
            "documentId": sheet_ref(document_id), "sheetName": sheet_name(tab),
            "columns": {"mappingMode": "defineBelow", "value": values, "matchingColumns": [matching], "schema": []},
            "options": {"handlingExtraData": "ignoreIt", "cellFormat": "RAW"},
        },
        "id": node_id, "name": name, "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5,
        "position": list(position), "credentials": copy.deepcopy(SHEETS_CREDENTIAL),
        "alwaysOutputData": True, "onError": "continueRegularOutput",
    }


def sheet_update_values_node(name: str, node_id: str, position, tab: str, matching: str, values: dict, *, document_id=SHEET_ID):
    return {
        "parameters": {
            "authentication": "oAuth2", "resource": "sheet", "operation": "update",
            "documentId": sheet_ref(document_id), "sheetName": sheet_name(tab),
            "columns": {"mappingMode": "defineBelow", "value": values, "matchingColumns": [matching], "schema": []},
            "options": {"handlingExtraData": "ignoreIt", "cellFormat": "RAW"},
        },
        "id": node_id, "name": name, "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5,
        "position": list(position), "credentials": copy.deepcopy(SHEETS_CREDENTIAL),
        "alwaysOutputData": True, "onError": "continueRegularOutput",
    }


def oauth_node(name: str, node_id: str, position):
    return {
        "parameters": {
            "method": "POST", "url": "https://oauth2.googleapis.com/token", "authentication": "none",
            "sendHeaders": False, "headerParameters": {"parameters": []}, "sendBody": True,
            "specifyBody": "keypair",
            "bodyParameters": {"parameters": [
                {"name": "client_id", "value": "={{ $env.GOOGLE_ADS_CLIENT_ID }}"},
                {"name": "client_secret", "value": "={{ $env.GOOGLE_ADS_CLIENT_SECRET }}"},
                {"name": "refresh_token", "value": "={{ $env.GOOGLE_ADS_REFRESH_TOKEN }}"},
                {"name": "grant_type", "value": "refresh_token"},
            ]},
            "contentType": "form-urlencoded", "options": {"timeout": 10000},
        },
        "id": node_id, "name": name, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": list(position), "onError": "continueRegularOutput",
    }


def ads_headers():
    return {"parameters": [
        {"name": "Authorization", "value": "=Bearer {{ $json.access_token }}"},
        {"name": "developer-token", "value": "={{ $env.GOOGLE_ADS_DEVELOPER_TOKEN }}"},
        {"name": "login-customer-id", "value": LOGIN_CUSTOMER_ID},
        {"name": "Content-Type", "value": "application/json"},
    ]}


def ads_http_node(name: str, node_id: str, position, endpoint: str, json_body: str):
    return {
        "parameters": {
            "method": "POST", "url": f"https://googleads.googleapis.com/v25/customers/{CUSTOMER_ID}:{endpoint}",
            "authentication": "none", "sendHeaders": True, "headerParameters": ads_headers(),
            "sendBody": True, "specifyBody": "json", "jsonBody": json_body,
            "options": {"timeout": 15000, "response": {"response": {"neverError": True}}},
        },
        "id": node_id, "name": name, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2,
        "position": list(position), "onError": "continueRegularOutput",
    }


def alert_email_node(name: str, node_id: str, position, subject: str, html: str):
    return {
        "parameters": {
            "fromEmail": "ben@copperchunk.com", "toEmail": "btl101@gmail.com",
            "subject": subject, "emailFormat": "html", "html": html, "options": {},
        },
        "id": node_id, "name": name, "type": "n8n-nodes-base.emailSend", "typeVersion": 2.1,
        "position": list(position), "onError": "continueRegularOutput",
        "credentials": {"smtp": {"id": "upVw1vzTxegbXV9E", "name": "Google Workspace SMTP"}},
    }


def respond_html_node(name: str, node_id: str, position, expression: str):
    return {
        "parameters": {
            "respondWith": "text", "responseBody": expression,
            "options": {"responseCode": 200, "enableStreaming": False, "responseHeaders": {"entries": [
                {"name": "Content-Type", "value": "text/html; charset=utf-8"},
                {"name": "Cache-Control", "value": "no-store, max-age=0"},
                {"name": "Pragma", "value": "no-cache"},
                {"name": "Referrer-Policy", "value": "no-referrer"},
                {"name": "X-Robots-Tag", "value": "noindex, nofollow"},
                {"name": "X-Content-Type-Options", "value": "nosniff"},
                {"name": "X-Frame-Options", "value": "DENY"},
            ]}},
        },
        "id": node_id, "name": name, "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.4,
        "position": list(position),
    }


LEAD_SHEET_FIELDS = [
    "submitted_at", "lead_order_id", "first_name", "last_name", "email", "phone", "operator", "destination",
    "departure_city", "travel_date", "duration", "guests", "budget", "pace", "notes", "contact_preference",
    "source_page", "landing_page", "referrer", "utm_source", "utm_medium", "utm_campaign", "utm_term",
    "utm_content", "utm_id", "matchtype", "gad_device", "network", "adgroupid", "targetid", "loc_physical",
    "loc_interest", "gclid", "gbraid", "wbraid", "click_id", "click_id_type", "device_type", "browser_language",
    "time_on_page", "page_load_time", "hashed_email", "hashed_phone", "qa_test", "ads_validate_only",
    "action_token_hash", "ads_upload_status", "ads_upload_error", "ads_conversion_action", "ads_uploaded_at_utc",
    "manual_action", "retraction_processed_at_utc",
]


MAIN_FORMAT_JS = r'''
const lead = $json.body || {};
const actionTokenHash = String($json.action_token_hash || '');
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const row = (label, value) => '<tr><th style="text-align:left;padding:7px 10px;background:#f3eef6;border-bottom:1px solid #ddd">' + esc(label) + '</th><td style="padding:7px 10px;border-bottom:1px solid #ddd">' + (esc(value) || '—') + '</td></tr>';
const isQa = String(lead.qa_test || '') === '1';
const name = String((lead.first_name || '') + ' ' + (lead.last_name || '')).trim();
const subject = (isQa ? '[TEST] ' : '') + 'New DCT lead - ' + (name || 'Website enquiry');
const actionToken = String(lead.action_token || '');
const actionUrl = (action) => 'https://n8.copperchunk.com/webhook/dct-lead-action' + '?oid=' + encodeURIComponent(String(lead.lead_order_id || '')) + '&action=' + encodeURIComponent(action) + '&token=' + encodeURIComponent(actionToken);
let actionsHtml = '';
if (!isQa && /^[a-f0-9]{64}$/i.test(actionToken) && /^[a-f0-9]{64}$/i.test(actionTokenHash) && String(lead.lead_order_id || '')) {
  const good = '<a href="' + esc(actionUrl('good')) + '" style="display:inline-block;background:#16794b;color:#fff;text-decoration:none;font-weight:bold;padding:13px 18px;border-radius:5px;">Mark as good</a>';
  const bad = '<a href="' + esc(actionUrl('bad')) + '" style="display:inline-block;background:#b3261e;color:#fff;text-decoration:none;font-weight:bold;padding:13px 18px;border-radius:5px;">Mark bad / queue retraction</a>';
  actionsHtml = '<div style="font-family:Arial,sans-serif;background:#fff8f7;border:1px solid #f1c7c3;padding:14px 16px;margin:0 0 16px;"><div style="font-weight:bold;color:#1A2B3D;margin-bottom:10px;">Lead actions</div><table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr><td style="padding:0 10px 8px 0;">' + good + '</td><td style="padding:0 0 8px;">' + bad + '</td></tr></table><div style="font-size:12px;color:#667085;line-height:1.45;">Each link opens a confirmation page. Opening or previewing the email cannot change the lead. A bad-lead confirmation only queues the retraction; the Ads API waits until the conversion is at least 24 hours old.</div></div>';
}
const details = [
  ['Lead Order ID', lead.lead_order_id], ['Operator', lead.operator || 'Help me compare'], ['Name', name],
  ['Email', lead.email], ['Phone', lead.phone], ['Destination', lead.destination],
  ['Travel date', lead.travel_date], ['Duration', lead.duration], ['Guests', lead.guests], ['Budget', lead.budget],
  ['Notes', lead.notes], ['Contact preference', lead.contact_preference], ['Source page', lead.source_page],
  ['UTM source', lead.utm_source], ['UTM medium', lead.utm_medium], ['UTM campaign', lead.utm_campaign], ['UTM ID', lead.utm_id],
  ['UTM term', lead.utm_term], ['UTM content', lead.utm_content], ['Match type', lead.matchtype], ['Ad device', lead.gad_device],
  ['Network', lead.network], ['Ad group ID', lead.adgroupid], ['Target ID', lead.targetid], ['Physical location ID', lead.loc_physical],
  ['Interest location ID', lead.loc_interest], ['GCLID', lead.gclid], ['GBRAID', lead.gbraid], ['WBRAID', lead.wbraid],
  ['Click ID type', lead.click_id_type], ['Click ID', lead.click_id], ['Landing page', lead.landing_page], ['Referrer', lead.referrer],
  ['Device', lead.device_type], ['Browser language', lead.browser_language], ['Time on page', lead.time_on_page],
  ['Submitted at', lead.submitted_at]
];
const html = '<div style="font-family:Arial,sans-serif;color:#24142f;max-width:760px"><h2 style="color:#5b247a">' + esc(subject) + '</h2>' + actionsHtml + '<table style="border-collapse:collapse;width:100%">' + details.map((item) => row(item[0], item[1])).join('') + '</table></div>';
return [{json: {...lead, action_token_hash: actionTokenHash, is_qa: isQa, email_subject: subject, email_html: html}}];
'''


BUILD_LEAD_SHEET_ROW_JS = """
const lead = $json;
const fields = %s;
const row = {};
for (const field of fields) row[field] = lead[field] ?? '';
row.action_token_hash = String(lead.action_token_hash || '');
row.ads_upload_status = '';
row.ads_upload_error = '';
row.ads_conversion_action = '';
row.ads_uploaded_at_utc = '';
row.manual_action = '';
row.retraction_processed_at_utc = '';
return [{json: row}];
""" % json.dumps(LEAD_SHEET_FIELDS)


BUILD_ADS_UPLOAD_JS = r'''
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
if (gbraid && wbraid) {
  if (genericType === 'wbraid') gbraid = '';
  else wbraid = '';
}
const braidType = gbraid ? 'gbraid' : (wbraid ? 'wbraid' : '');
const braidValue = gbraid || wbraid;
const route = braidValue ? 'braid' : 'gclid';
const actionId = braidValue ? '7748270854' : '7762251563';

const parsed = new Date(String(lead.submitted_at || ''));
const when = Number.isNaN(parsed.getTime()) ? new Date() : parsed;
const iso = when.toISOString();
const conversionDateTime = iso.slice(0, 10) + ' ' + iso.slice(11, 19) + '+00:00';
const conversion = {
  conversionAction: 'customers/3639225242/conversionActions/' + actionId,
  conversionDateTime,
  conversionValue: 50,
  currencyCode: 'CAD',
  conversionEnvironment: 'WEB',
  orderId: String(lead.lead_order_id || '')
};
const eclRequested = String(lead.ads_ecl_allowed || '') === '1';
const identifiers = [];
if (eclRequested && lead.hashed_email) identifiers.push({hashedEmail: String(lead.hashed_email)});
if (eclRequested && lead.hashed_phone) identifiers.push({hashedPhoneNumber: String(lead.hashed_phone)});
const eclAllowed = eclRequested && identifiers.length > 0;
if (gclid && (!braidType || (eclAllowed && braidType === 'gbraid'))) conversion.gclid = gclid;
if (braidType) conversion[braidType] = braidValue;
if (eclAllowed) conversion.userIdentifiers = identifiers;

return [{json: {
  ...lead,
  ads_route: route,
  ads_action_id: actionId,
  ads_validate_only: validateOnly,
  ads_conversion_datetime: conversionDateTime,
  queue_data_manager: route === 'gclid' && !validateOnly,
  google_ads_request: {conversions: [conversion], partialFailure: true, validateOnly}
}}];
'''


BUILD_DATA_MANAGER_ROW_JS = r'''
const lead = $('Build Ads Upload').first().json || {};
return [{json:{
  'Google Click ID': String(lead.gclid || lead.click_id || ''),
  'Conversion action': 'DCT - Submit Lead Form (Data Manager - GCLID)',
  'Conversion date/time': String(lead.ads_conversion_datetime || ''),
  'Conversion value': 50,
  'Currency': 'CAD',
  'Order ID': String(lead.lead_order_id || ''),
  'Event source': 'WEB',
  'Import status': 'active'
}}];
'''


CHECK_DATA_MANAGER_QUEUE_JS = r'''
const lead = $('Build Ads Upload').first().json || {};
const result = $input.first().json || {};
const failure = result.error || result.errorMessage || result.message || '';
const errorText = failure ? (typeof failure === 'string' ? failure : JSON.stringify(failure)) : '';
return [{json:{...lead,data_manager_queued:!errorText,data_manager_queue_error:errorText}}];
'''


PARSE_ADS_UPLOAD_JS = r'''
const request = $('Build Ads Upload').first().json || {};
const response = $json || {};
let dataManagerQueued = false;
let dataManagerError = '';
if (request.ads_route === 'gclid' && !request.ads_validate_only) {
  const queue = $('Check Data Manager Queue').first().json || {};
  dataManagerQueued = Boolean(queue.data_manager_queued);
  dataManagerError = String(queue.data_manager_queue_error || '');
}
const partial = response.partialFailureError || response.partial_failure_error || null;
const rpc = response.error || null;
const nodeError = response.errorMessage || response.message || null;
const failure = partial || rpc || nodeError;
const results = Array.isArray(response.results) ? response.results : [];
const accepted = !failure && (request.ads_validate_only || results.length > 0);
const errorText = failure ? (typeof failure === 'string' ? failure : JSON.stringify(failure)) : '';
return [{json:{
  ...request,
  data_manager_queued: dataManagerQueued,
  data_manager_queue_error: dataManagerError,
  ads_upload_accepted: accepted,
  ads_upload_error: errorText,
  ads_results_returned: results.length,
  ads_raw_response: response
}}];
'''


BUILD_ADS_ALERT_JS = r'''
const item = $json;
const queueExpected = item.ads_route === 'gclid' && !item.ads_validate_only;
const queueFailed = queueExpected && !item.data_manager_queued;
const immediateFailed = !item.ads_upload_accepted;
if (!queueFailed && !immediateFailed) return [];
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
let label = '';
let prefix = '';
if (item.ads_validate_only) {
  label = 'DCT Google Ads validation rejected'; prefix = '[TEST] ';
} else if (queueFailed && immediateFailed) {
  label = 'DCT immediate upload and Data Manager queue both failed'; prefix = '[ACTION REQUIRED] ';
} else if (queueFailed) {
  label = 'DCT Data Manager backup queue failed'; prefix = '[BACKUP WARNING] ';
} else if (item.data_manager_queued) {
  label = 'DCT immediate upload delayed; Data Manager retry queued'; prefix = '[RETRY QUEUED] ';
} else {
  label = 'DCT Google Ads upload failed'; prefix = '[ACTION REQUIRED] ';
}
const subject = prefix + label + ' - ' + String(item.lead_order_id || 'unknown order');
const html = '<div style="font-family:Arial,sans-serif"><h2>' + esc(label) + '</h2><p><strong>Order ID:</strong> ' + esc(item.lead_order_id) + '</p><p><strong>Route:</strong> ' + esc(item.ads_route) + '</p><p><strong>Action ID:</strong> ' + esc(item.ads_action_id) + '</p><p><strong>Data Manager queued:</strong> ' + esc(item.data_manager_queued) + '</p><p><strong>Immediate API:</strong></p><pre style="white-space:pre-wrap">' + esc(item.ads_upload_error || 'No result returned') + '</pre>' + (queueFailed ? '<p><strong>Queue error:</strong></p><pre style="white-space:pre-wrap">' + esc(item.data_manager_queue_error || 'Unknown queue error') + '</pre>' : '') + '</div>';
return [{json:{...item,ads_alert_subject:subject,ads_alert_html:html}}];
'''


BUILD_ADS_OUTCOME_JS = r'''
const item = $json;
const accepted = Boolean(item.ads_upload_accepted) && !Boolean(item.ads_validate_only);
const validated = Boolean(item.ads_upload_accepted) && Boolean(item.ads_validate_only);
const queued = !accepted && !validated && Boolean(item.data_manager_queued);
const now = new Date().toISOString();
const actionId = String(item.ads_action_id || '');
return [{json:{
  lead_order_id: String(item.lead_order_id || ''),
  ads_upload_status: accepted ? 'accepted' : (validated ? 'validated' : (queued ? 'queued_data_manager' : 'failed')),
  ads_upload_error: [String(item.ads_upload_error || ''), String(item.data_manager_queue_error || '')].filter(Boolean).join(' | '),
  ads_conversion_action: actionId ? 'customers/3639225242/conversionActions/' + actionId : '',
  ads_uploaded_at_utc: accepted ? now : ''
}}];
'''


GET_CONFIRM_JS = r'''
const req = $('Hash GET Action Token').first().json || {};
const q = req.query || {};
const row = $input.first().json || {};
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const shell = (title, body) => '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + esc(title) + '</title></head><body style="margin:0;background:#f4f7f8;color:#1A2B3D;font-family:Arial,sans-serif;"><main style="max-width:620px;margin:40px auto;padding:0 18px;"><div style="background:#fff;border-radius:10px;padding:28px;box-shadow:0 5px 24px rgba(26,43,61,.10);border-top:6px solid #2DBDC5;"><h1 style="font-size:24px;margin:0 0 14px;">' + esc(title) + '</h1>' + body + '</div></main></body></html>';
const oid = String(q.oid || '');
const action = String(q.action || '').toLowerCase();
const token = String(q.token || '');
const tokenHash = String(req.token_hash || '');
const orderOk = /^DCT-\d{8}-\d{6}-[a-f0-9]{8}$/i.test(oid);
const rowFound = String(row.lead_order_id || '') === oid;
const tokenOk = token.length >= 40 && tokenHash.length === 64 && String(row.action_token_hash || '') === tokenHash;
const actionOk = action === 'good' || action === 'bad';
const submittedText = String(row.submitted_at || '');
const submitted = submittedText ? new Date(submittedText.replace(' ', 'T') + (/[zZ]|[+-]\d\d:?\d\d$/.test(submittedText) ? '' : 'Z')) : null;
const expired = !submitted || Number.isNaN(submitted.getTime()) || (Date.now() - submitted.getTime()) > 54 * 86400000;
if (!orderOk || !rowFound || !tokenOk || !actionOk || expired) return [{json:{response_html:shell('This action link is not valid','<p style="line-height:1.55;">The link is invalid, expired, or no longer matches this lead. No changes were made.</p>')}}];
const state = String(row.manual_action || '');
if (String(q.recorded || '') === '1') return [{json:{response_html:shell('Decision recorded','<p style="line-height:1.55;">Your <strong>' + esc(action) + '</strong> decision has been recorded and queued for processing.</p><p style="font-size:13px;color:#667085;">Order ' + esc(oid) + '. You can close this page safely.</p>')}}];
if (state) return [{json:{response_html:shell('Lead already reviewed','<p style="line-height:1.55;">This lead already has a recorded action: <strong>' + esc(state) + '</strong>.</p><p style="font-size:13px;color:#667085;">No new action was taken.</p>')}}];
const adsStatus = String(row.ads_upload_status || '');
const canRetract = Boolean(String(row.gclid || row.gbraid || row.wbraid || row.click_id || '').trim());
let heading = action === 'good' ? 'Confirm this is a good lead' : 'Confirm this lead is bad';
let explanation = action === 'good' ? 'This records the human verdict in the DCT spreadsheet.' : (canRetract ? 'This stops any pending Data Manager retry and queues a Google Ads retraction. The retraction worker starts after the original conversion is at least 24 hours old and keeps retrying until Google can match it.' : 'This records the human verdict as rejected. There is no Google click identifier to retract.');
let button = action === 'good' ? 'Confirm good lead' : (canRetract ? 'Confirm and queue retraction' : 'Confirm rejected lead');
const html = '<p style="line-height:1.55;">' + esc(explanation) + '</p><div style="background:#f7f9fb;border:1px solid #d9e0e6;border-radius:6px;padding:12px 14px;margin:18px 0;"><div><strong>Destination:</strong> ' + esc(row.destination || 'Not specified') + '</div><div><strong>Order:</strong> ' + esc(oid) + '</div><div><strong>Ads status:</strong> ' + esc(adsStatus || 'not uploaded') + '</div></div><form method="post" action="https://n8.copperchunk.com/webhook/dct-lead-action-confirm"><input type="hidden" name="oid" value="' + esc(oid) + '"><input type="hidden" name="action" value="' + esc(action) + '"><input type="hidden" name="token" value="' + esc(token) + '"><input type="hidden" name="confirm" value="yes"><button type="submit" style="border:0;border-radius:5px;background:' + (action === 'good' ? '#16794b' : '#b3261e') + ';color:#fff;font-size:16px;font-weight:bold;padding:13px 18px;cursor:pointer;">' + esc(button) + '</button></form><p style="font-size:12px;color:#667085;margin-top:16px;">Nothing changes until you press the confirmation button.</p>';
return [{json:{response_html:shell(heading, html)}}];
'''


POST_VALIDATE_JS = r'''
const req = $('Hash POST Action Token').first().json || {};
const form = req.body || {};
const row = $input.first().json || {};
const oid = String(form.oid || '');
const action = String(form.action || '').toLowerCase();
const token = String(form.token || '');
const tokenHash = String(req.token_hash || '');
const submittedText = String(row.submitted_at || '');
const submitted = submittedText ? new Date(submittedText.replace(' ', 'T') + (/[zZ]|[+-]\d\d:?\d\d$/.test(submittedText) ? '' : 'Z')) : null;
const expired = !submitted || Number.isNaN(submitted.getTime()) || (Date.now() - submitted.getTime()) > 54 * 86400000;
const valid = String(form.confirm || '').toLowerCase() === 'yes' && /^DCT-\d{8}-\d{6}-[a-f0-9]{8}$/i.test(oid) && (action === 'good' || action === 'bad') && token.length >= 40 && tokenHash.length === 64 && String(row.lead_order_id || '') === oid && String(row.action_token_hash || '') === tokenHash && !expired;
const errorHtml = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Action not recorded</title></head><body style="font-family:Arial,sans-serif;background:#f4f7f8;color:#1A2B3D;"><main style="max-width:620px;margin:40px auto;background:#fff;padding:28px;border-top:6px solid #b3261e;"><h1>Action not recorded</h1><p>The confirmation was invalid or expired. No changes were made.</p></main></body></html>';
return [{json:{valid, error_html:errorHtml, lead_order_id:oid, requested_action:action, token_hash:tokenHash, received_at_utc:new Date().toISOString(), source:'email', execution_id:String($execution.id || '')}}];
'''


BUILD_EVENT_JS = r'''
const validated = $('Validate DCT Action POST').first().json;
return [{json:{event_id:String($json.event_id || ''),received_at_utc:validated.received_at_utc,lead_order_id:validated.lead_order_id,requested_action:validated.requested_action,token_hash:validated.token_hash,source:validated.source,processed_at_utc:'',result:'',ads_due_at_utc:'',ads_processed_at_utc:'',ads_result:'',ads_conversion_action:'',execution_id:validated.execution_id,detail:'',ads_attempt_count:0,ads_next_attempt_at_utc:''}}];
'''


PICK_EVENT_JS = r'''
const rows = $input.all().map(i => i.json).filter(r => String(r.event_id || '') && !String(r.processed_at_utc || ''));
rows.sort((a,b) => Number(a.row_number || 0) - Number(b.row_number || 0) || String(a.received_at_utc || '').localeCompare(String(b.received_at_utc || '')));
return rows.length ? [{json:rows[0]}] : [];
'''


DECIDE_EVENT_JS = r'''
const event = $('Pick Next DCT Action').first().json || {};
const row = $input.first().json || {};
const now = new Date();
const requested = String(event.requested_action || '').toLowerCase();
const current = String(row.manual_action || '');
const found = String(row.lead_order_id || '') === String(event.lead_order_id || '');
const tokenOk = String(row.action_token_hash || '') === String(event.token_hash || '') && String(event.token_hash || '').length === 64;
let nextState = current;
let result = '';
let detail = '';
let due = '';
let writeLead = false;
let disableDataManager = false;
let adsAction = '';
if (!found || !tokenOk || !['good','bad'].includes(requested)) {
  result = 'invalid_event'; detail = 'Lead or action token no longer matches.';
} else if (current) {
  const same = (current.startsWith('good_') && requested === 'good') || (current.startsWith('bad_') && requested === 'bad');
  result = same ? 'duplicate_ignored' : 'conflict_ignored'; detail = same ? 'The same decision was already recorded.' : 'The first confirmed decision remains in force.';
} else if (requested === 'good') {
  writeLead = true;
  nextState = String(row.ads_upload_status || '') === 'accepted' ? 'good_verified' : 'good_recorded';
  result = 'good_recorded'; detail = 'Human marked the lead as good.';
} else {
  writeLead = true;
  const hasBraid = Boolean(String(row.gbraid || row.wbraid || '').trim()) || ['gbraid','wbraid'].includes(String(row.click_id_type || '').toLowerCase());
  const hasGclid = Boolean(String(row.gclid || '').trim()) || String(row.click_id_type || '').toLowerCase() === 'gclid';
  adsAction = hasBraid ? 'customers/3639225242/conversionActions/7748270854' : (hasGclid ? 'customers/3639225242/conversionActions/7762251563' : '');
  const canRetract = Boolean(adsAction);
  if (canRetract) {
    const raw = String(row.submitted_at || row.ads_uploaded_at_utc || '');
    const submitted = new Date(raw.replace(' ', 'T') + (/[zZ]|[+-]\d\d:?\d\d$/.test(raw) ? '' : 'Z'));
    const earliest = Number.isNaN(submitted.getTime()) ? now.getTime() : submitted.getTime() + (24 * 60 + 30) * 60000;
    due = new Date(Math.max(now.getTime(), earliest)).toISOString();
    disableDataManager = hasGclid && !hasBraid;
    nextState = 'bad_retraction_queued'; result = 'retraction_queued'; detail = 'Human marked bad; Data Manager retry stopped where present; retraction due ' + due + '.';
  } else {
    nextState = 'bad_rejected'; result = 'rejected'; detail = 'Human marked bad; no accepted DCT Ads conversion is available to retract.';
  }
}
return [{json:{...event,_write_lead:writeLead,_disable_data_manager:disableDataManager,lead_order_id:String(event.lead_order_id || ''),dm_import_status:'retracted',manual_action:nextState,processed_at_utc:now.toISOString(),result,ads_due_at_utc:due,ads_processed_at_utc:'',ads_result:'',ads_conversion_action:adsAction || String(row.ads_conversion_action || ''),detail,ads_attempt_count:0,ads_next_attempt_at_utc:due}}];
'''


PICK_DUE_RETRACTION_JS = r'''
const now = Date.now();
const rows = $input.all().map(i => i.json).filter(r => {
  const due = String(r.ads_next_attempt_at_utc || r.ads_due_at_utc || '');
  return String(r.event_id || '') && String(r.result || '') === 'retraction_queued' && !String(r.ads_processed_at_utc || '') && due && new Date(due).getTime() <= now;
});
rows.sort((a,b) => new Date(a.ads_next_attempt_at_utc || a.ads_due_at_utc).getTime() - new Date(b.ads_next_attempt_at_utc || b.ads_due_at_utc).getTime() || Number(a.row_number || 0) - Number(b.row_number || 0));
return rows.length ? [{json:rows[0]}] : [];
'''


PREPARE_RETRACTION_JS = r'''
const event = $('Pick Due DCT Retraction').first().json || {};
const row = $input.first().json || {};
const now = new Date();
const found = String(row.lead_order_id || '') === String(event.lead_order_id || '');
const state = String(row.manual_action || '');
const hasBraid = Boolean(String(row.gbraid || row.wbraid || '').trim()) || ['gbraid','wbraid'].includes(String(row.click_id_type || '').toLowerCase());
const hasGclid = Boolean(String(row.gclid || '').trim()) || String(row.click_id_type || '').toLowerCase() === 'gclid';
const derivedAction = hasBraid ? 'customers/3639225242/conversionActions/7748270854' : (hasGclid ? 'customers/3639225242/conversionActions/7762251563' : '');
const action = String(event.ads_conversion_action || derivedAction || row.ads_conversion_action || '');
const validAction = /^customers\/3639225242\/conversionActions\/(7762251563|7748270854)$/.test(action);
const raw = String(row.submitted_at || row.ads_uploaded_at_utc || '');
const submitted = new Date(raw.replace(' ', 'T') + (/[zZ]|[+-]\d\d:?\d\d$/.test(raw) ? '' : 'Z'));
const ageDays = Number.isNaN(submitted.getTime()) ? 999 : (now.getTime() - submitted.getTime()) / 86400000;
let doRetract = false;
let nextState = state;
let adsResult = '';
let detail = '';
let processed = now.toISOString();
if (!found) { adsResult = 'lead_not_found'; detail = 'DCT lead row was not found.'; }
else if (state !== 'bad_retraction_queued') { adsResult = 'state_changed'; detail = 'Retraction cancelled because lead state is ' + (state || 'blank') + '.'; }
else if (!validAction) { adsResult = 'not_eligible'; detail = 'Retraction cancelled because there is no supported DCT conversion action.'; }
else if (ageDays > 54) { nextState = 'bad_retraction_expired'; adsResult = 'expired'; detail = 'Google Ads retraction window expired; manual attention required.'; }
else if (ageDays < 1) { adsResult = 'not_due'; processed = ''; detail = 'Retraction is not yet 24 hours old.'; }
else { doRetract = true; processed = ''; detail = 'Retraction ready for Google Ads.'; }
return [{json:{...event,_do_retract:doRetract,lead_order_id:String(event.lead_order_id || ''),manual_action:nextState,retraction_processed_at_utc:doRetract?'':now.toISOString(),ads_processed_at_utc:processed,ads_result:adsResult,ads_conversion_action:action,detail,ads_attempt_count:Number(event.ads_attempt_count || 0),ads_next_attempt_at_utc:String(event.ads_next_attempt_at_utc || event.ads_due_at_utc || '')}}];
'''


PARSE_RETRACTION_JS = r'''
const event = $('Prepare DCT Retraction').first().json || {};
const resp = $input.first().json || {};
const failureObject = resp.partialFailureError || resp.partial_failure_error || resp.error || resp.errorMessage || resp.message || '';
const failure = failureObject ? (typeof failureObject === 'string' ? failureObject : JSON.stringify(failureObject)) : '';
const already = /ALREADY_RETRACTED|CONVERSION_ALREADY_RETRACTED/i.test(failure);
const accepted = already || (Array.isArray(resp.results) && resp.results.length > 0 && !failure);
const attempt = Number(event.ads_attempt_count || 0) + 1;
const nowDate = new Date();
const now = nowDate.toISOString();
const submittedRaw = String(event.ads_due_at_utc || '');
const ageDays = submittedRaw ? (nowDate.getTime() - new Date(submittedRaw).getTime()) / 86400000 + (24.5 / 24) : 0;
const retryable = !accepted && (!failure || /CONVERSION_NOT_FOUND|TOO_RECENT|UNAUTHENTICATED|invalid_grant|RESOURCE_EXHAUSTED|INTERNAL|UNAVAILABLE|DEADLINE_EXCEEDED|temporar|timeout|429|5\d\d/i.test(failure));
const canRetry = retryable && ageDays <= 54;
const delayHours = attempt <= 2 ? 1 : (attempt <= 4 ? 3 : (attempt <= 8 ? 6 : 12));
const nextAttempt = canRetry ? new Date(nowDate.getTime() + delayHours * 3600000).toISOString() : '';
const detail = already ? 'Google Ads reports this conversion was already retracted.' : (accepted ? 'Google Ads accepted the retraction.' : (canRetry ? 'Retraction attempt ' + attempt + ' failed and will retry at ' + nextAttempt + ': ' : 'Google Ads retraction failed permanently: ') + (failure || JSON.stringify(resp)).slice(0, 500));
return [{json:{...event,_do_retract:false,manual_action:accepted?'bad_retracted':(canRetry?'bad_retraction_queued':'bad_retraction_failed'),retraction_processed_at_utc:accepted||!canRetry?now:'',ads_processed_at_utc:accepted||!canRetry?now:'',ads_result:accepted?(already?'already_retracted':'accepted'):(canRetry?'retry_scheduled':'failed'),detail,ads_attempt_count:attempt,ads_next_attempt_at_utc:nextAttempt}}];
'''


BUILD_RETRACTION_ALERT_JS = r'''
const item = $json || {};
const result = String(item.ads_result || '');
const attempt = Number(item.ads_attempt_count || 0);
const terminal = ['failed','expired','lead_not_found','not_eligible'].includes(result);
const scheduledNotice = result === 'retry_scheduled' && [1,4,8,12,20,28,36,44].includes(attempt);
if (!terminal && !scheduledNotice) return [];
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const prefix = terminal ? '[ACTION REQUIRED] ' : '[RETRACTION RETRY] ';
const subject = prefix + 'DCT lead ' + String(item.lead_order_id || 'unknown');
const html = '<div style="font-family:Arial,sans-serif"><h2>DCT conversion retraction</h2><p><strong>Order:</strong> ' + esc(item.lead_order_id) + '</p><p><strong>Result:</strong> ' + esc(result) + '</p><p><strong>Attempt:</strong> ' + esc(attempt) + '</p><p><strong>Next attempt:</strong> ' + esc(item.ads_next_attempt_at_utc || 'none') + '</p><pre style="white-space:pre-wrap">' + esc(item.detail || '') + '</pre></div>';
return [{json:{...item,retraction_alert_subject:subject,retraction_alert_html:html}}];
'''


RETRACTION_BODY = "={{ (() => { const b=$('Prepare DCT Retraction').first().json; const d=new Date(); const p=n=>String(n).padStart(2,'0'); const when=`${d.getUTCFullYear()}-${p(d.getUTCMonth()+1)}-${p(d.getUTCDate())} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}+00:00`; return {conversionAdjustments:[{conversionAction:b.ads_conversion_action,adjustmentType:'RETRACTION',orderId:b.lead_order_id,adjustmentDateTime:when}],partialFailure:true}; })() }}"


def patch_main_workflow(workflow: dict) -> dict:
    workflow = copy.deepcopy(workflow)
    by_name = {node["name"]: node for node in workflow.get("nodes", [])}

    if "Send Email Notification" in by_name:
        by_name["Send Email Notification"].setdefault("parameters", {})["toEmail"] = "={{ $json.is_qa ? 'btl101@gmail.com' : 'btl101@gmail.com, sales@rivercruisenetwork.com' }}"

    by_name["Hash Action Token"] = crypto_node(
        "Hash Action Token", "dct-hash-action-token", (-360, 0),
        {"action": "hash", "type": "SHA256", "binaryData": False,
         "value": "={{ $json.body.action_token || '' }}", "dataPropertyName": "action_token_hash", "encoding": "hex"},
    )
    by_name["Format Lead Email"] = code_node("Format Lead Email", "format-email", (-140, 0), MAIN_FORMAT_JS)
    by_name["Build Lead Sheet Row"] = code_node("Build Lead Sheet Row", "dct-build-lead-sheet-row", (100, -20), BUILD_LEAD_SHEET_ROW_JS)
    by_name["Log Lead to Google Sheet"] = sheet_append_node("Log Lead to Google Sheet", "dct-log-lead-sheet", (340, -20), "Leads")
    by_name["Restore Lead After Logging"] = code_node("Restore Lead After Logging", "dct-restore-lead-after-log", (560, -20), "return [{json:{...$('Format Lead Email').first().json}}];")
    by_name["Build Ads Upload"] = code_node("Build Ads Upload", "build-ads-upload", (780, 80), BUILD_ADS_UPLOAD_JS)
    by_name["IF Queue GCLID in Data Manager"] = if_node("IF Queue GCLID in Data Manager", "dct-if-queue-data-manager", (1000, 80), "={{ String($json.queue_data_manager) }}", "true")
    by_name["Build Data Manager Queue Row"] = code_node("Build Data Manager Queue Row", "dct-build-data-manager-row", (1220, 0), BUILD_DATA_MANAGER_ROW_JS)
    by_name["Append Data Manager Queue"] = sheet_append_node(
        "Append Data Manager Queue", "dct-append-data-manager-queue", (1440, 0), DATA_MANAGER_SHEET_TAB,
        document_id=DATA_MANAGER_SHEET_ID,
    )
    by_name["Check Data Manager Queue"] = code_node("Check Data Manager Queue", "dct-check-data-manager-queue", (1660, 0), CHECK_DATA_MANAGER_QUEUE_JS, on_error="continueRegularOutput")
    by_name["Get Google OAuth Token"] = oauth_node("Get Google OAuth Token", "get-google-token", (1880, 80))
    by_name["Upload Click Conversion"] = ads_http_node(
        "Upload Click Conversion", "upload-click-conversion", (2100, 80), "uploadClickConversions",
        "={{ $('Build Ads Upload').first().json.google_ads_request }}",
    )
    by_name["Parse Ads Upload"] = code_node("Parse Ads Upload", "parse-ads-upload", (2320, 80), PARSE_ADS_UPLOAD_JS, on_error="continueRegularOutput")
    by_name["Build Ads Failure Alert"] = code_node("Build Ads Failure Alert", "build-ads-alert", (2540, 0), BUILD_ADS_ALERT_JS)
    by_name["Send Ads Failure Alert"] = alert_email_node(
        "Send Ads Failure Alert", "send-ads-alert", (2760, 0),
        "={{ $json.ads_alert_subject }}", "={{ $json.ads_alert_html }}",
    )
    by_name["Build Ads Outcome Row"] = code_node("Build Ads Outcome Row", "dct-build-ads-outcome-row", (2540, 160), BUILD_ADS_OUTCOME_JS, on_error="continueRegularOutput")
    by_name["Update Lead Ads Outcome"] = sheet_update_node(
        "Update Lead Ads Outcome", "dct-update-lead-ads-outcome", (2760, 160), "Leads", "lead_order_id",
        {"ads_upload_status": "", "ads_upload_error": "", "ads_conversion_action": "", "ads_uploaded_at_utc": ""},
    )
    by_name["IF Mark DCT Queue Uploaded"] = if_node(
        "IF Mark DCT Queue Uploaded", "dct-if-mark-data-manager-uploaded", (2540, 320),
        "={{ String($json.ads_upload_accepted && $json.ads_route === 'gclid' && !$json.ads_validate_only) }}", "true",
    )
    by_name["Mark DCT Queue Uploaded"] = sheet_update_values_node(
        "Mark DCT Queue Uploaded", "dct-mark-data-manager-uploaded", (2760, 320), DATA_MANAGER_SHEET_TAB, "Order ID",
        {"Order ID": "={{ $json.lead_order_id }}", "Import status": "uploaded_api"},
        document_id=DATA_MANAGER_SHEET_ID,
    )

    replacements = {
        "Hash Action Token", "Format Lead Email", "Build Lead Sheet Row", "Log Lead to Google Sheet",
        "Restore Lead After Logging", "Build Ads Upload", "IF Queue GCLID in Data Manager",
        "Build Data Manager Queue Row", "Append Data Manager Queue", "Check Data Manager Queue",
        "Get Google OAuth Token", "Upload Click Conversion", "Parse Ads Upload",
        "Build Ads Failure Alert", "Send Ads Failure Alert", "Build Ads Outcome Row", "Update Lead Ads Outcome",
        "IF Mark DCT Queue Uploaded", "Mark DCT Queue Uploaded",
    }
    original_nodes = workflow.get("nodes", [])
    workflow["nodes"] = [
        by_name[node["name"]] if node["name"] in replacements else node
        for node in original_nodes
    ]
    existing_names = {node["name"] for node in original_nodes}
    workflow["nodes"].extend(node for name, node in by_name.items() if name not in existing_names)

    c = workflow.setdefault("connections", {})
    c["DCT Webhook"] = {"main": [[{"node": "Verify Token", "type": "main", "index": 0}]]}
    c["Verify Token"] = {"main": [[{"node": "Hash Action Token", "type": "main", "index": 0}]]}
    c["Hash Action Token"] = {"main": [[{"node": "Format Lead Email", "type": "main", "index": 0}]]}
    c["Format Lead Email"] = {"main": [[
        {"node": "Send Email Notification", "type": "main", "index": 0},
        {"node": "Build Lead Sheet Row", "type": "main", "index": 0},
    ]]}
    c["Build Lead Sheet Row"] = {"main": [[{"node": "Log Lead to Google Sheet", "type": "main", "index": 0}]]}
    c["Log Lead to Google Sheet"] = {"main": [[{"node": "Restore Lead After Logging", "type": "main", "index": 0}]]}
    c["Restore Lead After Logging"] = {"main": [[{"node": "Build Ads Upload", "type": "main", "index": 0}]]}
    c["Build Ads Upload"] = {"main": [[{"node": "IF Queue GCLID in Data Manager", "type": "main", "index": 0}]]}
    c["IF Queue GCLID in Data Manager"] = {"main": [
        [{"node": "Build Data Manager Queue Row", "type": "main", "index": 0}],
        [{"node": "Get Google OAuth Token", "type": "main", "index": 0}],
    ]}
    c["Build Data Manager Queue Row"] = {"main": [[{"node": "Append Data Manager Queue", "type": "main", "index": 0}]]}
    c["Append Data Manager Queue"] = {"main": [[{"node": "Check Data Manager Queue", "type": "main", "index": 0}]]}
    c["Check Data Manager Queue"] = {"main": [[{"node": "Get Google OAuth Token", "type": "main", "index": 0}]]}
    c["Get Google OAuth Token"] = {"main": [[{"node": "Upload Click Conversion", "type": "main", "index": 0}]]}
    c["Upload Click Conversion"] = {"main": [[{"node": "Parse Ads Upload", "type": "main", "index": 0}]]}
    c["Parse Ads Upload"] = {"main": [[
        {"node": "Build Ads Failure Alert", "type": "main", "index": 0},
        {"node": "Build Ads Outcome Row", "type": "main", "index": 0},
        {"node": "IF Mark DCT Queue Uploaded", "type": "main", "index": 0},
    ]]}
    c["Build Ads Outcome Row"] = {"main": [[{"node": "Update Lead Ads Outcome", "type": "main", "index": 0}]]}
    c["Build Ads Failure Alert"] = {"main": [[{"node": "Send Ads Failure Alert", "type": "main", "index": 0}]]}
    c["IF Mark DCT Queue Uploaded"] = {"main": [
        [{"node": "Mark DCT Queue Uploaded", "type": "main", "index": 0}],
        [],
    ]}
    return workflow


def action_workflow_definition() -> dict:
    def connect(c, source, *targets):
        c[source] = {"main": [[{"node": target, "type": "main", "index": 0} for target in targets]]}

    def connect_if(c, source, true_target, false_target):
        c[source] = {"main": [
            ([{"node": true_target, "type": "main", "index": 0}] if true_target else []),
            ([{"node": false_target, "type": "main", "index": 0}] if false_target else []),
        ]}

    nodes = [
        webhook_node("Confirm DCT Action GET", "dct-action-get", (0, 0), "GET", "dct-lead-action"),
        crypto_node("Hash GET Action Token", "dct-hash-get-action-token", (220, 0), {"action":"hash","type":"SHA256","binaryData":False,"value":"={{ $json.query.token || '' }}","dataPropertyName":"token_hash","encoding":"hex"}),
        sheet_read_node("Read DCT Lead for GET", "dct-read-lead-get", (440, 0), "Leads", "A:AZ", lookup_column="lead_order_id", lookup_value="={{ $('Hash GET Action Token').first().json.query.oid || '' }}", always_output=True, on_error="continueRegularOutput"),
        code_node("Build DCT Confirmation Page", "dct-build-confirmation", (660, 0), GET_CONFIRM_JS),
        respond_html_node("Respond DCT Confirmation Page", "dct-respond-confirmation", (880, 0), "={{ $json.response_html }}"),

        webhook_node("Confirm DCT Action POST", "dct-action-post", (0, 300), "POST", "dct-lead-action-confirm"),
        crypto_node("Hash POST Action Token", "dct-hash-post-action-token", (220, 300), {"action":"hash","type":"SHA256","binaryData":False,"value":"={{ $json.body.token || '' }}","dataPropertyName":"token_hash","encoding":"hex"}),
        sheet_read_node("Read DCT Lead for POST", "dct-read-lead-post", (440, 300), "Leads", "A:AZ", lookup_column="lead_order_id", lookup_value="={{ $('Hash POST Action Token').first().json.body.oid || '' }}", always_output=True, on_error="continueRegularOutput"),
        code_node("Validate DCT Action POST", "dct-validate-action-post", (660, 300), POST_VALIDATE_JS),
        if_node("IF Valid DCT Action", "dct-if-valid-action", (880, 300), "={{ String($json.valid) }}", "true"),
        crypto_node("Generate DCT Event ID", "dct-generate-event-id", (1100, 240), {"action":"generate","dataPropertyName":"event_id","encodingType":"uuid"}),
        code_node("Build DCT Lead Action Event", "dct-build-action-event", (1320, 240), BUILD_EVENT_JS),
        sheet_append_node("Append DCT Lead Action Event", "dct-append-action-event", (1540, 240), "Lead Actions"),
        {
            "parameters": {"respondWith":"redirect","redirectURL":"={{ 'https://n8.copperchunk.com/webhook/dct-lead-action?oid=' + encodeURIComponent($('Validate DCT Action POST').first().json.lead_order_id) + '&action=' + encodeURIComponent($('Validate DCT Action POST').first().json.requested_action) + '&token=' + encodeURIComponent($('Hash POST Action Token').first().json.body.token || '') + '&recorded=1' }}","options":{"responseCode":303,"responseHeaders":{"entries":[{"name":"Cache-Control","value":"no-store"},{"name":"Referrer-Policy","value":"no-referrer"}]}}},
            "id":"dct-redirect-after-post","name":"Redirect After DCT Action POST","type":"n8n-nodes-base.respondToWebhook","typeVersion":1.4,"position":[1760,240],
        },
        respond_html_node("Respond Invalid DCT Action POST", "dct-respond-invalid-post", (1100, 380), "={{ $json.error_html }}"),

        schedule_node("Process DCT Action Events", "dct-action-worker-schedule", (0, 660), 1),
        sheet_read_node("Read DCT Action Events", "dct-read-action-events", (220, 660), "Lead Actions", "A:P"),
        code_node("Pick Next DCT Action", "dct-pick-action-event", (440, 660), PICK_EVENT_JS),
        sheet_read_node("Read DCT Lead for Action", "dct-read-lead-event", (660, 660), "Leads", "A:AZ", lookup_column="lead_order_id", lookup_value="={{ $('Pick Next DCT Action').first().json.lead_order_id || '' }}", always_output=True),
        code_node("Decide DCT Action", "dct-decide-action", (880, 660), DECIDE_EVENT_JS),
        if_node("IF Update DCT Lead", "dct-if-update-lead", (1100, 660), "={{ String($json._write_lead) }}", "true"),
        sheet_update_node("Update DCT Lead Manual Action", "dct-update-lead-manual-action", (1320, 600), "Leads", "lead_order_id", {"manual_action":""}),
        if_node("IF Stop DCT Data Manager Retry", "dct-if-stop-data-manager", (1540, 600), "={{ String($json._disable_data_manager) }}", "true"),
        sheet_update_values_node(
            "Stop DCT Data Manager Retry", "dct-stop-data-manager-retry", (1760, 540), DATA_MANAGER_SHEET_TAB, "Order ID",
            {"Order ID": "={{ $json.lead_order_id }}", "Import status": "={{ $json.dm_import_status }}"},
            document_id=DATA_MANAGER_SHEET_ID,
        ),
        code_node("Restore DCT Action Event", "dct-restore-action-event", (1980, 600), "return [{json:{...$('Decide DCT Action').first().json}}];"),
        sheet_update_node("Update DCT Action Outcome", "dct-update-action-outcome", (2200, 660), "Lead Actions", "event_id", {"processed_at_utc":"","result":"","ads_due_at_utc":"","ads_processed_at_utc":"","ads_result":"","ads_conversion_action":"","detail":"","ads_attempt_count":"","ads_next_attempt_at_utc":""}),

        schedule_node("Process Due DCT Retractions", "dct-retraction-worker-schedule", (0, 1040), 15),
        sheet_read_node("Read DCT Retraction Events", "dct-read-retraction-events", (220, 1040), "Lead Actions", "A:P"),
        code_node("Pick Due DCT Retraction", "dct-pick-due-retraction", (440, 1040), PICK_DUE_RETRACTION_JS),
        sheet_read_node("Read DCT Lead for Retraction", "dct-read-lead-retraction", (660, 1040), "Leads", "A:AZ", lookup_column="lead_order_id", lookup_value="={{ $('Pick Due DCT Retraction').first().json.lead_order_id || '' }}", always_output=True),
        code_node("Prepare DCT Retraction", "dct-prepare-retraction", (880, 1040), PREPARE_RETRACTION_JS),
        if_node("IF Call DCT Google Retraction", "dct-if-call-retraction", (1100, 1040), "={{ String($json._do_retract) }}", "true"),
        oauth_node("Get OAuth for DCT Retraction", "dct-oauth-retraction", (1320, 980)),
        ads_http_node("Upload DCT Conversion Retraction", "dct-upload-retraction", (1540, 980), "uploadConversionAdjustments", RETRACTION_BODY),
        code_node("Parse DCT Retraction Result", "dct-parse-retraction", (1760, 980), PARSE_RETRACTION_JS),
        sheet_update_node("Update DCT Lead Retraction Result", "dct-update-lead-retraction-result", (1980, 980), "Leads", "lead_order_id", {"manual_action":"","retraction_processed_at_utc":""}),
        code_node("Restore DCT Parsed Retraction", "dct-restore-parsed-retraction", (2200, 980), "return [{json:{...$('Parse DCT Retraction Result').first().json}}];"),
        sheet_update_node("Update DCT Lead Retraction State", "dct-update-lead-retraction-state", (1320, 1160), "Leads", "lead_order_id", {"manual_action":"","retraction_processed_at_utc":""}),
        code_node("Restore DCT Prepared Retraction", "dct-restore-prepared-retraction", (1540, 1160), "return [{json:{...$('Prepare DCT Retraction').first().json}}];"),
        sheet_update_node("Update DCT Retraction Event", "dct-update-retraction-event", (2420, 1040), "Lead Actions", "event_id", {"ads_processed_at_utc":"","ads_result":"","ads_conversion_action":"","detail":"","ads_attempt_count":"","ads_next_attempt_at_utc":""}),
        code_node("Build DCT Retraction Alert", "dct-build-retraction-alert", (2420, 880), BUILD_RETRACTION_ALERT_JS),
        alert_email_node("Send DCT Retraction Alert", "dct-send-retraction-alert", (2640, 880), "={{ $json.retraction_alert_subject }}", "={{ $json.retraction_alert_html }}"),
    ]

    c = {}
    connect(c, "Confirm DCT Action GET", "Hash GET Action Token")
    connect(c, "Hash GET Action Token", "Read DCT Lead for GET")
    connect(c, "Read DCT Lead for GET", "Build DCT Confirmation Page")
    connect(c, "Build DCT Confirmation Page", "Respond DCT Confirmation Page")

    connect(c, "Confirm DCT Action POST", "Hash POST Action Token")
    connect(c, "Hash POST Action Token", "Read DCT Lead for POST")
    connect(c, "Read DCT Lead for POST", "Validate DCT Action POST")
    connect(c, "Validate DCT Action POST", "IF Valid DCT Action")
    connect_if(c, "IF Valid DCT Action", "Generate DCT Event ID", "Respond Invalid DCT Action POST")
    connect(c, "Generate DCT Event ID", "Build DCT Lead Action Event")
    connect(c, "Build DCT Lead Action Event", "Append DCT Lead Action Event")
    connect(c, "Append DCT Lead Action Event", "Redirect After DCT Action POST")

    connect(c, "Process DCT Action Events", "Read DCT Action Events")
    connect(c, "Read DCT Action Events", "Pick Next DCT Action")
    connect(c, "Pick Next DCT Action", "Read DCT Lead for Action")
    connect(c, "Read DCT Lead for Action", "Decide DCT Action")
    connect(c, "Decide DCT Action", "IF Update DCT Lead")
    connect_if(c, "IF Update DCT Lead", "Update DCT Lead Manual Action", "Update DCT Action Outcome")
    connect(c, "Update DCT Lead Manual Action", "IF Stop DCT Data Manager Retry")
    connect_if(c, "IF Stop DCT Data Manager Retry", "Stop DCT Data Manager Retry", "Restore DCT Action Event")
    connect(c, "Stop DCT Data Manager Retry", "Restore DCT Action Event")
    connect(c, "Restore DCT Action Event", "Update DCT Action Outcome")

    connect(c, "Process Due DCT Retractions", "Read DCT Retraction Events")
    connect(c, "Read DCT Retraction Events", "Pick Due DCT Retraction")
    connect(c, "Pick Due DCT Retraction", "Read DCT Lead for Retraction")
    connect(c, "Read DCT Lead for Retraction", "Prepare DCT Retraction")
    connect(c, "Prepare DCT Retraction", "IF Call DCT Google Retraction")
    connect_if(c, "IF Call DCT Google Retraction", "Get OAuth for DCT Retraction", "Update DCT Lead Retraction State")
    connect(c, "Get OAuth for DCT Retraction", "Upload DCT Conversion Retraction")
    connect(c, "Upload DCT Conversion Retraction", "Parse DCT Retraction Result")
    connect(c, "Parse DCT Retraction Result", "Update DCT Lead Retraction Result")
    connect(c, "Update DCT Lead Retraction Result", "Restore DCT Parsed Retraction")
    connect(c, "Restore DCT Parsed Retraction", "Update DCT Retraction Event", "Build DCT Retraction Alert")
    connect(c, "Update DCT Lead Retraction State", "Restore DCT Prepared Retraction")
    connect(c, "Restore DCT Prepared Retraction", "Update DCT Retraction Event", "Build DCT Retraction Alert")
    connect(c, "Build DCT Retraction Alert", "Send DCT Retraction Alert")

    return {"name": ACTION_WORKFLOW_NAME, "nodes": nodes, "connections": c,
            "settings": {"executionOrder": "v1", "callerPolicy": "workflowsFromSameOwner", "availableInMCP": False}}


def writable_workflow(workflow: dict):
    return {key: workflow[key] for key in ("name", "nodes", "connections", "settings")}


def list_workflows(api: N8nApi):
    return api.call("GET", "/workflows?limit=250").get("data", [])


def verify(api: N8nApi, workflow_id: str, required: set[str]):
    fresh = api.call("GET", f"/workflows/{workflow_id}")
    names = {node.get("name") for node in fresh.get("nodes", [])}
    missing = sorted(required - names)
    if missing or not fresh.get("active"):
        raise RuntimeError(f"Workflow verification failed for {workflow_id}; missing={missing}, active={fresh.get('active')}")
    return fresh


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--phase", choices=("all", "action", "main"), default="all")
    args = parser.parse_args()

    api = N8nApi(load_key())
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    run_stamp = stamp()
    action_def = action_workflow_definition()
    action_existing = next((w for w in list_workflows(api) if w.get("name") == ACTION_WORKFLOW_NAME), None)
    if action_existing:
        action_live = api.call("GET", f"/workflows/{action_existing['id']}")
        write_json(BACKUP_DIR / f"dct-action-before-{run_stamp}.json", action_live)
    main_live = api.call("GET", f"/workflows/{MAIN_WORKFLOW_ID}")
    main_candidate = patch_main_workflow(main_live)
    write_json(BACKUP_DIR / f"dct-main-candidate-{run_stamp}.json", main_candidate)
    write_json(BACKUP_DIR / f"dct-action-candidate-{run_stamp}.json", action_def)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "main_nodes": len(main_candidate["nodes"]), "action_nodes": len(action_def["nodes"])}, separators=(",", ":")))
        return 0

    if args.phase in {"all", "action"}:
        if action_existing:
            action_id = action_existing["id"]
            api.call("PUT", f"/workflows/{action_id}", writable_workflow(action_def))
        else:
            action_id = api.call("POST", "/workflows", writable_workflow(action_def))["id"]
        api.call("POST", f"/workflows/{action_id}/activate")
        action_live = verify(api, action_id, {"Confirm DCT Action GET", "Confirm DCT Action POST", "Process Due DCT Retractions"})
        write_json(BACKUP_DIR / f"dct-action-live-{run_stamp}.json", action_live)

    if args.phase in {"all", "main"}:
        action_live = next((w for w in list_workflows(api) if w.get("name") == ACTION_WORKFLOW_NAME), None)
        if not action_live or not action_live.get("active"):
            raise RuntimeError("DCT Lead Email Actions is not active; refusing to add email buttons")
        fresh_main = api.call("GET", f"/workflows/{MAIN_WORKFLOW_ID}")
        patched = patch_main_workflow(fresh_main)
        write_json(BACKUP_DIR / f"dct-main-before-put-{run_stamp}.json", fresh_main)
        api.call("PUT", f"/workflows/{MAIN_WORKFLOW_ID}", writable_workflow(patched))
        if not fresh_main.get("active"):
            api.call("POST", f"/workflows/{MAIN_WORKFLOW_ID}/activate")
        main_live = verify(api, MAIN_WORKFLOW_ID, {"DCT Webhook", "Hash Action Token", "Log Lead to Google Sheet", "Update Lead Ads Outcome"})
        write_json(BACKUP_DIR / f"dct-main-live-{run_stamp}.json", main_live)

    print(json.dumps({"main_workflow_id": MAIN_WORKFLOW_ID, "action_workflow": ACTION_WORKFLOW_NAME, "main_nodes": len(main_candidate["nodes"]), "action_nodes": len(action_def["nodes"]), "sheet_id": SHEET_ID}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
