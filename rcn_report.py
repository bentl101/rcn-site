#!/usr/bin/env python3
"""
RCN scheduled reports + health monitor. Cron-driven on the VPS.

Modes:
  --health   daily heartbeat + alerts (Ads API version OK? any failed uploads?)
  --daily    yesterday's leads + spend
  --weekly   last 7 days summary + physical-region performance
  --monthly  previous calendar month summary + physical-region performance

Reads all creds from ~/.secrets. Emails reports via Google Workspace SMTP. Daily and
health emails stay private to Ben; weekly and monthly reviews also go to the client.
Pure stdlib — no external deps. Google Ads API version is pinned below; when it
gets deprecated the --health check will alert and you bump ADS_VERSION here +
in the n8n nodes + conversion_worker.py + recover_braid.py.
"""
import html as html_lib
import os, sys, json, smtplib, urllib.request, urllib.parse, urllib.error
from datetime import date, datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from zoneinfo import ZoneInfo

CID              = '5306933986'                 # River Cruise Network
WORKFLOW_ID      = 'zYw4HtTy1OTH7jUy'
ACTION_WORKFLOW_ID = 'LpJaof03qyAbSGip'
ADS_VERSION      = 'v24'                         # bump when --health reports UNSUPPORTED_VERSION
REPORT_TO        = ('btl101@gmail.com',)
CLIENT_REPORT_TO = ('sales@rivercruisenetwork.com',)
WEEKLY_REPORT_TO = REPORT_TO + CLIENT_REPORT_TO
MONTHLY_REPORT_TO = REPORT_TO + CLIENT_REPORT_TO
REPORT_FROM      = 'hello@copperchunk.com'
# Good leads upload to one of two UPLOAD_CLICKS actions (split by click type):
#   'offline (upload)'        — gclid (count One)
#   'offline (upload) - iOS'  — gbraid/wbraid (count Every)
# Sum both for "good leads credited in Ads".
OFFLINE_ACTIONS = ['offline (upload)', 'offline (upload) - iOS']
LEGACY_ACTION   = 'Legacy submit lead form'  # every form completion (client-side baseline)
ACCOUNT_TZ      = ZoneInfo('America/Toronto')

def account_today():
    return datetime.now(ACCOUNT_TZ).date()

def submitted_account_date(body):
    """Convert the UTC form timestamp to the Google Ads account's calendar day."""
    raw = str((body or {}).get('submitted_at') or '').strip()
    if not raw:
        return None
    try:
        submitted = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if submitted.tzinfo is None:
            submitted = submitted.replace(tzinfo=timezone.utc)
        return submitted.astimezone(ACCOUNT_TZ).date()
    except ValueError:
        return None

def offline_total(conv):
    return sum(conv.get(n, 0) for n in OFFLINE_ACTIONS)

def load_secrets():
    s = {}
    for line in open(os.path.expanduser('~/.secrets')):
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1); s[k] = v.strip().strip('"').strip("'")
    return s

S   = load_secrets()
MCC = S.get('GOOGLE_ADS_MANAGER_ID', '3814278874')

# ───────────────────────── Google Ads ─────────────────────────
def ads_token():
    data = urllib.parse.urlencode({
        'client_id': S['GOOGLE_ADS_CLIENT_ID'], 'client_secret': S['GOOGLE_ADS_CLIENT_SECRET'],
        'refresh_token': S['GOOGLE_ADS_REFRESH_TOKEN'], 'grant_type': 'refresh_token',
    }).encode()
    return json.load(urllib.request.urlopen(
        urllib.request.Request('https://oauth2.googleapis.com/token', data=data)))['access_token']

def ads_search(tok, gaql):
    out, body = [], {'query': gaql}
    while True:
        req = urllib.request.Request(
            f'https://googleads.googleapis.com/{ADS_VERSION}/customers/{CID}/googleAds:search',
            data=json.dumps(body).encode())
        req.add_header('Authorization', f'Bearer {tok}')
        req.add_header('developer-token', S['GOOGLE_ADS_DEVELOPER_TOKEN'])
        req.add_header('login-customer-id', MCC)
        req.add_header('Content-Type', 'application/json')
        r = json.load(urllib.request.urlopen(req))
        out += r.get('results', [])
        if not r.get('nextPageToken'): return out
        body['pageToken'] = r['nextPageToken']

def ads_metrics(tok, start, end):
    rows = ads_search(tok, "SELECT metrics.cost_micros, metrics.clicks, metrics.impressions, "
        f"metrics.conversions FROM customer WHERE segments.date BETWEEN '{start}' AND '{end}'")
    cost = clicks = impr = 0
    for r in rows:
        m = r['metrics']
        cost += int(m.get('costMicros', 0)); clicks += int(m.get('clicks', 0)); impr += int(m.get('impressions', 0))
    return {'cost': cost / 1e6, 'clicks': clicks, 'impressions': impr}

