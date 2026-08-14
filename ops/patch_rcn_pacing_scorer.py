#!/usr/bin/env python3
"""Patch the live RCN n8n workflow for resilient scoring and person-level pacing.

Run this script on the VPS, where ``/home/ben/.secrets`` contains ``N8N_API_KEY``.
It backs up the current workflow, patches only non-trigger nodes/connections/static
data, PUTs the result, and writes a post-PUT snapshot for audit/rollback.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import pathlib
import re
import urllib.parse
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo


N8N_BASE = "http://localhost:5678/api/v1"
WORKFLOW_ID = "zYw4HtTy1OTH7jUy"
OPENCODE_WORKFLOW_ID = "Vx31Joxwt61lRGSj"
BACKUP_DIR = pathlib.Path("/home/ben/infra/n8n/workflow-backups")
ACCOUNT_TIMEZONE = ZoneInfo("America/Toronto")


def load_key() -> str:
    for line in pathlib.Path("/home/ben/.secrets").read_text(encoding="utf-8").splitlines():
        if line.startswith("N8N_API_KEY="):
            value = line.split("=", 1)[1].strip()
            if value:
                return value
    raise RuntimeError("N8N_API_KEY is missing from /home/ben/.secrets")


class N8nApi:
    def __init__(self, key: str):
        self.key = key

    def call(self, method: str, path: str, payload=None):
        data = None
        headers = {"X-N8N-API-KEY": self.key}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(N8N_BASE + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"n8n API {method} {path} failed: HTTP {exc.code}: {body[:2000]}"
            ) from exc


def stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: pathlib.Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def node(workflow: dict, name: str) -> dict:
    matches = [item for item in workflow["nodes"] if item.get("name") == name]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one node named {name!r}, found {len(matches)}")
    return matches[0]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one {label} anchor, found {count}")
    return text.replace(old, new, 1)


def workflow_payload(workflow: dict) -> dict:
    return {
        key: copy.deepcopy(workflow[key])
        for key in ("name", "nodes", "connections", "settings", "staticData")
        if key in workflow
    }


def build_opencode_prompt_node(position: list[int]) -> dict:
    js_code = r"""
