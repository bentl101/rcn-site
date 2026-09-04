#!/usr/bin/env python3
"""Create or update the production DCT lead-email workflow on the n8n VPS."""
from __future__ import annotations

import json
import pathlib
import urllib.request

BASE = "http://localhost:5678/api/v1"
NAME = "DCT Form Handler"
SMTP = {"smtp": {"id": "upVw1vzTxegbXV9E", "name": "Google Workspace SMTP"}}


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
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const row = (label, value) => `<tr><th style="text-align:left;padding:7px 10px;background:#f3eef6;border-bottom:1px solid #ddd">${esc(label)}</th><td style="padding:7px 10px;border-bottom:1px solid #ddd">${esc(value) || '—'}</td></tr>`;
const isQa = String(lead.qa_test || '') === '1';
const name = `${lead.first_name || ''} ${lead.last_name || ''}`.trim();
const subject = `${isQa ? '[TEST] ' : ''}New DCT lead - ${name || 'Website enquiry'}`;
const details = [
  ['Lead Order ID', lead.lead_order_id], ['Operator', lead.operator || 'Help me compare'],
  ['Name', name], ['Email', lead.email], ['Phone', lead.phone],
  ['Destination', lead.destination], ['Departure city', lead.departure_city],
  ['Travel date', lead.travel_date], ['Duration', lead.duration], ['Guests', lead.guests],
  ['Budget', lead.budget], ['Pace', lead.pace], ['Notes', lead.notes],
  ['Contact preference', lead.contact_preference], ['Source page', lead.source_page],
  ['UTM source', lead.utm_source], ['UTM medium', lead.utm_medium], ['UTM campaign', lead.utm_campaign],
  ['UTM term', lead.utm_term], ['UTM content', lead.utm_content],
  ['Click ID type', lead.click_id_type], ['Click ID', lead.click_id],
  ['Landing page', lead.landing_page], ['Referrer', lead.referrer],
  ['Device', lead.device_type], ['Time on page', lead.time_on_page], ['Submitted at', lead.submitted_at]
];
const html = `<div style="font-family:Arial,sans-serif;color:#24142f;max-width:760px"><h2 style="color:#5b247a">${esc(subject)}</h2><table style="border-collapse:collapse;width:100%">${details.map(x => row(x[0], x[1])).join('')}</table></div>`;
return [{json: {...lead, is_qa: isQa, email_subject: subject, email_html: html}}];
"""


def workflow():
    nodes = [
        {"parameters":{"httpMethod":"POST","path":"dct-form","responseMode":"onReceived","options":{}},"id":"dct-webhook","name":"DCT Webhook","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[-560,0],"webhookId":"dct-form-webhook"},
        {"parameters":{"language":"javaScript","jsCode":verify_code.strip()+"\n"},"id":"verify-token","name":"Verify Token","type":"n8n-nodes-base.code","typeVersion":2,"position":[-320,0]},
        {"parameters":{"language":"javaScript","jsCode":format_code.strip()+"\n"},"id":"format-email","name":"Format Lead Email","type":"n8n-nodes-base.code","typeVersion":2,"position":[-80,0]},
        {"parameters":{"fromEmail":"ben@copperchunk.com","toEmail":"={{ $json.is_qa ? 'btl101@gmail.com' : 'sales@discountcoachtours.ca, btl101@gmail.com' }}","subject":"={{ $json.email_subject }}","emailFormat":"html","html":"={{ $json.email_html }}","options":{"replyTo":"={{ $json.email }}"}},"id":"send-email","name":"Send Email Notification","type":"n8n-nodes-base.emailSend","typeVersion":2.1,"position":[180,0],"credentials":SMTP,"onError":"continueRegularOutput"},
    ]
    connections = {
        "DCT Webhook":{"main":[[{"node":"Verify Token","type":"main","index":0}]]},
        "Verify Token":{"main":[[{"node":"Format Lead Email","type":"main","index":0}]]},
        "Format Lead Email":{"main":[[{"node":"Send Email Notification","type":"main","index":0}]]},
    }
    return {"name":NAME,"nodes":nodes,"connections":connections,"settings":{"executionOrder":"v1","saveDataSuccessExecution":"all","saveDataErrorExecution":"all"}}


def main():
    existing = next((w for w in api("GET", "/workflows?limit=250").get("data", []) if w.get("name") == NAME), None)
    if existing:
        workflow_id = existing["id"]
        if existing.get("active"):
            api("POST", f"/workflows/{workflow_id}/deactivate")
        result = api("PUT", f"/workflows/{workflow_id}", workflow())
    else:
        result = api("POST", "/workflows", workflow())
        workflow_id = result["id"]
    active = api("POST", f"/workflows/{workflow_id}/activate")
    print(json.dumps({"id":workflow_id,"name":active.get("name"),"active":active.get("active")}, separators=(",",":")))


if __name__ == "__main__":
    main()
