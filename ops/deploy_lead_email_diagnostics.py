#!/usr/bin/env python3
"""Patch only the two live email HTML expressions. Run beside the JS on the VPS.

Default: preview/validate. --apply: backup, patch and verify active versions.
--report: send Ben one seven-day sparse-lead digest through an isolated SMTP
workflow. No intake replay, Ads calls, CRM changes or lead-sheet writes.
"""
import argparse
import copy
import datetime as dt
import html
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import urllib.parse
import urllib.request

SITES = {'RCN': 'zYw4HtTy1OTH7jUy', 'DCT': 'PmntlqBanV9ZMy3O'}
ROOT = Path(__file__).resolve().parent
RENDERER = (ROOT / 'lead_email_diagnostics.js').read_text().split("\nif (typeof module")[0].strip()
BEN = 'btl101@gmail.com'


def api(method, path, body=None):
    key = next(line.split('=', 1)[1].strip() for line in Path('/home/ben/.secrets').read_text().splitlines() if line.startswith('N8N_API_KEY='))
    req = urllib.request.Request('http://localhost:5678/api/v1' + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'X-N8N-API-KEY': key, 'Content-Type': 'application/json'}, method=method)
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}


def private_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(data, indent=2))
    path.chmod(0o600)


def email_node(w):
    nodes = [n for n in w['nodes'] if n['name'] == 'Send Email Notification']
    assert len(nodes) == 1
    return nodes[0]


def expression_inner(expression):
    assert expression.startswith('={{') and expression.endswith('}}'), 'Unexpected email expression'
    return expression[3:-2].strip()


def patch(w, brand):
    result = copy.deepcopy(w)
    params = email_node(result)['parameters']
    if '<!-- LEAD_DIAGNOSTICS_V1 -->' in params['html']:
        return result
    original = expression_inner(params['html'])
    source = '$json.body || {}' if brand == 'RCN' else '$json'
    params['html'] = '={{ (' + RENDERER + ')(' + source + ', ' + json.dumps(brand) + ') + (' + original + ') }}'
    # Prove that the original expression is the only changed field.
    check = copy.deepcopy(result)
    email_node(check)['parameters']['html'] = email_node(w)['parameters']['html']
    assert check == w
    return result