const upstream = $('Build Signals').first().json;
let source = {};
try { source = $('Codex Score Lead').first().json || {}; } catch (_) {}
const features = upstream._features || {};
const instructions = `You are scoring inbound leads for River Cruise Network, a Canadian river cruise travel agency.

Return a conservative lead quality judgment as structured JSON.

FORM STRUCTURE
- destination, phone, email, additional_info, and name are free text.
- budget, duration, guests, and operator are dropdown fields. They are constrained choices and cannot be gibberish.
- Low budget, flexible budget, short duration, or one guest are not red flags by themselves.

DESTINATION
- Strong positive: supported Europe, Egypt/Nile, or Asia river cruise intent. Examples include Rhine, Danube, Douro, Seine, Nile, Egypt, Luxor to Aswan, Mekong, Moselle, Bordeaux, Rhone, Saone, Elbe, Grand European, Christmas markets, Europe, France, Spain, Portugal, Italy, Scotland, Vietnam, and Cambodia.
- Weak or invalid: ordinary town/suburb, street address, random name, beach/package destination, ocean cruise, land tour, resort, or gibberish. Amazon, India/Ganges, Galapagos, Africa/safari, Alaska, Caribbean, and US land destinations are outside scope unless the enquiry also clearly asks for a supported river cruise.
- Undecided answers such as not sure, flexible, open, TBD, any, or open to suggestions are legitimate. Mark destination_validity as plausible when surrounding intent is coherent.

CONTACT AND VERIFICATION
- phone_valid_veriphone=false is a serious review signal, but do not suppress from phone alone.
- phone_valid_veriphone=null means verification was unavailable. Treat it as valid.
- email_mx_valid=false or email_mailbox_valid=false is a warning rather than an automatic reject if the phone is usable.
- email_free_provider=true is neutral.

TIMING
- 3-18 months out is normal. 0-2 months is late but not junk. Past dates are only a yellow flag unless paired with other junk signals.

OTHER SIGNALS
- honeypot_filled, repeated name, destination equals name, disposable email, suspicious referrer, and gibberish destination are strong junk signals.
- Prior cruise experience, specific rivers/operators, detailed notes, or a coherent undecided request are positive.

SCORING POLICY
- send_to_sales: 75-100, coherent and likely worth sales follow-up.
- review: 45-74, ambiguous, contact issue, weak destination, or mixed signals.
- suppress: 0-44, clearly spam or junk with multiple strong red flags.
- When uncertain, prefer review over suppress.`;
const schema = {
  lead_score: 'integer 0-100',
  lead_quality: 'good|questionable|bad',
  decision: 'send_to_sales|review|suppress',
  destination_validity: 'valid_river_cruise|plausible|weak|invalid',
  confidence: 'number 0-1',
  reason_short: 'one or two concise sentences',
  risk_flags: ['short_flag_names'],
  sales_note: 'short practical note for the sales caller',
};
const prompt = [
  instructions,
  'LEAD FEATURES JSON:', JSON.stringify(features, null, 2),
  'Return ONLY a valid JSON object with exactly these fields:', JSON.stringify(schema, null, 2),
].filter(Boolean).join('\n\n');
return [{json:{
  prompt,
  model:'kimi-k3',
  system:'Follow the scoring policy exactly. Return JSON only, without Markdown fences or commentary.',
  max_tokens:4096,
  temperature:1,
  _codex_error:String(source.error || '').slice(0,1000),
}}];
""".strip()
    return {
        "parameters": {"language": "javaScript", "jsCode": js_code + "\n"},
        "id": "rcn-build-opencode-fallback",
        "name": "Build OpenCode Fallback",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
    }


def execute_opencode_node(position: list[int]) -> dict:
    return {
        "parameters": {
            "workflowId": {
                "__rl": True,
                "value": OPENCODE_WORKFLOW_ID,
                "mode": "list",
                "cachedResultName": "OpenCode Go - Reusable Model Runner",
            },
            "workflowInputs": {
                "mappingMode": "defineBelow",
                "value": {
                    "prompt": "={{ $json.prompt }}",
                    "model": "={{ $json.model }}",
                    "system": "={{ $json.system }}",
                    "max_tokens": "={{ $json.max_tokens }}",
                    "temperature": "={{ $json.temperature }}",
                },
                "matchingColumns": [],
                "schema": [
                    {"id": "prompt", "displayName": "prompt", "required": False, "display": True, "canBeUsedToMatch": True, "type": "string"},
                    {"id": "model", "displayName": "model", "required": False, "display": True, "canBeUsedToMatch": True, "type": "string"},
                    {"id": "system", "displayName": "system", "required": False, "display": True, "canBeUsedToMatch": True, "type": "string"},
                    {"id": "max_tokens", "displayName": "max_tokens", "required": False, "display": True, "canBeUsedToMatch": True, "type": "number"},
                    {"id": "temperature", "displayName": "temperature", "required": False, "display": True, "canBeUsedToMatch": True, "type": "number"},
                ],
                "attemptToConvertTypes": False,
                "convertFieldsToString": False,
            },
            "mode": "once",
            "options": {},
        },
        "id": "rcn-call-opencode-fallback",
        "name": "Call OpenCode Go Fallback",
        "type": "n8n-nodes-base.executeWorkflow",
        "typeVersion": 1.3,
        "position": position,
        "onError": "continueErrorOutput",
    }


def normalize_opencode_node(position: list[int]) -> dict:
    js_code = r"""
