#!/usr/bin/env python3
"""Install/test only the isolated monitor on the n8n VPS. No lead or Ads writes."""
import argparse
import datetime as dt
import json
import os
import pathlib
import secrets
import time
import urllib.error
import urllib.request
from build import build

os.umask(0o077)
HOME = pathlib.Path('/home/ben/infra/dct-conversion-monitor')
REGISTRY = HOME/'installation.json'
BASE = 'http://localhost:5678'

def api_key():
    for line in pathlib.Path('/home/ben/.secrets').read_text().splitlines():
        if line.startswith('N8N_API_KEY='):
            return line.split('=',1)[1].strip().strip('"').strip("'")
    raise RuntimeError('Existing n8n API key is missing')

KEY = api_key()

def api(method, path, body=None):
    payload=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(BASE+'/api/v1'+path,data=payload,method=method,
                              headers={'X-N8N-API-KEY':KEY,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=60) as r:
            raw=r.read(); return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        # API errors can echo submitted credentials: never dump the response.
        raise RuntimeError(f'n8n {method} {path} returned HTTP {e.code}') from None

def save(value): REGISTRY.write_text(json.dumps(value,indent=2)+'\n')

def install():
    HOME.mkdir(parents=True,exist_ok=True)
    reg=json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {}
    if not reg.get('apiCredential'):
        reg['apiCredential']=api('POST','/credentials',{'name':'DCT monitor n8n read access','type':'httpHeaderAuth','data':{'name':'X-N8N-API-KEY','value':KEY}})['id'];save(reg)
    if not reg.get('triggerCredential'):
        token=secrets.token_urlsafe(48)
        (HOME/'trigger.key').write_text(token)
        reg['triggerCredential']=api('POST','/credentials',{'name':'DCT monitor private trigger','type':'httpHeaderAuth','data':{'name':'X-DCT-Monitor-Key','value':token}})['id'];save(reg)
    def upsert(key,w):
        if reg.get(key):
            old=api('GET','/workflows/'+reg[key])
            stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            (HOME/(key+'-'+stamp+'.backup.json')).write_text(json.dumps(old))
            w['staticData']=old.get('staticData')
            api('PUT','/workflows/'+reg[key],w)
        else:
            reg[key]=api('POST','/workflows',w)['id'];save(reg)
    _,error=build(reg['apiCredential'],reg['triggerCredential'])
    upsert('errorWorkflow',error)
    # This installed n8n runtime requires an active error workflow (verified in logs).
    err=api('GET','/workflows/'+reg['errorWorkflow'])
    if err.get('active'):api('POST','/workflows/'+reg['errorWorkflow']+'/deactivate')
    api('POST','/workflows/'+reg['errorWorkflow']+'/activate')
    main,_=build(reg['apiCredential'],reg['triggerCredential'],reg['errorWorkflow'])
    upsert('workflow',main)
    # Trigger changes require publication. Existing DCT intake/actions are untouched.
    main=api('GET','/workflows/'+reg['workflow'])
    if main.get('active'):api('POST','/workflows/'+reg['workflow']+'/deactivate')
    api('POST','/workflows/'+reg['workflow']+'/activate')
    print(json.dumps({'installed':reg['workflow'],'url':'https://n8.copperchunk.com/workflow/'+reg['workflow'],'errorWorkflow':reg['errorWorkflow']}))

def status():
    reg=json.loads(REGISTRY.read_text()); w=api('GET','/workflows/'+reg['workflow']); s=(w.get('staticData') or {}).get('global',{})
    def report(key): return {k:v for k,v in s[key].items() if k!='intakeCache'} if s.get(key) else None
    print(json.dumps({'id':w['id'],'name':w['name'],'active':w['active'],'settings':w['settings'],
      'aiNodes':[n['name'] for n in w['nodes'] if any(t in n['type'].lower() for t in ['codex','openai','agent','anthropic'])],
      'lastCheck':report('lastCheck'),'lastDryRun':report('lastDryRun'),'lastDeliveryTest':s.get('lastDeliveryTest'),'lastSuccessfulExecution':s.get('lastSuccessfulExecution'),
      'recentExecutions':[{k:e.get(k) for k in ['id','status','startedAt','stoppedAt']} for e in api('GET','/executions?workflowId='+w['id']+'&limit=3')['data']]}))

def run(mode):
    reg=json.loads(REGISTRY.read_text()); path='/executions?workflowId='+reg['workflow']+'&limit=5'
    previous={e['id'] for e in api('GET',path)['data']}
    state_field={'dry-run':'lastDryRun','test-alert':'lastDeliveryTest','run':'lastCheck','test-failure':'lastDelivered'}[mode]
    observed_workflow=reg['errorWorkflow'] if mode=='test-failure' else reg['workflow']
    old_state=(api('GET','/workflows/'+observed_workflow).get('staticData') or {}).get('global',{}).get(state_field)
    req=urllib.request.Request(BASE+'/webhook/dct-conversion-monitor',data=json.dumps({'dry_run':mode=='dry-run','test_alert':mode=='test-alert','test_failure':mode=='test-failure'}).encode(),headers={'Content-Type':'application/json','X-DCT-Monitor-Key':(HOME/'trigger.key').read_text().strip()})
    with urllib.request.urlopen(req,timeout=30) as r:
        if r.status!=200:raise RuntimeError('Private monitor trigger was not accepted')
    for _ in range(90):
        time.sleep(2)
        state=(api('GET','/workflows/'+observed_workflow).get('staticData') or {}).get('global',{})
        if state.get(state_field) and state[state_field]!=old_state:
            print(json.dumps({'status':'success','mode':mode,'evidence':'Sanitized checkpoint saved after all reads and any required email completed'}));status();return
        candidates=[e for e in api('GET',path)['data'] if e['id'] not in previous]
        if candidates and candidates[0]['status'] in ['success','error','canceled','crashed']:
            e=candidates[0];print(json.dumps({'execution':e['id'],'status':e['status'],'mode':mode}));status();return
    raise RuntimeError('Monitor still running after three minutes; inspect before retriggering')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['install','dry-run','test-alert','test-failure','run','status']);args=p.parse_args()
    if args.mode=='install':install()
    elif args.mode=='status':status()
    else:run(args.mode)