def js_eval(code, value):
    program = 'const fs=require("fs");const $json=JSON.parse(fs.readFileSync(0,"utf8"));const result=(' + code + ');process.stdout.write(JSON.stringify(result));'
    done = subprocess.run(['node', '-e', program], input=json.dumps(value), capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError('JavaScript rendering failed; inspect private source locally')
    return json.loads(done.stdout)


def validate(w, patched, brand):
    old = email_node(w)['parameters']['html']
    new = email_node(patched)['parameters']['html']
    for lead in [{'email_html':''}, {'first_name':'<script>bad</script>', 'email':'person@example.com', 'user_agent':'Synthetic QA browser', 'ip_address':'192.0.2.1', 'utm_campaign':'Example campaign', 'time_on_page':0, 'email_html':'<p>ORIGINAL EMAIL</p>'}]:
        item = {'body':lead} if brand == 'RCN' else lead
        rendered = js_eval(expression_inner(new), item)
        previous = js_eval(expression_inner(old), item)
        assert rendered.endswith(previous)
        assert '<!-- LEAD_DIAGNOSTICS_V1 -->' in rendered
        assert '<script>bad</script>' not in rendered
        if lead.get('user_agent'):
            assert 'Synthetic QA browser' in rendered and '192.0.2.1' in rendered


def deploy(apply):
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    for brand, wid in SITES.items():
        live = api('GET', '/workflows/' + wid)
        assert live['active'] and live['versionId'] == live['activeVersionId']
        candidate = patch(live, brand)
        validate(live, candidate, brand)
        changed = candidate != live
        if apply and changed:
            fresh = api('GET', '/workflows/' + wid)
            assert fresh['versionId'] == live['versionId'], 'Workflow changed during review; rerun'
            candidate = patch(fresh, brand)
            private_json(Path('/home/ben/infra/n8n/workflow-backups') / (brand.lower() + '-before-email-diagnostics-' + stamp + '.json'), fresh)
            # Omit staticData: leave server-owned counters/cache untouched.
            payload = {k: candidate[k] for k in ('name', 'nodes', 'connections', 'settings')}
            api('PUT', '/workflows/' + wid, payload)
            checked = api('GET', '/workflows/' + wid)
            assert checked['active'] and checked['versionId'] == checked['activeVersionId']
            for key in ('nodes', 'connections', 'settings'):
                assert checked[key] == candidate[key], 'Saved content differs: ' + key
            print(json.dumps({'site':brand, 'applied':True, 'activeVersionId':checked['activeVersionId'], 'changed_field':'Send Email Notification.parameters.html'}), flush=True)
        else:
            print(json.dumps({'site':brand, 'validated':True, 'change_needed':changed, 'applied':False}), flush=True)


def output_item(runs, name):
    try:
        return runs[name][0]['data']['main'][0][0]['json']
    except (KeyError, IndexError, TypeError):
        return {}


def collect():
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
    all_leads, seen, counts = [], set(), {}
    for brand, wid in SITES.items():
        cursor = None
        examined = 0
        while True:
            path = '/executions?workflowId=' + wid + '&limit=100' + ('&cursor=' + urllib.parse.quote(cursor, safe='') if cursor else '')
            page = api('GET', path)
            ended = False
            for ex in page['data']:
                started = dt.datetime.fromisoformat(ex['startedAt'].replace('Z', '+00:00'))
                if started < cutoff:
                    ended = True
                    continue
                if ex.get('mode') != 'webhook':
                    continue
                full = api('GET', '/executions/' + ex['id'] + '?includeData=true')
                runs = full.get('data', {}).get('resultData', {}).get('runData', {})
                # Only already-delivered genuine notifications; no QA or auth failures.
                if not runs.get('Send Email Notification') or runs['Send Email Notification'][0].get('error'):
                    continue
                item = output_item(runs, 'Assign Daily Lead Number' if brand == 'RCN' else 'Format Lead Email')
                lead = item.get('body', {}) if brand == 'RCN' else item
                if not lead or str(lead.get('qa_test', '')) == '1':
                    continue
                key = (brand, lead.get('lead_order_id') or ex['id'])
                if key in seen:
                    continue
                seen.add(key)
                examined += 1
                # Known numeric IDs may be resolved from the existing RCN cache.
                all_leads.append({'brand':brand, 'execution':ex['id'], 'lead':lead, 'startedAt':ex['startedAt']})
            cursor = page.get('nextCursor')
            if ended or not cursor:
                break
        counts[brand] = examined
    selected = []
    generic = {'', 'not sure', 'not sure yet', 'flexible', 'any', 'unknown', 'n/a', 'none', 'na', '-', 'undecided'}
    for item in all_leads:
        lead = item['lead']
        missing_contact = [k for k in ('first_name', 'last_name', 'email', 'phone') if not str(lead.get(k) or '').strip()]
        sparse_trip = [k for k in ('destination', 'travel_date', 'duration', 'budget', 'guests') if str(lead.get(k) or '').strip().lower() in generic]
        decision = str(lead.get('decision') or '')
        if missing_contact or len(sparse_trip) >= 2 or decision in ('review', 'suppress'):
            item['review_reason'] = '; '.join(filter(None, [
                'Missing contact fields: ' + ', '.join(missing_contact) if missing_contact else '',
                'Missing/flexible/unsure trip fields: ' + ', '.join(sparse_trip) if sparse_trip else '',
                'Existing review decision: ' + decision if decision in ('review', 'suppress') else '',
            ]))
            selected.append(item)
    selected.sort(key=lambda x: x['startedAt'], reverse=True)
    return selected, {'since_utc':cutoff.isoformat(), 'delivered_leads_examined':counts, 'selected':len(selected)}


def send_report(selected, summary):
    # Ledger is written before sending: an ambiguous result must be reviewed, never resent blindly.
    day = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d')
    ledger = Path('/home/ben/infra/n8n/workflow-backups') / ('lead-diagnostics-report-' + day + '.json')
    assert not ledger.exists(), 'Report already attempted today; inspect ledger before resending'
    content = '<h1>Recent lead diagnostics</h1><p>Last seven days, from ' + html.escape(summary['since_utc']) + ' UTC. Reviewed ' + str(sum(summary['delivered_leads_examined'].values())) + ' delivered website submissions across RCN and DCT. Selected ' + str(len(selected)) + ' with missing contact details, at least two missing/flexible/unsure trip fields, or an existing review/suppress decision. This is a review list, not a finding of spam.</p><p>All future lead notifications now include these diagnostics. This digest was sent only to Ben. No leads or conversions were replayed.</p>'
    for item in selected:
        content += '<hr><h2>' + html.escape(item['brand'] + ' — ' + str(item['lead'].get('lead_order_id') or item['execution'])) + '</h2><p>' + html.escape(item['review_reason']) + '</p>'
        content += js_eval('(' + RENDERER + ')($json.lead, $json.brand)', item)
    private_json(ledger, {'state':'prepared', 'summary':summary})
    mail = copy.deepcopy(email_node(api('GET', '/workflows/' + SITES['RCN'])))
    mail['id'], mail['name'], mail['position'] = 'digest-email', 'Send Ben Diagnostics', [450,0]
    mail['parameters'].update({'toEmail':BEN, 'subject':f'Lead diagnostics: {len(selected)} recent submissions to review — {day}', 'html':'={{ $json.html }}', 'options':{}})
    secret, path = secrets.token_hex(32), 'lead-diagnostics-' + secrets.token_hex(16)
    workflow = {'name':'Temporary Ben-only lead diagnostics', 'nodes':[
        {'id':'digest-webhook','name':'Private Digest Trigger','type':'n8n-nodes-base.webhook','typeVersion':2,'position':[0,0], 'webhookId':path,'parameters':{'httpMethod':'POST','path':path,'responseMode':'onReceived','options':{}}},
        {'id':'digest-guard','name':'Verify Digest Secret','type':'n8n-nodes-base.code','typeVersion':2,'position':[220,0], 'parameters':{'jsCode':"if ($json.headers['x-digest-secret'] !== " + json.dumps(secret) + ") return []; return [{json:{html:$json.body.html}}];"}}, mail],
        'connections':{'Private Digest Trigger':{'main':[[{'node':'Verify Digest Secret','type':'main','index':0}]]},'Verify Digest Secret':{'main':[[{'node':'Send Ben Diagnostics','type':'main','index':0}]]}}, 'settings':{'executionOrder':'v1'}}
    created = api('POST', '/workflows', workflow)
    wid = created['id']
    private_json(ledger, {'state':'created', 'workflow_id':wid, 'summary':summary})
    try:
        api('POST', '/workflows/' + wid + '/activate')
        private_json(ledger, {'state':'sending', 'workflow_id':wid, 'summary':summary})
        req = urllib.request.Request('http://localhost:5678/webhook/' + path, data=json.dumps({'html':content}).encode(), headers={'Content-Type':'application/json', 'X-Digest-Secret':secret}, method='POST')
        with urllib.request.urlopen(req, timeout=30) as response:
            assert response.status == 200
        for attempt in range(20):
            executions = api('GET', '/executions?workflowId=' + wid + '&limit=5')['data']
            if executions and executions[0]['status'] in ('success','error','crashed','canceled'):
                ex = api('GET', '/executions/' + executions[0]['id'] + '?includeData=true')
                sent = output_item(ex.get('data',{}).get('resultData',{}).get('runData',{}), 'Send Ben Diagnostics')
                assert ex['status'] == 'success' and BEN in sent.get('accepted', []) and not sent.get('rejected'), 'SMTP delivery not confirmed'
                private_json(ledger, {'state':'smtp_accepted', 'execution_id':ex['id'], 'summary':summary})
                print(json.dumps({'report':'smtp_accepted', 'to':BEN, 'selected':len(selected), 'execution':ex['id']}), flush=True)
                break
            time.sleep(2)
        else:
            raise RuntimeError('Digest status uncertain; inspect ledger and execution; do not resend')
    finally:
        api('POST', '/workflows/' + wid + '/deactivate')
        api('DELETE', '/workflows/' + wid)


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--report', action='store_true')
    parser.add_argument('--preview-report', action='store_true')
    args = parser.parse_args()
    deploy(args.apply)
    if args.report or args.preview_report:
        selected, summary = collect()
        print(json.dumps({'report_preview':summary}), flush=True)
        if args.report:
            assert all('<!-- LEAD_DIAGNOSTICS_V1 -->' in email_node(api('GET','/workflows/'+wid))['parameters']['html'] for wid in SITES.values()), 'Deploy diagnostics before sending report'
            send_report(selected, summary)