def ads_conv_by_action(tok, start, end):
    rows = ads_search(tok, "SELECT segments.conversion_action_name, metrics.all_conversions "
        f"FROM customer WHERE segments.date BETWEEN '{start}' AND '{end}'")
    d = {}
    for r in rows:
        nm = r['segments']['conversionActionName']
        d[nm] = d.get(nm, 0) + float(r['metrics'].get('allConversions', 0))
    return d

def _physical_region_key(row):
    """Prefer a province-level geo; fall back to the user's country."""
    province = row.get('segments', {}).get('geoTargetProvince')
    if province:
        return province
    country_id = row.get('userLocationView', {}).get('countryCriterionId')
    if country_id:
        return f'geoTargetConstants/{country_id}'
    return '__unknown__'

def ads_geo_names(tok, resource_names):
    """Resolve Google Ads geo-target resource names to reader-friendly labels."""
    clean = sorted({
        value for value in resource_names
        if value.startswith('geoTargetConstants/') and value.rsplit('/', 1)[-1].isdigit()
    })
    resolved = {}
    for offset in range(0, len(clean), 100):
        batch = clean[offset:offset + 100]
        quoted = ', '.join(f"'{value}'" for value in batch)
        rows = ads_search(tok,
            "SELECT geo_target_constant.resource_name, geo_target_constant.name, "
            "geo_target_constant.country_code, geo_target_constant.target_type "
            f"FROM geo_target_constant WHERE geo_target_constant.resource_name IN ({quoted})")
        for row in rows:
            geo = row.get('geoTargetConstant', {})
            resource_name = geo.get('resourceName')
            if resource_name:
                resolved[resource_name] = {
                    'name': geo.get('name') or resource_name,
                    'country_code': geo.get('countryCode') or '',
                    'target_type': geo.get('targetType') or '',
                }
    return resolved

def ads_region_performance(tok, start, end):
    """Return Ads performance by the user's physical province/region.

    Traffic metrics and qualified offline conversions are queried separately so
    conversion-action segmentation cannot duplicate spend, clicks, or impressions.
    """
    traffic_rows = ads_search(tok,
        "SELECT user_location_view.country_criterion_id, segments.geo_target_province, "
        "metrics.cost_micros, metrics.clicks, metrics.impressions "
        "FROM user_location_view "
        f"WHERE segments.date BETWEEN '{start}' AND '{end}' AND metrics.impressions > 0")
    action_names = ', '.join(f"'{name}'" for name in OFFLINE_ACTIONS)
    conversion_rows = ads_search(tok,
        "SELECT user_location_view.country_criterion_id, segments.geo_target_province, "
        "segments.conversion_action_name, metrics.all_conversions "
        "FROM user_location_view "
        f"WHERE segments.date BETWEEN '{start}' AND '{end}' "
        f"AND segments.conversion_action_name IN ({action_names}) "
        "AND metrics.all_conversions > 0")

    grouped = {}
    def bucket(key):
        return grouped.setdefault(key, {
            'resource_name': key, 'cost': 0.0, 'clicks': 0,
            'impressions': 0, 'good_leads': 0.0,
        })

    for row in traffic_rows:
        item = bucket(_physical_region_key(row))
        metrics = row.get('metrics', {})
        item['cost'] += int(metrics.get('costMicros', 0)) / 1e6
        item['clicks'] += int(metrics.get('clicks', 0))
        item['impressions'] += int(metrics.get('impressions', 0))
    for row in conversion_rows:
        item = bucket(_physical_region_key(row))
        item['good_leads'] += float(row.get('metrics', {}).get('allConversions', 0))

    names = ads_geo_names(tok, grouped.keys())
    regions = []
    for key, item in grouped.items():
        meta = names.get(key, {})
        if key == '__unknown__':
            label = 'Unknown physical region'
        else:
            label = meta.get('name') or key.rsplit('/', 1)[-1]
            country_code = meta.get('country_code') or ''
            if meta.get('target_type') == 'Country':
                label += ' (province unavailable)'
            elif country_code and country_code != 'CA':
                label += f', {country_code}'
        item['label'] = label
        item['country_code'] = meta.get('country_code') or ''
        regions.append(item)
    regions.sort(key=lambda item: (-item['cost'], item['label']))
    return regions

# ───────────────────────── n8n leads ─────────────────────────
def n8n_execs(workflow_id=WORKFLOW_ID, limit=250, max_pages=None):
    """Fetch saved executions with cursor pagination (up to limit * max_pages)."""
    if max_pages is None:
        max_pages = 20 if workflow_id == WORKFLOW_ID else 2
    out, cursor = [], None
    for _ in range(max_pages):
        query = {
            'workflowId': workflow_id, 'limit': str(limit), 'includeData': 'true',
        }
        if cursor:
            query['cursor'] = cursor
        req = urllib.request.Request(
            'http://localhost:5678/api/v1/executions?' + urllib.parse.urlencode(query))
        req.add_header('X-N8N-API-KEY', S['N8N_API_KEY'])
        page = json.load(urllib.request.urlopen(req))
        rows = page.get('data', [])
        out.extend(rows)
        cursor = page.get('nextCursor')
        if not cursor or not rows:
            break
    return out