const response = $input.first().json || {};
let text = String(response.content || '').trim();
text = text.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '').trim();
if (!text) throw new Error('OpenCode Go returned no content');
let parsed;
try { parsed = JSON.parse(text); }
catch (error) { throw new Error(`OpenCode Go returned invalid JSON: ${error.message}`); }
const required = ['lead_score','lead_quality','decision','destination_validity','confidence','reason_short','risk_flags','sales_note'];
for (const key of required) if (!(key in parsed)) throw new Error(`OpenCode Go response missing ${key}`);
const content = JSON.stringify(parsed);
return [{json:{
  choices:[{message:{content}}],
  _scorer_model:`opencode-go:${response.model || 'kimi-k3'}`,
  _opencode:{provider:response.provider || 'opencode-go',finish_reason:response.finish_reason || null,usage:response.usage || {}},
}}];
""".strip()
    return {
        "parameters": {"language": "javaScript", "jsCode": js_code + "\n"},
        "id": "rcn-normalize-opencode-fallback",
        "name": "Normalize OpenCode Fallback",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": position,
        "onError": "continueErrorOutput",
    }


def patch_codex(workflow: dict) -> None:
    codex = node(workflow, "Codex Score Lead")
    codex["parameters"]["model"] = "gpt-5.5"
    codex["parameters"]["reasoningEffort"] = "high"
    codex["parameters"]["codexBin"] = "/home/node/.n8n/codex/codex-runner-isolated"
    codex.setdefault("parameters", {}).setdefault("options", {})["timeoutSeconds"] = 180


def patch_parse_labels(workflow: dict) -> None:
    parse = node(workflow, "Parse Score")
    code = parse["parameters"]["jsCode"]
    code = replace_once(
        code,
        "if (!content) throw new Error('no content in DeepSeek response');",
        "if (!content) throw new Error('no content in scorer response');",
        "scorer empty-content label",
    )
    code = replace_once(
        code,
        "scorer_model: (wrapped && wrapped._scorer_model) || 'deepseek-v4-flash',",
        "scorer_model: (wrapped && wrapped._scorer_model) || 'unknown-scorer',",
        "default scorer model label",
    )
    parse["parameters"]["jsCode"] = code

    error_node = node(workflow, "Normalize Scorer Error")
    error_code = error_node["parameters"]["jsCode"]
    error_code = error_code.replace("Both Codex primary and DeepSeek fallback failed.", "Both Codex primary and OpenCode Go fallback failed.")
    error_code = error_code.replace("Codex and DeepSeek were unavailable.", "Codex and OpenCode Go were unavailable.")
    error_code = error_code.replace("fail-open:codex-deepseek", "fail-open:codex-opencode-go")
    error_node["parameters"]["jsCode"] = error_code


def patch_campaign_classification(workflow: dict) -> None:
    assign = node(workflow, "Assign Daily Lead Number")
    code = assign["parameters"]["jsCode"]
    old_daily_identity = r"""const email = String(body.email || '').trim().toLowerCase();
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
    new_daily_identity = r"""store.rcnDailyLeadCounter.seenAliases ||= {};
const email = String(body.email || '').trim().toLowerCase();
const phone = String(body.phone || '').replace(/\D+/g, '');
const aliases = [email ? `e:${email}` : '', phone ? `p:${phone}` : ''].filter(Boolean);
const matchedAlias = aliases.find((alias) =>
  store.rcnDailyLeadCounter.seenAliases[alias] || store.rcnDailyLeadCounter.seen[alias]
);
let dailyUniqueNumber = matchedAlias
  ? (store.rcnDailyLeadCounter.seenAliases[matchedAlias] || store.rcnDailyLeadCounter.seen[matchedAlias])
  : 0;

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
        code = replace_once(
            code, old_daily_identity, new_daily_identity,
            "daily lead email/phone alias identity",
        )
    code = replace_once(
        code,
        'const netMap = { x: "P-Max", g: "Search", s: "Search", d: "P-Max", ytv: "P-Max" };',
        'const netMap = { x: "Paid", g: "Search", s: "Search", d: "Display", ytv: "Video" };',
        "campaign network fallback map",
    )
    code = replace_once(
        code,
        '  x: "Performance Max",',
        '  x: "Cross-network / automated campaign",',
        "Google network x display label",
    )
    code = replace_once(
        code,
        'const campaign = campaigns[campaignId];',
        'const cachedCampaign = /^\\d+$/.test(campaignId) ? (store.rcnCampaignMetadata?.[campaignId] || null) : null;\nconst campaign = cachedCampaign || campaigns[campaignId];',
        "shared campaign metadata cache",
    )
    assign["parameters"]["jsCode"] = code


PACING_JS = r"""
const b = {...($json.body || {})};
const store = $getWorkflowStaticData('global');
const tz = 'America/Toronto';
const raw = String(b.submitted_at || '').slice(0, 19);
const date = new Intl.DateTimeFormat('en-CA', {
  timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit',
}).format(raw ? new Date(raw.replace(' ', 'T') + 'Z') : new Date());

if (!store.rcnDailyPacingCounter || store.rcnDailyPacingCounter.date !== date) {
  store.rcnDailyPacingCounter = {date, seenPeople: {}, seenAliases: {}, seenClicks: {}, uniqueCount: 0, campaigns: {}};
}
const counter = store.rcnDailyPacingCounter;
counter.seenPeople ||= {};
counter.seenAliases ||= {};
counter.seenClicks ||= counter.seen || {};
counter.campaigns ||= {};
counter.uniqueCount ||= 0;

