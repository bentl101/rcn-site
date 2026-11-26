#!/usr/bin/env python3
"""Build a deterministic n8n monitor. Credential IDs are injected by deploy.py."""
import json
import pathlib
import uuid
from urllib.parse import urlencode

ROOT = pathlib.Path(__file__).parent
LEADS = '1dY5JczBg7qkxMov1HmbPRlOpwPrrKwSndh5NiYXfVTY'
QUEUE = '12NZo1KjNDeuMUk-0f0AirO5lNZD0AssWf41kRTUXGh8'

def node(name, typ, params, x, y=0, version=1, **kw):
    return dict(id=str(uuid.uuid5(uuid.NAMESPACE_URL, 'dct-monitor/'+name)), name=name,
                type=typ, typeVersion=version, position=[x,y], parameters=params, **kw)

def code(name, text, x, y=0):
    return node(name,'n8n-nodes-base.code',{'jsCode':text},x,y,version=2)

def edge(name): return {'node':name,'type':'main','index':0}

def http(name, url, x, **params):
    return node(name,'n8n-nodes-base.httpRequest',dict(url=url,options={'timeout':45000},**params),x,version=4.2,
                retryOnFail=True,maxTries=3,waitBetweenTries=5000,onError='continueRegularOutput')

def sheet(name, sid, ranges, x):
    url='https://sheets.googleapis.com/v4/spreadsheets/'+sid+'/values:batchGet?'+urlencode([('ranges',r) for r in ranges]+[('valueRenderOption','UNFORMATTED_VALUE')])
    n=http(name,url,x,authentication='predefinedCredentialType',nodeCredentialType='googleSheetsOAuth2Api')
    n['credentials']={'googleSheetsOAuth2Api':{'id':'YAn0z4KXSLPGMLum','name':'Google Sheets account'}}
    return n

def email(name, x, y=0):
    return node(name,'n8n-nodes-base.emailSend',{'fromEmail':'ben@copperchunk.com','toEmail':'btl101@gmail.com',
                'subject':'={{ $json.subject }}','emailFormat':'html','html':'={{ $json.html }}','options':{}},x,y,version=2.1,
                credentials={'smtp':{'id':'upVw1vzTxegbXV9E','name':'Google Workspace SMTP'}},retryOnFail=True,maxTries=3,waitBetweenTries=5000)

def condition(name, field, x, y=0):
    return node(name,'n8n-nodes-base.if',{'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':2},
                'conditions':[{'id':'enabled','leftValue':'={{ $json.'+field+' }}','rightValue':'','operator':{'type':'boolean','operation':'true','singleValue':True}}],
                'combinator':'and'},'options':{}},x,y,version=2.2)