def n8n_workflow(workflow_id):
    req = urllib.request.Request(f'http://localhost:5678/api/v1/workflows/{workflow_id}')
    req.add_header('X-N8N-API-KEY', S['N8N_API_KEY'])
    return json.load(urllib.request.urlopen(req))

def _node(rd, name):
    try: return rd[name][0]['data']['main'][0][0]['json']
    except Exception: return None

def _upload_accepted(rd):
    """True = Google accepted the upload, False = rejected (fake/test gclid, etc.),
    None = the Upload node didn't run / no data captured."""
    up = rd.get('Upload Click Conversion')
    if not up: return None
    try: r = up[0]['data']['main'][0][0]['json']
    except Exception: return None
    if r and r.get('results') and not r.get('partialFailureError') and not r.get('error'):
        return True
    return False

def _person_key(body):
    """Stable daily person key shared with live pacing: email, phone, then order ID."""
    email = str((body or {}).get('email') or '').strip().lower()
    if email:
        return f'e:{email}'
    phone = ''.join(ch for ch in str((body or {}).get('phone') or '') if ch.isdigit())
    if phone:
        return f'p:{phone}'
    return f'o:{(body or {}).get("lead_order_id") or ""}'


def _phone_is_quarantined(body, features):
    """Mirror the live deterministic missing/invalid-phone policy."""
    digits = ''.join(ch for ch in str((body or {}).get('phone') or '') if ch.isdigit())
    if not digits:
        return True
    if features.get('phone_fictional') is True or features.get('phone_repeating') is True:
        return True
    verified = features.get('phone_valid_veriphone')
    if verified is False:
        return True
    return verified is not True and features.get('phone_valid_shape') is not True


def _email_is_invalid(body, features):
    email = str((body or {}).get('email') or '').strip()
    shape_ok = '@' in email and '.' in email.rsplit('@', 1)[-1]
    return (not shape_ok
            or features.get('email_mx_valid') is False
            or features.get('email_mailbox_valid') is False
            or features.get('email_disposable') is True
            or features.get('email_disposable_reoon') is True)


def _effective_decision(body, features, parsed_body):
    """Apply today's contact policy to immutable historical execution data."""
    original = str((parsed_body or {}).get('decision') or '?')
    if not _phone_is_quarantined(body, features):
        return original
    if _email_is_invalid(body, features):
        return 'suppress'
    # Do not rescue an independently suppressed spam lead; only quarantine
    # historical sends/reviews that had an invalid or missing phone.
    return 'review' if original in {'send_to_sales', 'review'} else original


def _person_aliases(body):
    """All stable contact aliases available for one submission."""
    aliases = []
    email = str((body or {}).get('email') or '').strip().lower()
    phone = ''.join(ch for ch in str((body or {}).get('phone') or '') if ch.isdigit())
    if email:
        aliases.append(f'e:{email}')
    if phone:
        aliases.append(f'p:{phone}')
    return aliases or [_person_key(body)]


def _canonical_person(body, alias_map):
    aliases = _person_aliases(body)
    canonical = next((alias_map[a] for a in aliases if a in alias_map), aliases[0])
    for alias in aliases:
        alias_map[alias] = canonical
    return canonical

def _manual_upload_outcomes(action_execs, start_d, end_d, aliases=None):
    """Return person/day outcomes for review leads approved through email actions.

    Existing automatic uploads do not traverse Parse Manual Upload Result, so
    this adds only genuinely recovered/manual uploads and cannot double-count a
    normal send_to_sales execution.
    """
    outcomes, aliases = {}, (aliases if aliases is not None else {})
    for execution in action_execs or ():
        rd = execution.get('data', {}).get('resultData', {}).get('runData', {})
        result = _node(rd, 'Parse Manual Upload Result')
        row = _node(rd, 'Read Scoring for Event')
        if not result or not row:
            continue
        dd = submitted_account_date(row)
        if dd is None or not (start_d <= dd <= end_d):
            continue
        state = str(result.get('manual_action') or '')
        if state not in {'good_uploaded', 'good_upload_failed'}:
            continue
        person = (dd, _canonical_person(row, aliases))
        if state == 'good_uploaded':
            outcomes[person] = 'accepted'
        elif outcomes.get(person) != 'accepted':
            outcomes[person] = 'rejected'
    return outcomes


def _manual_upload_ledger(action_workflow):
    try:
        return (action_workflow or {}).get('staticData', {}).get('global', {}).get(
            'rcnManualUploadLedger', {}
        )
    except AttributeError:
        return {}


