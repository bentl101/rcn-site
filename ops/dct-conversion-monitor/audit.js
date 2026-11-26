'use strict';

// Pure, read-only reconciliation. Never returns click IDs, contact data or tokens.
function audit(inputs, nowIso) {
  const now = new Date(nowIso).getTime();
  const day = 86400000, cutoff = now - 32 * day, intakeCutoff = now - 7 * day;
  const action = 'customers/3639225242/conversionActions/7762251563';
  const actionName = 'DCT - Submit Lead Form (Data Manager - GCLID)';
  const issues = [];
  const add = (code, order, message, nextAction, attempts = 0, variant = '') => {
    if (order && !/^DCT-\d{8}-\d{6}-[a-f0-9]{8}$/i.test(order)) order = '';
    issues.push({key: [code, order, variant].filter(Boolean).join(':'), code, order,
      message, nextAction, attempts, retries: Math.max(0, attempts - 1)});
  };
  const stamp = value => {
    const s = String(value || '').trim();
    return s ? Date.parse(s.replace(' ', 'T') + (/(?:Z|[+-]\d\d:?\d\d)$/i.test(s) ? '' : 'Z')) : NaN;
  };
  const yes = x => ['1', 'true', 'yes'].includes(String(x).toLowerCase());
  const qa = r => yes(r.qa_test) || yes(r.ads_validate_only) || /(?:QA|TEST)/i.test(r.lead_order_id || '');
  const gclid = r => Boolean(String(r.gclid || '').trim()) || (r.click_id_type === 'gclid' && Boolean(r.click_id));
  const errorCodes = x => [...new Set(String(x || '').match(/\b(?:UNAUTHENTICATED|PERMISSION_DENIED|INVALID_ARGUMENT|CONVERSION_NOT_FOUND|RESOURCE_EXHAUSTED|UNAVAILABLE|INTERNAL|DEADLINE_EXCEEDED|INVALID_CONVERSION_ACTION|EXPIRED_EVENT|invalid_grant|ECONNABORTED|ETIMEDOUT)\b/g) || [])].join(', ') || 'See private workflow execution';
  const readFailure = (name, input) => {
    const raw = JSON.stringify(input?.error || input?.message || '');
    const status = raw.match(/\b(400|401|403|404|408|429|500|502|503|504)\b/)?.[0];
    const reason = status ? 'HTTP '+status : errorCodes(raw);
    add('source_unavailable', '', name + ' could not be read completely. '+reason, 'Check the named n8n read node and its credential; monitoring cannot confirm health.', 0, name);
  };
  function table(input, required, name) {
    if (!input || input.error || !Array.isArray(input.valueRanges)) { readFailure(name,input); return null; }
    const out = [];
    for (const vr of input.valueRanges) {
      const rows = vr.values;
      if (!Array.isArray(rows) || !rows.length || !Array.isArray(rows[0])) { readFailure(name); return null; }
      const heads = rows[0];
      rows.slice(1).forEach((row, i) => {out[i] ||= {}; heads.forEach((h, j) => out[i][h] = row[j] ?? '');});
    }
    const heads = input.valueRanges.flatMap(r => r.values[0]);
    if (required.some(h => !heads.includes(h))) { add('source_schema', '', name + ' headers changed.', 'Restore the expected source mapping or update this monitor after review.', 0, name); return null; }
    return out;
  }
  const leads = table(inputs.leads, ['lead_order_id','submitted_at','gclid','qa_test','ads_validate_only','ads_upload_status','ads_conversion_action','manual_action','decision','lead_status'], 'Leads');
  const queue = table(inputs.queue, ['Google Click ID','Conversion action','Conversion date/time','Order ID','Import status'], 'Conversion queue');
  const actions = table(inputs.actions, ['event_id','lead_order_id','requested_action','ads_result','ads_attempt_count','ads_next_attempt_at_utc','ads_due_at_utc'], 'Lead Actions');
  const lm = new Map((leads || []).filter(r=>r.lead_order_id).map(r=>[r.lead_order_id,r]));
  const qm = new Map();
  for (const row of queue || []) {
    const id = String(row['Order ID'] || ''); if (!id) continue;
    if (qm.has(id)) add('duplicate_queue',id,'More than one queue row has this Order ID.','Review the duplicate rows without resending an accepted conversion.');
    qm.set(id,row);
  }
  const badIds = new Set((leads || []).filter(r=>String(r.manual_action).startsWith('bad') || ['bad','rejected'].includes(r.lead_status)).map(r=>r.lead_order_id));
  for (const a of actions || []) {
    if (a.requested_action === 'bad' && !['invalid_event','duplicate_ignored'].includes(a.result)) badIds.add(a.lead_order_id);
  }
  let recentGclid = 0, trackedOlderGclid = 0, eligible = 0, withheld = 0, pendingRetractions = 0;
  for (const r of leads || []) {
    if (qa(r) || !gclid(r) || (stamp(r.submitted_at) < cutoff && !(inputs.watchOrders || []).includes(r.lead_order_id))) continue;
    const id = r.lead_order_id, q = qm.get(id);
    if (stamp(r.submitted_at)<cutoff) trackedOlderGclid++; else recentGclid++;
    if (!Number.isFinite(stamp(r.submitted_at))) add('invalid_timestamp',id,'Lead timestamp is invalid.','Check the submitted_at source cell.');
    const bad = badIds.has(id);
    const hold = (r.ads_upload_status === 'withheld_quarantine' && r.lead_status === 'quarantine' && r.decision === 'review') ||
      (r.ads_upload_status === 'withheld_spam' && r.lead_status === 'spam' && r.decision === 'suppress') || r.ads_upload_status === 'duplicate_submission';
    if (hold && !bad) withheld++;
    if (!bad && !hold) {
      eligible++;
      // Email-button approvals of held leads upload directly from the action
      // workflow and never write a queue row. Exempt them only when the lead
      // projection AND a confirmed Lead Actions upload receipt both agree.
      const manualUploaded = r.decision === 'review' && r.lead_status === 'approved' &&
        r.manual_action === 'good_uploaded' && r.ads_upload_status === 'accepted' &&
        (actions || []).some(a => a.lead_order_id === id && a.requested_action === 'good' &&
          a.result === 'manual_uploaded' && a.ads_result === 'accepted');
      if (queue && !q && !manualUploaded) add('missing_queue', id, 'Eligible GCLID lead is missing from the conversion queue.', r.ads_upload_status === 'accepted' ? 'Repair queue mirroring using uploaded_api; do not resend the accepted conversion.' : 'Inspect intake/approval logging and recover the missing queue row with its original Order ID.');
      if (r.ads_conversion_action && r.ads_conversion_action !== action) add('wrong_lead_action', id, 'GCLID lead has an unexpected conversion action.', 'Review routing and historic receipts before changing or replaying anything.');
      if (!['accepted','queued_data_manager','failed','rejected','error','pending','manual_retry','manual_upload_failed',''].includes(r.ads_upload_status)) add('unexpected_upload_status', id, 'Unrecognized eligible-lead upload status.', 'Inspect this lead and update monitoring only after verifying the status semantics.');
    }
    if (!q) continue;
    if (q['Conversion action'] !== actionName) add('wrong_queue_action',id,'Queue row does not use the expected DCT conversion action.','Check queue mapping against action 7762251563.');
    if (r.gclid && q['Google Click ID'] !== r.gclid) add('click_id_mismatch',id,'Queue click ID differs from the private lead record.','Compare the private records; preserve the original conversion identity.');
    const status = String(q['Import status']);
    if (bad && status !== 'retracted') add(status === 'active' ? 'bad_active' : 'bad_not_retracted',id, status === 'active' ? 'Bad lead remains active for import.' : 'Bad lead queue row is inactive but is not labelled retracted.', 'Reconcile the queue label with the accepted retraction; do not resend the conversion.');
    if (hold && status === 'active') add('withheld_active',id,'A withheld lead is active for import.','Inspect the eligibility gate and stop unintended import after review.');
    if (!bad && !hold && !['active','uploaded_api','uploaded_dm'].includes(status)) add('unexpected_queue_status',id,'Eligible queue row has an unexpected import status.','Review the row status; accepted API/DM rows must remain inactive.');
  }
  for (const [id,q] of qm) {
    const recordedLead = lm.get(id);
    if (badIds.has(id) && recordedLead && gclid(recordedLead) && !qa(recordedLead) && q['Import status'] !== 'retracted' && !issues.some(i=>['bad_active','bad_not_retracted'].includes(i.code)&&i.order===id)) {
      add(q['Import status']==='active'?'bad_active':'bad_not_retracted',id,q['Import status']==='active'?'Bad lead remains active for import.':'Bad lead queue row is inactive but is not labelled retracted.','Reconcile the queue label with the accepted retraction; do not resend the conversion.');
    }
    if (q['Import status'] !== 'active') continue;
    if (leads && !lm.has(id)) add('orphan_active',id,'Active queue row has no matching lead record.','Review the private lead log before the next import.');
    if (q['Conversion action'] !== actionName && !issues.some(i=>i.code==='wrong_queue_action'&&i.order===id)) add('wrong_queue_action',id,'Active row has an unexpected conversion action.','Check action 7762251563 and the source mapping.');
    if (badIds.has(id) && !issues.some(i=>i.code==='bad_active'&&i.order===id)) add('bad_active',id,'Bad lead remains active for import.','Reconcile the queue immediately after reviewing its retraction.');
  }
  for (const a of actions || []) {
    if (!a.lead_order_id || a.requested_action !== 'bad' || qa(lm.get(a.lead_order_id) || {})) continue;
    if (['duplicate_ignored','invalid_event','bad_no_conversion','rejected'].includes(a.result) || ['accepted','already_retracted','state_changed','not_eligible'].includes(a.ads_result)) continue;
    // A rejected, never-uploaded lead has no Ads retraction to process.
    if (!a.ads_due_at_utc && !a.ads_next_attempt_at_utc && !a.ads_conversion_action && !Number(a.ads_attempt_count)) continue;
    const attempts = Number(a.ads_attempt_count || 0), next = stamp(a.ads_next_attempt_at_utc || a.ads_due_at_utc);
    const lead = lm.get(a.lead_order_id), age = lead ? (now-stamp(lead.submitted_at))/day : 0;
    if (['expired','failed','terminal_failure','lead_not_found'].includes(a.ads_result) || /(?:expired|failed)$/.test(a.result || '') || age > 54) {
      add('retraction_terminal',a.lead_order_id,'Retraction failed or expired: '+errorCodes(a.detail),'Inspect the action receipt and resolve manually; preserve its original Order ID.',attempts,a.ads_result || 'expired'); continue;
    }
    if (!a.ads_processed_at_utc) {
      pendingRetractions++;
      if (!Number.isFinite(next) || next < now-30*60000) add('retraction_overdue',a.lead_order_id,'Retraction next attempt is missing or over 30 minutes overdue.','Check the DCT Lead Email Actions worker and its latest execution.',attempts);
      if (attempts >= 3) add('retraction_retries',a.lead_order_id,'Retraction is repeatedly retrying: '+errorCodes(a.detail),'Check the latest Google error and the next scheduled retry.',attempts,String(attempts < 5 ? 3 : Math.floor(attempts/5)*5));
    }
  }
  let intakeCount = 0;
  const intakeCache = new Map((inputs.intakeCache || []).filter(e=>stamp(e.startedAt)>=intakeCutoff).map(e=>[e.order,e]));
  const intake = inputs.intake;
  if (!intake || intake.error || !Array.isArray(intake.data)) readFailure('n8n intake history',intake);
  else {
    const rows = intake.data;
    if (intake.nextCursor && (!rows.length || Math.min(...rows.map(e=>stamp(e.startedAt))) > intakeCutoff)) add('intake_history_truncated','','Intake history does not cover the full seven-day check.','Increase the bounded page limit or add pagination before trusting reconciliation.');
    for (const e of rows) {
      if (stamp(e.startedAt)<intakeCutoff || stamp(e.startedAt)>now-30*60000) continue;
      const run = e.data?.resultData?.runData;
      const body = run?.['Verify Token']?.[0]?.data?.main?.[0]?.[0]?.json?.body;
      if (!run) { add('intake_data_missing','','Retained intake execution is missing its audit data.','Inspect n8n execution retention; the independent lead check is incomplete.'); continue; }
      if (!body || qa(body) || !gclid(body) || !/^DCT-\d{8}-\d{6}-[a-f0-9]{8}$/i.test(body.lead_order_id || '')) continue;
      intakeCache.set(body.lead_order_id,{order:body.lead_order_id,startedAt:e.startedAt,status:e.status,executionId:String(e.id).replace(/\D/g,'')});
    }
  }
  for (const e of intakeCache.values()) {
    intakeCount++;
    if (leads && !lm.has(e.order)) add('missing_lead',e.order,'Authenticated GCLID intake is missing from the private lead sheet.','Inspect its intake execution and recover logging before considering any upload.');
    if (e.status !== 'success') add('intake_failed',e.order,'Authenticated intake execution did not complete successfully.','Inspect DCT Form Handler execution '+e.executionId+'.');
  }
  const diag = inputs.ads;
  let diagnostics = [];
  if (!diag || diag.error || !Array.isArray(diag.results) || !diag.results.length) readFailure('Google Ads diagnostics',diag);
  else {
    diagnostics = diag.results.map(r=>r.offlineConversionUploadClientSummary).filter(Boolean).map(r=>({client:r.client,status:r.status,lastUpload:r.lastUploadDateTime || '',alerts:r.alerts || [],failedCount:(r.dailySummaries||[]).reduce((s,d)=>s+Number(d.failedCount||0),0)}));
    for (const d of diagnostics) {
      if (['NEEDS_ATTENTION','URGENT','POOR'].includes(d.status) || d.alerts.length || d.failedCount) add('ads_diagnostics','','Google '+d.client+' status '+d.status+'; '+d.alerts.length+' error groups; '+d.failedCount+' failed events.','Open Google Ads upload diagnostics and inspect the reported errors.',0,d.client+':'+d.status+':'+JSON.stringify(d.alerts));
    }
    const connector = diagnostics.find(d=>d.client==='ADS_DATA_CONNECTOR');
    for (const [id,q] of qm) {
      // API dates are account-local, so require a newer calendar date rather than treating them as UTC.
      const queuedDay = String(q['Conversion date/time'] || '').slice(0,10);
      if (q['Import status']==='active' && stamp(q['Conversion date/time'])<now-36*3600000 && (!connector || connector.lastUpload.slice(0,10)<=queuedDay)) add('fallback_stalled',id,'Active fallback row is over 36 hours old with no newer connector upload receipt.','Inspect the Data Manager connection, schedule, credentials and row errors; do not assume an empty-run timestamp proves failure.');
    }
  }
  const settings = inputs.action;
  if (!settings || settings.error || !Array.isArray(settings.results) || settings.results.length !== 1) readFailure('Conversion action',settings);
  else {
    const a = settings.results[0].conversionAction;
    if (!a || a.id !== '7762251563' || a.name !== actionName || a.status !== 'ENABLED' || a.type !== 'UPLOAD_CLICKS') add('action_config','','The expected DCT conversion action is missing, disabled or changed.','Inspect action 7762251563 before changing any queue records.');
  }
  const unique = [...new Map(issues.map(i=>[i.key,i])).values()].sort((a,b)=>a.key.localeCompare(b.key));
  return {checkedAt:new Date(now).toISOString(),customerId:'3639225242',issues:unique,intakeCache:[...intakeCache.values()],
    counts:{leads:leads?.length ?? null,queue:qm.size,recentGclid,trackedOlderGclid,eligible,withheld,intakeCount,pendingRetractions},
    diagnostics:diagnostics.map(({alerts,...d})=>({...d,errorGroups:alerts.length})),
    coverage:{leadLookbackDays:32,intakeLookbackDays:7,intakeHistoryStart:[...intakeCache.values()].map(e=>e.startedAt).sort()[0] || null,source:'authenticated n8n intake history, cached as non-PII IDs for seven days',rawHostingCsv:false,emptyDataManagerRuns:false,connectionUiMapping:false},
    latestRunNote:'Google lastUpload is the last nonempty upload in America/Toronto, not the latest scheduled Data Manager run.'};
}

function changes(report, previous = []) {
  const known = new Set(previous), current = report.issues.map(i=>i.key);
  const incomplete=report.issues.some(i=>['source_unavailable','source_schema','intake_history_truncated','intake_data_missing'].includes(i.code));
  return {newIssues:report.issues.filter(i=>!known.has(i.key)),resolved:incomplete?[]:previous.filter(k=>!current.includes(k)),snapshot:incomplete?[...new Set([...previous,...current])]:current};
}
if (typeof module !== 'undefined') module.exports = {audit,changes};