def build(api_credential='API_CREDENTIAL', trigger_credential='TRIGGER_CREDENTIAL', error_id=None):
    nodes=[node('Daily 09:40 Dublin','n8n-nodes-base.scheduleTrigger',{'rule':{'interval':[{'field':'cronExpression','expression':'0 40 9 * * *'}]}},0,version=1.2),
      node('Private monitor check','n8n-nodes-base.webhook',{'httpMethod':'POST','path':'dct-conversion-monitor','authentication':'headerAuth','responseMode':'onReceived','options':{}},0,220,version=2,
           webhookId='dct-conversion-monitor',credentials={'httpHeaderAuth':{'id':trigger_credential,'name':'DCT monitor private trigger'}}),
      code('Start check',"const b=$json.body||{};if(b.test_failure===true)throw new Error('DCT_MONITOR_SELF_TEST');return [{json:{now:new Date().toISOString(),dryRun:b.dry_run===true,testAlert:b.test_alert===true}}];",220),
      sheet('Read leads',LEADS,['Leads!A:B','Leads!AG:AK','Leads!AR:AS','Leads!AU:AZ','Leads!BC:BE'],440),
      sheet('Read conversion queue',QUEUE,['Conversions!A:H'],660),
      sheet('Read lead actions',LEADS,["'Lead Actions'!A:D","'Lead Actions'!G:P"],880),
      http('Read intake history','http://localhost:5678/api/v1/executions?workflowId=PmntlqBanV9ZMy3O&limit=250&includeData=true',1100,authentication='genericCredentialType',genericAuthType='httpHeaderAuth'),
      http('Get Ads read token','https://oauth2.googleapis.com/token',1320,method='POST',sendBody=True,contentType='form-urlencoded',bodyParameters={'parameters':[
          {'name':'client_id','value':'={{ $env.GOOGLE_ADS_CLIENT_ID }}'}, {'name':'client_secret','value':'={{ $env.GOOGLE_ADS_CLIENT_SECRET }}'},
          {'name':'refresh_token','value':'={{ $env.GOOGLE_ADS_REFRESH_TOKEN }}'}, {'name':'grant_type','value':'refresh_token'}]})]
    nodes[6]['credentials']={'httpHeaderAuth':{'id':api_credential,'name':'DCT monitor n8n read access'}}
    headers={'parameters':[{'name':'Authorization','value':"=Bearer {{ $('Get Ads read token').first().json.access_token || '' }}"},
          {'name':'developer-token','value':'={{ $env.GOOGLE_ADS_DEVELOPER_TOKEN }}'}, {'name':'login-customer-id','value':'3814278874'}]}
    query='SELECT offline_conversion_upload_client_summary.client, offline_conversion_upload_client_summary.last_upload_date_time, offline_conversion_upload_client_summary.status, offline_conversion_upload_client_summary.alerts, offline_conversion_upload_client_summary.daily_summaries FROM offline_conversion_upload_client_summary'
    for name,q,x in [('Read Ads diagnostics',query,1540),('Read conversion action',"SELECT conversion_action.id, conversion_action.name, conversion_action.status, conversion_action.type FROM conversion_action WHERE conversion_action.id = 7762251563",1760)]:
        nodes.append(http(name,'https://googleads.googleapis.com/v25/customers/3639225242/googleAds:search',x,method='POST',sendHeaders=True,headerParameters=headers,sendBody=True,specifyBody='json',jsonBody=json.dumps({'query':q})))
    evaluate=ROOT.joinpath('audit.js').read_text()+r'''
const start=$('Start check').first().json;
const state=$getWorkflowStaticData('global');
const report=audit({leads:$('Read leads').first().json,queue:$('Read conversion queue').first().json,
 actions:$('Read lead actions').first().json,intake:$('Read intake history').first().json,
 ads:$('Read Ads diagnostics').first().json,action:$('Read conversion action').first().json,intakeCache:state.lastCheck?.intakeCache || [],
 watchOrders:(state.seen||[]).map(k=>k.match(/DCT-\d{8}-\d{6}-[a-f0-9]{8}/i)?.[0]).filter(Boolean)},start.now);
const acknowledged=[
 'missing_queue:DCT-20261022-161336-9ecd047a','missing_queue:DCT-20261031-174655-c7b28629',
 'bad_not_retracted:DCT-20260921-155556-6fa3536e','bad_not_retracted:DCT-20260924-020525-58936292','bad_not_retracted:DCT-20261003-182611-f39e1163'];
const delta=changes(report,state.seen || acknowledged.filter(k=>report.issues.some(i=>i.key===k)));
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const subject=start.testAlert?'DCT conversion monitor — delivery test':`DCT conversion monitor: ${delta.newIssues.length} new issue(s), ${delta.resolved.length} resolved`;
const lines=delta.newIssues.map(i=>`<li><b>${esc(i.order||i.code)}</b>: ${esc(i.message)} Attempts: ${i.attempts}; retries: ${i.retries}. ${esc(i.nextAction)}</li>`).join('');
const diagnostics=report.diagnostics.map(d=>`<li>${esc(d.client)}: ${esc(d.status)}; latest nonempty upload ${esc(d.lastUpload||'unavailable')} (America/Toronto); ${d.errorGroups} error groups.</li>`).join('');
const html=`<h2>${esc(subject)}</h2><p>Account 363-922-5242. Check: ${esc(report.checkedAt)}.</p>`+
 (start.testAlert?'<p>The no-AI n8n monitor can send alerts to Ben. This is a delivery test, not a conversion failure.</p>':'')+
 `<ul>${lines}</ul>`+(delta.resolved.length?`<p>Resolved: ${delta.resolved.map(esc).join(', ')}.</p>`:'')+
 `<p>${report.counts.recentGclid} recent GCLID leads checked; ${report.counts.pendingRetractions} pending retractions. Read requests retry up to three times.</p><ul>${diagnostics}</ul>`+
 '<p>Coverage: lead sheet, queue, authenticated n8n intake history, action/retraction records and Google upload diagnostics. Google does not expose empty scheduled runs or connection-screen mapping/credentials here. The hosting CSV is not part of this check. A stale nonempty-upload timestamp alone is not a failure.</p>'+
 '<p><a href="https://n8.copperchunk.com/workflow/'+$workflow.id+'">Open monitor</a> · <a href="https://ads.google.com/aw/datamanager">Google Data Manager</a></p>';
return [{json:{report,...delta,subject,html,dryRun:start.dryRun,testAlert:start.testAlert,notify:!start.dryRun&&(start.testAlert||delta.newIssues.length>0||delta.resolved.length>0)}}];
'''
    nodes += [code('Reconcile and deduplicate',evaluate,1980),condition('Alert needed','notify',2200),email('Email Ben',2420),
      code('Commit successful check',r'''const data=$('Reconcile and deduplicate').first().json;
const state=$getWorkflowStaticData('global');
if(data.dryRun) state.lastDryRun=data.report;
else if(data.testAlert) state.lastDeliveryTest={at:data.report.checkedAt,executionId:$execution.id};
else {state.seen=data.snapshot;state.lastCheck=data.report;state.lastSuccessfulExecution=$execution.id;
 state.history=[...(state.history||[]),{at:data.report.checkedAt,issues:data.report.issues.length,counts:data.report.counts}].slice(-30);
 if(data.notify) state.lastAlertAt=data.report.checkedAt;}
return [{json:{checkedAt:data.report.checkedAt,issueCount:data.report.issues.length,notified:data.notify,dryRun:data.dryRun}}];''',2640)]
    connections={a:{'main':[[edge(b)]]} for a,b in zip([n['name'] for n in nodes[2:11]],[n['name'] for n in nodes[3:12]])}
    connections['Daily 09:40 Dublin']={'main':[[edge('Start check')]]}
    connections['Private monitor check']={'main':[[edge('Start check')]]}
    connections['Reconcile and deduplicate']={'main':[[edge('Alert needed')]]}
    connections['Alert needed']={'main':[[edge('Email Ben')],[edge('Commit successful check')]]}
    connections['Email Ben']={'main':[[edge('Commit successful check')]]}
    settings={'executionOrder':'v1','timezone':'Europe/Dublin','executionTimeout':900,'saveDataSuccessExecution':'none','saveDataErrorExecution':'none','saveManualExecutions':False}
    if error_id: settings['errorWorkflow']=error_id
    workflow={'name':'DCT | Conversion Queue & Retraction Monitor (no AI)','nodes':nodes,'connections':connections,'settings':settings,'staticData':None}
    failure=[node('Monitor execution failed','n8n-nodes-base.errorTrigger',{},0),
      code('Prepare failure alert',r'''const s=$getWorkflowStaticData('global'); const e=$json.execution||{};
const node=String(e.lastNodeExecuted||'unknown').replace(/[^a-zA-Z0-9 _-]/g,'').slice(0,80);
const test=String(e.error?.message||'').includes('DCT_MONITOR_SELF_TEST');
const key=String($json.workflow?.id||'')+':'+node+':'+new Date().toISOString().slice(0,10)+':'+test;
return [{json:{key,notify:s.lastDelivered!==key,subject:test?'DCT conversion monitor — failure-path test':'DCT conversion monitor failed',html:test?'<p>This confirms the separate monitor-failure alert can reach Ben. It was a deliberate test; no conversion failure was detected.</p>':'<h2>DCT monitor could not complete</h2><p>Check the n8n monitor execution '+String(e.id||'').replace(/\D/g,'')+'. Last node: '+node+'. The monitor retries network reads three times; this failure needs attention. No conversion or lead records were changed.</p>'}}];''',220),
      condition('Failure alert needed','notify',440),email('Email monitor failure',660),
      code('Remember delivered failure',"$getWorkflowStaticData('global').lastDelivered=$('Prepare failure alert').first().json.key;return [{json:{alertDelivered:true}}];",880)]
    fc={a:{'main':[[edge(b)]]} for a,b in [('Monitor execution failed','Prepare failure alert'),('Prepare failure alert','Failure alert needed'),('Failure alert needed','Email monitor failure'),('Email monitor failure','Remember delivered failure')]}
    error={'name':'DCT | Conversion Monitor Failure Alert','nodes':failure,'connections':fc,'settings':{k:v for k,v in settings.items() if k!='errorWorkflow'},'staticData':None}
    return workflow,error

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    for name,w in zip(['workflow','error-workflow'],build()): a.output.joinpath(name+'.json').write_text(json.dumps(w,indent=2)+'\n')