def lead_breakdown(execs, start_d, end_d, action_execs=None, action_workflow=None):
    counts = {'send_to_sales': 0, 'review': 0, 'suppress': 0, 'total': 0,
              'good_uploaded': 0, 'good_rejected': 0}
    leads, covered_min = [], None
    # Collapse every upload attempt for a person/day to one final operational
    # outcome.  Acceptance wins if another submission for the same person was
    # rejected, while a person is rejected only when every captured attempt was.
    upload_outcomes, aliases = {}, {}
    for e in execs:
        rd = e.get('data', {}).get('resultData', {}).get('runData', {})
        bf = _node(rd, 'Build Signals') or _node(rd, 'Build Features')
        if not bf: continue
        b = bf.get('body', {})
        features = bf.get('_features', {})
        dd = submitted_account_date(b)
        if dd is None: continue
        covered_min = dd if covered_min is None else min(covered_min, dd)
        if not (start_d <= dd <= end_d): continue
        ps = _node(rd, 'Parse Score') or {}; pb = ps.get('body', {})
        dec = _effective_decision(b, features, pb); counts['total'] += 1
        if dec in counts: counts[dec] += 1
        # "uploaded" now means GOOGLE ACCEPTED it — rejects (fake/test click IDs) don't count.
        if dec == 'send_to_sales' and b.get('click_id'):
            person = (dd, _canonical_person(b, aliases))
            accepted = _upload_accepted(rd)
            if accepted is True:
                upload_outcomes[person] = 'accepted'
            elif accepted is False and upload_outcomes.get(person) != 'accepted':
                upload_outcomes[person] = 'rejected'
        leads.append({'name': f"{b.get('first_name','')} {b.get('last_name','')}".strip(),
                      'score': pb.get('lead_score'), 'decision': dec,
                      'dest': b.get('destination', ''), 'when': (b.get('submitted_at') or '')[:16]})
    # Include only manual/recovery routes that actually called Google Ads.
    # Acceptance still wins over any rejected attempt for the same person/day.
    for person, outcome in _manual_upload_outcomes(action_execs, start_d, end_d, aliases).items():
        if outcome == 'accepted' or upload_outcomes.get(person) != 'accepted':
            upload_outcomes[person] = outcome
    # The action workflow keeps a compact durable ledger because successful
    # action executions are retained for much less time than report windows.
    for record in _manual_upload_ledger(action_workflow).values():
        dd = submitted_account_date(record)
        if dd is None or not (start_d <= dd <= end_d):
            continue
        state = str(record.get('manual_action') or '')
        if state not in {'good_uploaded', 'good_upload_failed'}:
            continue
        person = (dd, _canonical_person(record, aliases))
        outcome = 'accepted' if state == 'good_uploaded' else 'rejected'
        if outcome == 'accepted' or upload_outcomes.get(person) != 'accepted':
            upload_outcomes[person] = outcome

    leads.sort(key=lambda x: x['when'])
    counts['good_uploaded'] = sum(value == 'accepted' for value in upload_outcomes.values())
    counts['good_rejected'] = sum(value == 'rejected' for value in upload_outcomes.values())
    return counts, leads, covered_min

def upload_failures(execs, start_d, end_d):
    fails = []
    for e in execs:
        rd = e.get('data', {}).get('resultData', {}).get('runData', {})
        up = rd.get('Upload Click Conversion')
        if not up: continue
        try: resp = up[0]['data']['main'][0][0]['json']
        except Exception: continue
        b = ((_node(rd, 'Build Signals') or _node(rd, 'Build Features')) or {}).get('body', {})
        dd = submitted_account_date(b)
        if dd and not (start_d <= dd <= end_d): continue
        err = resp.get('error'); pfe = resp.get('partialFailureError')
        if resp.get('results') and not err and not pfe: continue
        msg = ''
        if err: msg = err.get('message', '')
        if pfe:
            try: msg = pfe['details'][0]['errors'][0]['message']
            except Exception: msg = json.dumps(pfe)[:140]
        fails.append({'name': f"{b.get('first_name','')} {b.get('last_name','')}".strip(),
                      'order': b.get('lead_order_id', ''), 'when': (b.get('submitted_at') or '')[:16], 'msg': msg[:140]})
    return fails

# ───────────────────────── email ─────────────────────────
def send_email(subject, html, recipients=REPORT_TO):
    recipients = tuple(recipients)
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject; msg['From'] = REPORT_FROM; msg['To'] = ', '.join(recipients)
    msg.attach(MIMEText(html, 'html'))
    host, port = S['SMTP_HOST'], int(S['SMTP_PORT'])
    if port == 465:
        srv = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        srv = smtplib.SMTP(host, port, timeout=30); srv.starttls()
    srv.login(S['SMTP_USER'], S['SMTP_PASSWORD'])
    srv.sendmail(REPORT_FROM, list(recipients), msg.as_string()); srv.quit()

# ───────────────────────── HTML helpers ─────────────────────────
TEAL, NAVY = '#2DBDC5', '#1A2B3D'
def shell(title, inner):
    return (f'<div style="font-family:Arial,Helvetica,sans-serif;max-width:640px;color:#222;">'
            f'<h2 style="color:{NAVY};border-bottom:3px solid {TEAL};padding-bottom:6px;">{title}</h2>'
            f'{inner}<p style="color:#999;font-size:11px;margin-top:24px;">River Cruise Network · '
            f'automated report · Google Ads {ADS_VERSION} · CID {CID}</p></div>')