// Migrate a pre-alias counter in place. Saved people used email as the old
// canonical key, so mapping each known email to itself prevents a same-day
// repeat from being counted again immediately after deployment.
if (Object.keys(counter.seenAliases).length === 0) {
  for (const key of Object.keys(counter.seenPeople)) {
    if (/^[ep]:/.test(key)) counter.seenAliases[key] = key;
  }
}

const campaignIdRaw = String(b.utm_id || b.utm_campaign || '').trim();
const campaignId = /^\d+$/.test(campaignIdRaw) ? campaignIdRaw : '';
const network = String(b.network || '').toLowerCase();
const legacyCampaignLabels = {
  '17692419316':'Search','17701562522':'Search','17748453978':'Search','17748453990':'Search',
  '17748453996':'Search','17748454008':'Search','17748454209':'Search','17757640502':'Search',
  '17834302943':'Search','17935071531':'Search','17935071543':'Search','17935071729':'Search',
  '17936430673':'Search','17936430898':'Search','17936430913':'Search','17936430922':'Search',
  '17942589257':'Search','17942589746':'Search','17942589767':'Search','17942589824':'Search',
  '19580607759':'Search','19703576153':'Search','19772611609':'Search','19772626285':'Search',
  '19793144771':'Search','19793957509':'Search','20296814851':'Search','20303260471':'Display',
  '23613244727':'Search','23885505079':'P-Max',
};
const cachedCampaign = store.rcnCampaignMetadata?.[campaignId] || {};
const provisionalLabel = cachedCampaign.label || legacyCampaignLabels[campaignId]
  || (network === 'x' ? 'Paid' : (network === 'd' ? 'Display' : (network === 'ytv' ? 'Video' : 'Search')));
const campaignKey = campaignId ? `id:${campaignId}` : `channel:${provisionalLabel}`;
counter.campaigns[campaignKey] ||= {
  campaignId,
  label: provisionalLabel,
  name: String(cachedCampaign.name || b.campaign_name || ''),
  uniqueCount: 0,
  uniqueClicks: 0,
};

const email = String(b.email || '').trim().toLowerCase();
const phone = String(b.phone || '').replace(/\D+/g, '');
const aliases = [email ? `e:${email}` : '', phone ? `p:${phone}` : ''].filter(Boolean);
const matchedAlias = aliases.find((alias) => counter.seenAliases[alias] || counter.seenPeople[alias]);
const personKey = matchedAlias
  ? (counter.seenAliases[matchedAlias] || matchedAlias)
  : (aliases[0] || `o:${b.lead_order_id || Date.now()}`);
const clickKey = `${String(b.click_id_type || 'gclid').toLowerCase()}:${String(b.click_id || '').trim()}`;
const freshPerson = !counter.seenPeople[personKey];
const freshClick = Boolean(b.click_id) && !counter.seenClicks[clickKey];

if (freshPerson) {
  counter.seenPeople[personKey] = campaignKey;
  counter.uniqueCount += 1;
  counter.campaigns[campaignKey].uniqueCount += 1;
}
for (const alias of aliases) counter.seenAliases[alias] = personKey;
if (freshPerson && freshClick) {
  counter.seenClicks[clickKey] = campaignKey;
  counter.campaigns[campaignKey].uniqueClicks = Number(counter.campaigns[campaignKey].uniqueClicks || 0) + 1;
}

b.pacing = {
  date,
  campaignKey,
  label: counter.campaigns[campaignKey].label,
  campaignId,
  fresh: freshPerson,
  freshPerson,
  freshClick,
  campaignLeads: counter.campaigns[campaignKey].uniqueCount,
  totalLeads: counter.uniqueCount,
  campaignClicks: counter.campaigns[campaignKey].uniqueClicks,
};
// A repeated person remains visible in saved execution data but does not fetch
// spend or send another pacing email.
return freshPerson ? [{json:{...$json, body:b}}] : [];
""".strip() + "\n"


def patch_pacing(workflow: dict) -> None:
    node(workflow, "Build Lead Pacing Snapshot")["parameters"]["jsCode"] = PACING_JS

    pacing_email = node(workflow, "Build Pacing Email")
    code = pacing_email["parameters"]["jsCode"]
    replacements = (
        ("const countLabel = (count) => `${count} unique qualifying ${count === 1 ? 'click' : 'clicks'}`;",
         "const countLabel = (count) => `${count} unique qualifying ${count === 1 ? 'person' : 'people'}`;"),
        ("const state = p.fresh ? 'new unique qualifying click' : 'repeat click - denominator unchanged';",
         "const state = p.freshPerson ? 'new unique qualifying person' : 'repeat person - denominator unchanged';"),
        ("Provisional CPL = current Google Ads spend divided by unique qualifying Google click IDs from send-to-sales leads.",
         "Provisional CPL = current Google Ads spend divided by unique qualifying people from send-to-sales leads. Distinct click IDs remain an Ads-credit diagnostic."),
        ("qualifying click #${p.campaignLeads || ''}", "qualifying person #${p.campaignLeads || ''}"),
    )
    for old, new in replacements:
        code = replace_once(code, old, new, f"pacing email text {old[:30]}")
    pacing_email["parameters"]["jsCode"] = code

    spend = node(workflow, "Get Current Google Ads Spend")
    spend_body = spend["parameters"]["jsonBody"]
    spend_body = replace_once(
        spend_body,
        "SELECT campaign.id, campaign.name, metrics.cost_micros, metrics.clicks FROM campaign",
        "SELECT campaign.id, campaign.name, campaign.advertising_channel_type, metrics.cost_micros, metrics.clicks FROM campaign",
        "Google Ads pacing campaign metadata query",
    )
    spend["parameters"]["jsonBody"] = spend_body

    # The fetched Ads row is authoritative for any current or future campaign.
    # It updates the generic campaign-key bucket before the email is rendered.
    code = pacing_email["parameters"]["jsCode"]
    anchor = "const rows = Array.isArray($json.results) ? $json.results : [];\n"
    metadata = r"""