def kpi_table(rows):
    out = '<table style="border-collapse:collapse;width:100%;margin:10px 0;">'
    for label, val in rows:
        out += (f'<tr><td style="padding:6px 12px;border:1px solid #e0e0e0;background:#f7f9fa;'
                f'font-weight:bold;width:55%;">{label}</td>'
                f'<td style="padding:6px 12px;border:1px solid #e0e0e0;">{val}</td></tr>')
    return out + '</table>'

def money(x): return f'${x:,.2f} CAD'

def count_value(x):
    return f'{int(round(x)):,}' if abs(x - round(x)) < 0.0005 else f'{x:,.1f}'

def executive_summary_html(metrics, good_ads, regions):
    items = [
        f'<li><b>Full-period Ads:</b> {money(metrics["cost"])} spend generated '
        f'{metrics["clicks"]:,} clicks and {metrics["impressions"]:,} impressions, with '
        f'{count_value(good_ads)} qualified lead conversions credited in Google Ads.</li>'
    ]
    if regions and metrics['cost']:
        top = regions[0]
        share = top['cost'] / metrics['cost'] * 100
        cpl = money(top['cost'] / top['good_leads']) if top['good_leads'] else 'n/a'
        items.append(
            f'<li><b>Largest physical region:</b> {html_lib.escape(top["label"])} represented '
            f'{share:.1f}% of spend and {count_value(top["good_leads"])} qualified lead '
            f'conversions at {cpl} per credited lead.</li>')
    return (f'<h3 style="color:{NAVY};margin-bottom:6px;">Executive summary</h3>'
            f'<ul style="margin-top:6px;padding-left:20px;line-height:1.45;">{"".join(items)}</ul>')

def region_table_html(regions, account_metrics, good_ads, top_n=10):
    if not regions:
        return ''
    shown = [dict(item) for item in regions[:top_n]]
    remainder = regions[top_n:]
    if remainder:
        shown.append({
            'label': 'Other regions',
            'cost': sum(item['cost'] for item in remainder),
            'clicks': sum(item['clicks'] for item in remainder),
            'impressions': sum(item['impressions'] for item in remainder),
            'good_leads': sum(item['good_leads'] for item in remainder),
        })
    reported = {
        'cost': sum(item['cost'] for item in regions),
        'clicks': sum(item['clicks'] for item in regions),
        'impressions': sum(item['impressions'] for item in regions),
        'good_leads': sum(item['good_leads'] for item in regions),
    }
    unreported = {
        'label': 'Unreported by Google',
        'cost': max(0.0, account_metrics['cost'] - reported['cost']),
        'clicks': max(0, account_metrics['clicks'] - reported['clicks']),
        'impressions': max(0, account_metrics['impressions'] - reported['impressions']),
        'good_leads': max(0.0, good_ads - reported['good_leads']),
    }
    if (unreported['cost'] >= 0.01 or unreported['clicks'] or
            unreported['impressions'] or unreported['good_leads'] >= 0.0005):
        shown.append(unreported)
    total = {
        'label': 'Total',
        'cost': account_metrics['cost'],
        'clicks': account_metrics['clicks'],
        'impressions': account_metrics['impressions'],
        'good_leads': good_ads,
    }

    def table_row(item, total_row=False):
        good = item['good_leads']
        cpl = money(item['cost'] / good) if good else '—'
        weight = 'font-weight:bold;background:#eef8f9;' if total_row else ''
        cell = f'padding:6px 7px;border:1px solid #e0e0e0;{weight}'
        return (
            f'<tr><td style="{cell}text-align:left;">{html_lib.escape(item["label"])}</td>'
            f'<td style="{cell}text-align:right;white-space:nowrap;">{money(item["cost"])}</td>'
            f'<td style="{cell}text-align:right;">{item["clicks"]:,}</td>'
            f'<td style="{cell}text-align:right;">{item["impressions"]:,}</td>'
            f'<td style="{cell}text-align:right;">{count_value(good)}</td>'
            f'<td style="{cell}text-align:right;white-space:nowrap;">{cpl}</td></tr>')

    body = ''.join(table_row(item) for item in shown) + table_row(total, total_row=True)
    return (
        f'<h3 style="color:{NAVY};margin-bottom:5px;">Ads performance by physical province / region</h3>'
        '<p style="color:#555;font-size:12px;line-height:1.4;margin:5px 0 10px;">'
        'Ranked by spend using Google Ads user-location reporting. This reflects where the '
        'ad user was physically located, not places they merely showed interest in.</p>'
        '<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;font-size:12px;">'
        '<tr style="background:#f7f9fa;">'
        '<th style="padding:6px 7px;border:1px solid #e0e0e0;text-align:left;">Region</th>'
        '<th style="padding:6px 7px;border:1px solid #e0e0e0;text-align:right;">Spend</th>'
        '<th style="padding:6px 7px;border:1px solid #e0e0e0;text-align:right;">Clicks</th>'
        '<th style="padding:6px 7px;border:1px solid #e0e0e0;text-align:right;">Impr.</th>'
        '<th style="padding:6px 7px;border:1px solid #e0e0e0;text-align:right;">Good leads</th>'
        '<th style="padding:6px 7px;border:1px solid #e0e0e0;text-align:right;">Cost / good</th>'
        f'</tr>{body}</table></div>'
        '<p style="color:#777;font-size:11px;line-height:1.4;margin:7px 0 14px;">'
        '“Good leads” sums the two qualified offline-upload conversion actions and is '
        'attributed to the original ad-click date. Fractional values reflect data-driven '
        'attribution. The top 10 regions are shown; remaining locations are grouped as Other '
        'regions. “Unreported by Google” reconciles traffic that Google Ads does not assign '
        'to a reportable province or region.</p>')

def summary_html(tok, label, start_d, end_d, intro_html=''):
    start, end = start_d.isoformat(), end_d.isoformat()
    m = ads_metrics(tok, start, end)
    conv = ads_conv_by_action(tok, start, end)
    good_ads  = offline_total(conv)           # both upload actions, Ads-credited (lags ~1–3d)
    total_ads = conv.get(LEGACY_ACTION, 0)    # Ads baseline form completions (also lags)
    regions = ads_region_performance(tok, start, end) if label in ('weekly', 'monthly') else []
    execs = n8n_execs()
    action_execs = n8n_execs(ACTION_WORKFLOW_ID)
    action_workflow = n8n_workflow(ACTION_WORKFLOW_ID)
    counts, leads, covered_min = lead_breakdown(
        execs, start_d, end_d, action_execs, action_workflow
    )
    n8n_partial = covered_min is not None and covered_min > start_d
    uploaded = counts['good_uploaded']        # send_to_sales + click_id ACCEPTED by Google (immediate)
    rejected = counts['good_rejected']        # uploads Google bounced (fake/test click IDs, etc.)
    pw = ' <span style="color:#c77;font-weight:normal;">(recent window)</span>' if n8n_partial else ''
    # Cost/good lead: use our immediate uploaded count when n8n covers the whole period;
    # for older periods (monthly, beyond n8n retention) fall back to the now-settled Ads count.
    basis = uploaded if (uploaded and not n8n_partial) else (good_ads or None)
    cpl_good = money(m['cost'] / basis) if basis else 'n/a'
    lead_total_basis = counts['total'] if (counts['total'] and not n8n_partial) else total_ads
    cpl_all = money(m['cost'] / lead_total_basis) if lead_total_basis else 'n/a'
    rows = [
        ('Period', f'{start} → {end}'),
        ('Ad spend', money(m['cost'])),
        ('Clicks', f"{m['clicks']:,}"),
        ('Impressions', f"{m['impressions']:,}"),
        ('Leads scored (n8n)' + pw, f"{counts['total']}"),
        ('Good leads — uploaded &amp; accepted by Google' + pw, f'<b>{uploaded}</b>'),
    ]
    if rejected:
        rows.append(('Uploads rejected by Google <span style="color:#999;font-weight:normal;">(fake/test click IDs)</span>',
                     f'<span style="color:#c62828;">{rejected}</span>'))
    rows += [
        ('Conversions credited in Ads <span style="color:#999;font-weight:normal;">(settling, ~1–3d lag)</span>', f'{good_ads:g}'),
        ('Cost / good lead', cpl_good),
        ('Cost / lead', cpl_all),
    ]
    inner = intro_html
    if regions:
        inner += executive_summary_html(m, good_ads, regions)
    inner += kpi_table(rows)
    inner += ('<p style="color:#777;font-size:12px;margin:6px 0 14px;">'
              '“Uploaded &amp; accepted” counts only good leads Google <b>accepted</b> in real time — '
              'rejected uploads (fake/test click IDs) are excluded. '
              '“Credited in Ads” lags 1–3 days (offline conversions settle with fractional, '
              'data-driven attribution) and rises over the following days — so it’s normally '
              'lower than the accepted count on the morning after. iOS (gbraid/wbraid) conversions '
              'are modelled and credit more slowly than gclid. Operational good-lead totals '
              'count each person once per account day; distinct click IDs remain an Ads-credit '
              'diagnostic.</p>')
    inner += region_table_html(regions, m, good_ads)
    # n8n tier split
    if counts['total']:
        note = ' <span style="color:#c77;">(recent window only — older leads aged out of n8n)</span>' if n8n_partial else ''
        inner += (f'<h3 style="color:{NAVY};">Quality split{note}</h3>' + kpi_table([
            ('✅ Good (send_to_sales)', counts['send_to_sales']),
            ('🟡 Review', counts['review']),
            ('🔴 Spam (suppress)', counts['suppress']),
            ('Scored total (n8n)', counts['total']),
        ]))
    # lead list (daily only, or small lists)
    if leads and len(leads) <= 40:
        rowsh = ''.join(
            f'<tr><td style="padding:4px 8px;border:1px solid #eee;">{l["when"]}</td>'
            f'<td style="padding:4px 8px;border:1px solid #eee;">{l["name"] or "-"}</td>'
            f'<td style="padding:4px 8px;border:1px solid #eee;text-align:center;">{l["score"]}</td>'
            f'<td style="padding:4px 8px;border:1px solid #eee;">{l["decision"]}</td>'
            f'<td style="padding:4px 8px;border:1px solid #eee;">{(l["dest"] or "")[:30]}</td></tr>'
            for l in leads)
        inner += (f'<h3 style="color:{NAVY};">Leads</h3>'
                  '<table style="border-collapse:collapse;width:100%;font-size:13px;">'
                  '<tr style="background:#f7f9fa;"><th style="padding:4px 8px;border:1px solid #eee;text-align:left;">When</th>'
                  '<th style="padding:4px 8px;border:1px solid #eee;text-align:left;">Name</th>'
                  '<th style="padding:4px 8px;border:1px solid #eee;">Score</th>'
                  '<th style="padding:4px 8px;border:1px solid #eee;text-align:left;">Decision</th>'
                  '<th style="padding:4px 8px;border:1px solid #eee;text-align:left;">Destination</th></tr>'
                  f'{rowsh}</table>')
    return shell(f'RCN {label}: {start} → {end}', inner)