const rows = Array.isArray($json.results) ? $json.results : [];
const channelLabels = Object.freeze({
  SEARCH: 'Search', PERFORMANCE_MAX: 'P-Max', DEMAND_GEN: 'Demand Gen',
  DISPLAY: 'Display', VIDEO: 'Video', SHOPPING: 'Shopping',
  MULTI_CHANNEL: 'Multi-channel', LOCAL: 'Local', APP: 'App',
  SMART: 'Smart', HOTEL: 'Hotel', TRAVEL: 'Travel',
  LOCAL_SERVICES: 'Local Services', DISCOVERY: 'Demand Gen',
});
const campaignRow = rows.find((row) => String(row.campaign?.id || '') === String(p.campaignId || ''));
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
  const authoritativeLabel = labelForChannel(channel, p.label);
  p.label = authoritativeLabel;
  p.campaignName = String(campaignRow.campaign?.name || '');
  const bucket = store.rcnDailyPacingCounter?.campaigns?.[p.campaignKey];
  if (bucket) {
    bucket.label = p.label;
    bucket.name = p.campaignName;
  }
}
""".strip() + "\n"
    code = replace_once(code, anchor, metadata, "pacing Ads metadata enrichment")
    code = replace_once(
        code,
        "const name = `${b.first_name || ''} ${b.last_name || ''}`.trim() || 'New lead';",
        "const name = `${b.first_name || ''} ${b.last_name || ''}`.trim() || 'New lead';\nconst campaignDisplay = p.campaignName ? `${p.label}: ${p.campaignName}` : p.label;",
        "pacing campaign display",
    )
    code = code.replace("<b>${name}</b> - ${p.label} - ${state}", "<b>${name}</b> - ${campaignDisplay} - ${state}")
    pacing_email["parameters"]["jsCode"] = code


def execution_node(run_data: dict, name: str) -> dict | None:
    try:
        return run_data[name][0]["data"]["main"][0][0]["json"]
    except (KeyError, IndexError, TypeError):
        return None


def account_date(body: dict) -> str | None:
    raw = str(body.get("submitted_at") or "")[:19]
    if not raw:
        return None
    try:
        instant = dt.datetime.fromisoformat(raw.replace(" ", "T")).replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None
    return instant.astimezone(ACCOUNT_TIMEZONE).date().isoformat()


def person_key(body: dict) -> str:
    email = str(body.get("email") or "").strip().lower()
    if email:
        return f"e:{email}"
    phone = re.sub(r"\D+", "", str(body.get("phone") or ""))
    if phone:
        return f"p:{phone}"
    return f"o:{body.get('lead_order_id') or ''}"


def phone_is_quarantined(body: dict, features: dict) -> bool:
    """Return the live policy result for missing or definitively invalid phones.

    Veriphone ``true`` is authoritative for international numbers that do not
    match the local NANP shape check. A verifier outage remains fail-open only
    when the deterministic shape check passes.
    """
    digits = re.sub(r"\D+", "", str(body.get("phone") or ""))
    if not digits:
        return True
    if features.get("phone_fictional") is True or features.get("phone_repeating") is True:
        return True
    verified = features.get("phone_valid_veriphone")
    if verified is False:
        return True
    return verified is not True and features.get("phone_valid_shape") is not True


def provisional_campaign_label(body: dict) -> str:
    label = str(body.get("campaign_label") or "").strip()
    if label:
        return label
    network = str(body.get("network") or "").strip().lower()
    if network == "x":
        return "Paid"
    if network == "d":
        return "Display"
    if network == "ytv":
        return "Video"
    return "Search"


def campaign_key(body: dict) -> str:
    campaign_id = str(body.get("utm_id") or body.get("utm_campaign") or "").strip()
    return f"id:{campaign_id}" if campaign_id.isdigit() else f"channel:{provisional_campaign_label(body)}"


def rebuild_today_people(api: N8nApi, workflow: dict) -> dict:
    """Rebuild today's pacing state from saved qualifying executions.

    This prevents a stale workflow snapshot or a hard-coded person list from
    clobbering leads that arrive while the patch is being prepared.
    """
    today = dt.datetime.now(ACCOUNT_TIMEZONE).date().isoformat()
    executions = []
    cursor = None
    for _ in range(20):
        query = f"workflowId={WORKFLOW_ID}&limit=250&includeData=true"
        if cursor:
            query += "&cursor=" + urllib.parse.quote(str(cursor), safe="")
        response = api.call("GET", "/executions?" + query)
        rows = response.get("data", [])
        executions.extend(rows)
        cursor = response.get("nextCursor")
        if not cursor or not rows:
            break
    qualifying: list[tuple[str, dict]] = []
    for execution in executions:
        run_data = execution.get("data", {}).get("resultData", {}).get("runData", {})
        source = execution_node(run_data, "Build Signals") or execution_node(run_data, "Build Features")
        parsed = execution_node(run_data, "Parse Score")
        if not source or not parsed:
            continue
        body = source.get("body") or {}
        features = source.get("_features") or {}
        parsed_body = parsed.get("body") or {}
        if account_date(body) != today:
            continue
        if parsed_body.get("decision") != "send_to_sales" or not body.get("click_id"):
            continue
        if phone_is_quarantined(body, features):
            continue
        qualifying.append((str(body.get("submitted_at") or ""), body))

    seen_people: dict[str, str] = {}
    seen_aliases: dict[str, str] = {}
    seen_clicks: dict[str, str] = {}
    campaigns: dict[str, dict] = {}
    for _, body in sorted(qualifying, key=lambda item: item[0]):
        label = provisional_campaign_label(body)
        key = campaign_key(body)
        campaign_id = str(body.get("utm_id") or body.get("utm_campaign") or "").strip()
        campaigns.setdefault(key, {
            "campaignId": campaign_id,
            "label": label,
            "name": str(body.get("campaign_name") or ""),
            "uniqueCount": 0,
            "uniqueClicks": 0,
        })
        email = str(body.get("email") or "").strip().lower()
        phone = re.sub(r"\D+", "", str(body.get("phone") or ""))
        aliases = [value for value in (
            f"e:{email}" if email else "", f"p:{phone}" if phone else ""
        ) if value]
        pkey = next((seen_aliases[alias] for alias in aliases if alias in seen_aliases), None)
        pkey = pkey or (aliases[0] if aliases else person_key(body))
        if pkey not in seen_people:
            seen_people[pkey] = key
            campaigns[key]["uniqueCount"] += 1
        for alias in aliases:
            seen_aliases[alias] = pkey
        click_id = str(body.get("click_id") or "").strip()
        click_type = str(body.get("click_id_type") or "gclid").strip().lower()
        ckey = f"{click_type}:{click_id}"
        if click_id and ckey not in seen_clicks:
            seen_clicks[ckey] = key
            campaigns[key]["uniqueClicks"] += 1

    counter = {
        "date": today,
        "seenPeople": seen_people,
        "seenAliases": seen_aliases,
        "seenClicks": seen_clicks,
        "uniqueCount": len(seen_people),
        "campaigns": campaigns,
    }
    workflow.setdefault("staticData", {}).setdefault("global", {})[
        "rcnDailyPacingCounter"
    ] = counter
    return counter


def patch_connections(workflow: dict) -> None:
    connections = workflow["connections"]
    connections["Codex Score Lead"] = {
        "main": [
            [{"node": "Parse Score", "type": "main", "index": 0}],
            [{"node": "Build OpenCode Fallback", "type": "main", "index": 0}],
        ]
    }
    connections["Build OpenCode Fallback"] = {
        "main": [[{"node": "Call OpenCode Go Fallback", "type": "main", "index": 0}]]
    }
    connections["Call OpenCode Go Fallback"] = {
        "main": [
            [{"node": "Normalize OpenCode Fallback", "type": "main", "index": 0}],
            [{"node": "Normalize Scorer Error", "type": "main", "index": 0}],
        ]
    }
    connections["Normalize OpenCode Fallback"] = {
        "main": [
            [{"node": "Parse Score", "type": "main", "index": 0}],
            [{"node": "Normalize Scorer Error", "type": "main", "index": 0}],
        ]
    }
    connections.pop("Call DeepSeek", None)


def patch(workflow: dict) -> dict:
    result = copy.deepcopy(workflow)
    deepseek = node(result, "Call DeepSeek")
    result["nodes"].remove(deepseek)
    result["nodes"].extend([
        build_opencode_prompt_node([80, 640]),
        execute_opencode_node([320, 640]),
        normalize_opencode_node([560, 640]),
    ])
    patch_codex(result)
    patch_parse_labels(result)
    patch_campaign_classification(result)
    patch_pacing(result)
    patch_connections(result)
    return result


def validate(workflow: dict) -> None:
    names = [item["name"] for item in workflow["nodes"]]
    if len(names) != len(set(names)):
        raise RuntimeError("Patched workflow contains duplicate node names")
    for removed in ("Call DeepSeek",):
        if removed in names or removed in workflow["connections"]:
            raise RuntimeError(f"Removed node {removed!r} still exists")
    for required in (
        "Codex Score Lead", "Build OpenCode Fallback", "Call OpenCode Go Fallback",
        "Normalize OpenCode Fallback", "Parse Score", "Build Lead Pacing Snapshot",
    ):
        if required not in names:
            raise RuntimeError(f"Required node {required!r} is missing")
    if node(workflow, "Webhook")["parameters"].get("path") != "rcn-form":
        raise RuntimeError("Webhook path changed unexpectedly")
    query = node(workflow, "Get Current Google Ads Spend")["parameters"]["jsonBody"]
    if "campaign.advertising_channel_type" not in query:
        raise RuntimeError("Google Ads channel metadata was not added to the pacing query")


def main() -> int:
    api = N8nApi(load_key())
    current = api.call("GET", f"/workflows/{WORKFLOW_ID}")
    run_stamp = stamp()
    before = BACKUP_DIR / f"rcn-before-codex-opencode-pacing-{run_stamp}.json"
    after = BACKUP_DIR / f"rcn-after-codex-opencode-pacing-{run_stamp}.json"
    write_json(before, current)
    patched = patch(current)
    counter = rebuild_today_people(api, patched)
    validate(patched)
    updated = api.call("PUT", f"/workflows/{WORKFLOW_ID}", workflow_payload(patched))
    fresh = api.call("GET", f"/workflows/{WORKFLOW_ID}")
    validate(fresh)
    write_json(after, fresh)
    print(json.dumps({
        "workflow_id": WORKFLOW_ID,
        "active": fresh.get("active"),
        "version_id": fresh.get("versionId"),
        "before_backup": str(before),
        "after_backup": str(after),
        "updated_at": updated.get("updatedAt"),
        "nodes": len(fresh.get("nodes", [])),
        "pacing_counter": {
            "date": counter["date"],
            "uniqueCount": counter["uniqueCount"],
            "campaigns": counter["campaigns"],
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