# ───────────────────────── modes ─────────────────────────
def expected_good_with_click(execs, day_d):
    """Unique people on day_d who should auto-upload."""
    people, aliases = set(), {}
    for e in execs:
        rd = e.get('data', {}).get('resultData', {}).get('runData', {})
        bf = _node(rd, 'Build Signals') or _node(rd, 'Build Features')
        if not bf: continue
        b = bf.get('body', {})
        if submitted_account_date(b) != day_d: continue
        ps = _node(rd, 'Parse Score') or {}
        pb = ps.get('body', {})
        if _effective_decision(b, bf.get('_features', {}), pb) == 'send_to_sales' and b.get('click_id'):
            people.add(_canonical_person(b, aliases))
    return len(people)

def expected_unique_click_groups(execs, day_d):
    """One first-touch click group per unique upload-eligible person.

    Ads reporting can be lower than accepted uploads because the gclid action is
    ONE_PER_CLICK and because offline conversions settle after upload.
    """
    groups, aliases = set(), {}
    rows = []
    for e in execs:
        rd = e.get('data', {}).get('resultData', {}).get('runData', {})
        bf = _node(rd, 'Build Signals') or _node(rd, 'Build Features')
        if not bf: continue
        b = bf.get('body', {})
        if submitted_account_date(b) != day_d: continue
        ps = _node(rd, 'Parse Score') or {}
        pb = ps.get('body', {})
        if _effective_decision(b, bf.get('_features', {}), pb) == 'send_to_sales' and b.get('click_id'):
            rows.append(b)
    seen_people = set()
    for b in sorted(rows, key=lambda row: str(row.get('submitted_at') or '')):
        person = _canonical_person(b, aliases)
        if person in seen_people:
            continue
        seen_people.add(person)
        groups.add((b.get('click_id_type') or 'gclid', b.get('click_id')))
    return len(groups)

def run_health():
    today = account_today(); y = today - timedelta(days=1)
    alerts, info = [], []
    tok = None
    # 1. API version — the #1 systemic risk (direct test, authoritative)
    try:
        tok = ads_token()
        ads_search(tok, "SELECT customer.id FROM customer LIMIT 1")
        info.append(f'Google Ads API {ADS_VERSION}: OK')
    except urllib.error.HTTPError as ex:
        body = ex.read().decode()
        if 'UNSUPPORTED_VERSION' in body or 'deprecated' in body:
            alerts.append(f'🚨 Google Ads API {ADS_VERSION} is DEPRECATED/BLOCKED — bump ADS_VERSION in '
                          'rcn_report.py, the n8n Upload/Geo nodes, conversion_worker.py & recover_braid.py.')
        else:
            alerts.append(f'🚨 Google Ads API error: {body[:200]}')
    # 2. expected good leads (n8n) vs conversions actually in Ads (includes recoveries)
    execs = n8n_execs()
    action_execs = n8n_execs(ACTION_WORKFLOW_ID)
    action_workflow = n8n_workflow(ACTION_WORKFLOW_ID)
    counts, _, _ = lead_breakdown(execs, y, y, action_execs, action_workflow)
    expected_auto = expected_good_with_click(execs, y)
    expected = max(expected_auto, counts.get('good_uploaded', 0) + counts.get('good_rejected', 0))
    unique_clicks = expected_unique_click_groups(execs, y)
    actual = None; spend = None
    if tok:
        try:
            actual = round(offline_total(ads_conv_by_action(tok, y.isoformat(), y.isoformat())))
            spend = ads_metrics(tok, y.isoformat(), y.isoformat())['cost']
        except Exception as ex:
            alerts.append(f'🚨 Ads metrics query failed: {ex}')
    # Alert on upload failures/missing accepted uploads. Ads credited conversions are a lagging
    # metric and can be lower the morning after, especially when repeat submits share a gclid.
    if counts.get('good_rejected'):
        alerts.append(f'🚨 {counts["good_rejected"]} good-lead upload(s) were rejected by Google Ads '
                      f'yesterday — check the Upload Click Conversion node response.')
    if expected >= 3 and counts.get('good_uploaded', 0) < expected:
        alerts.append(f'🚨 Only {counts["good_uploaded"]} of {expected} upload-eligible good leads were '
                      f'accepted by Google Ads yesterday — check the Upload Click Conversion node.')
    # 3. n8n's OWN credentials. Check #1 above tests ~/.secrets, which is a different
    # OAuth grant from the one in the n8n container's env. On 12 Sep 2026 the n8n token
    # died at ~11:30 UTC and this report said "All good" the next morning because its
    # own token was fine and the day's 2 failed uploads sat under the expected>=3 gate.
    # Reading the OAuth node's output in the last 24h catches it regardless of volume.
    no_token = []
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    for e in execs:
        if (e.get('startedAt') or '') < cutoff:
            continue
        rd = e.get('data', {}).get('resultData', {}).get('runData', {})
        node = rd.get('Get Google OAuth Token')
        if not node:
            continue
        out = ((node[0].get('data') or {}).get('main') or [[]])[0]
        j = out[0].get('json', {}) if out else {}
        if not j.get('access_token'):
            ps = rd.get('Parse Score')
            pj = (((ps[0].get('data') or {}).get('main') or [[]])[0] or [{}])[0].get('json', {}) if ps else {}
            no_token.append(pj.get('body', {}).get('lead_order_id', e.get('startedAt', '?')[:16]))
    if no_token:
        alerts.append(f'🚨 n8n could not mint a Google Ads access token for {len(no_token)} upload(s) in the '
                      f'last 24h — its refresh token is probably revoked (invalid_grant). Run '
                      f'ops/reissue_google_ads_token.py, then conversion_worker.py --upload-order for: '
                      + ', '.join(no_token[:6]) + (' …' if len(no_token) > 6 else ''))
    else:
        info.append('n8n Google Ads token: OK (every upload in the last 24h minted a token)')
    # heartbeat info
    if spend is not None: info.append(f'Spend yesterday: {money(spend)}')
    info.append(f'Yesterday ({y}): {counts["total"]} scored — '
                f'{counts["send_to_sales"]} good / {counts["review"]} review / {counts["suppress"]} spam')
    info.append(f'Good leads uploaded &amp; accepted: {counts["good_uploaded"]}'
                + (f' · <span style="color:#c62828;">{counts["good_rejected"]} rejected by Google</span>' if counts.get('good_rejected') else ''))
    info.append(f'Unique ad-click groups eligible for Ads credit: {unique_clicks}')
    info.append(f'Conversions credited in Ads so far: {actual if actual is not None else "?"}')
    healthy = not alerts
    status = '✅ All good' if healthy else '🚨 ATTENTION NEEDED'
    inner = ''
    if alerts:
        inner += ('<div style="background:#fdecea;border:1px solid #f5c6cb;padding:12px;border-radius:6px;color:#7a1c12;">'
                  + '<br>'.join(alerts) + '</div>')
    inner += '<h3 style="color:#1A2B3D;">Status</h3>' + '<br>'.join(info)
    send_email(f'[RCN health] {status} — {y}', shell(f'RCN health check — {status}', inner))
    print(f'[RCN health] {status} — {y}')

def run_summary(label, start_d, end_d, recipients=REPORT_TO, example=False):
    tok = ads_token()
    intro_html = ''
    subject_prefix = ''
    if example:
        subject_prefix = '[EXAMPLE] '
        intro_html = (
            '<div style="background:#eaf9fa;border:1px solid #2DBDC5;padding:12px 14px;'
            'border-radius:6px;margin:0 0 14px;">'
            '<b>This is an example of the weekly review.</b><br>'
            'Regular reviews will arrive every Monday morning.'
            '</div>'
        )
    html = summary_html(tok, label, start_d, end_d, intro_html=intro_html)
    send_email(f'{subject_prefix}[RCN {label}] {start_d} → {end_d}', html, recipients)
    print(f'sent {label}: {start_d} → {end_d}')

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    today = account_today()
    if mode == '--health':
        run_health()
    elif mode == '--daily':
        y = today - timedelta(days=1); run_summary('daily', y, y)
    elif mode == '--weekly':
        run_summary('weekly', today - timedelta(days=7), today - timedelta(days=1), WEEKLY_REPORT_TO)
    elif mode == '--weekly-example':
        run_summary('weekly', today - timedelta(days=7), today - timedelta(days=1),
                    WEEKLY_REPORT_TO, example=True)
    elif mode == '--monthly':
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        run_summary('monthly', last_prev.replace(day=1), last_prev, MONTHLY_REPORT_TO)
    else:
        print('usage: rcn_report.py --health|--daily|--weekly|--weekly-example|--monthly'); sys.exit(1)

if __name__ == '__main__':
    main()
