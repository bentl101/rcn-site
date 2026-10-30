/* Pure renderer: captured submission fields only; no lookups or side effects. */
function renderLeadDiagnostics(lead = {}, brand = '') {
  const present = v => v !== null && v !== undefined && String(v).trim() !== '';
  const text = v => Array.isArray(v) ? v.join(', ') : String(v);
  const esc = v => text(v).replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const value = v => present(v) ? esc(v) : 'Not captured / not supplied';
  const travelFields = ['destination', 'travel_date', 'duration', 'budget', 'guests'];
  const missing = travelFields.filter(k => !present(lead[k]));
  const name = [lead.first_name, lead.last_name].filter(present).join(' ') || lead.name;
  const campaignId = lead.utm_id || (/^\d+$/.test(String(lead.utm_campaign || '')) ? lead.utm_campaign : '');
  const campaignName = lead.campaign_name || (present(lead.utm_campaign) && !/^\d+$/.test(String(lead.utm_campaign)) ? lead.utm_campaign : '');
  const boolean = v => v === true || v === 1 || v === '1' ? 'Yes' : v === false || v === 0 || v === '0' ? 'No' : '';
  const rows = [
    ['Website / lead ID', [brand, lead.lead_order_id].filter(present).join(' / ')],
    ['Submitted at (as recorded)', lead.submitted_at],
    ['Sender name (as supplied)', name], ['Sender email (as supplied)', lead.email], ['Sender phone (as supplied)', lead.phone],
    ['Campaign name', campaignName], ['Campaign ID', campaignId],
    ['UTM source / medium', [lead.utm_source, lead.utm_medium].filter(present).join(' / ')],
    ['UTM campaign (raw)', lead.utm_campaign], ['Ad group ID', lead.adgroupid],
    ['Keyword / UTM term', lead.utm_term], ['Ad / UTM content', lead.utm_content],
    ['Network / match type', [lead.network, lead.matchtype].filter(present).join(' / ')],
    ['Click ID type', lead.click_id_type], ['Click ID', lead.click_id],
    ['GCLID', lead.gclid], ['GBRAID', lead.gbraid], ['WBRAID', lead.wbraid],
    ['Source page', lead.page_source || lead.source_page], ['Landing page', lead.landing_page], ['Referrer', lead.referrer],
    ['IP address (captured by site)', lead.ip_address],
    ['Approximate IP location', [lead.ip_city, lead.ip_region, lead.ip_country].filter(present).join(', ')],
    ['User agent (as reported)', lead.user_agent], ['Device / ad device', [lead.device_type, lead.gad_device].filter(present).join(' / ')],
    ['Browser language', lead.browser_language],
    ['Time on page (seconds, client reported)', lead.time_on_page],
    ['Trip fields absent', missing.length ? missing.join(', ') : 'None of the five checked fields is empty; defaults may be present'],
    ['Destination', lead.destination], ['Travel date', lead.travel_date], ['Duration', lead.duration], ['Budget', lead.budget], ['Guests', lead.guests],
    ['Operator', lead.operator], ['Visitor comments', lead.additional_info || lead.notes],
    ['Honeypot filled', boolean(lead.honeypot_filled)],
    ['Email domain MX valid (existing check)', boolean(lead.email_mx_valid)],
    ['Email mailbox result (existing check)', lead.email_reoon_status],
    ['Disposable email (existing check)', boolean(lead.email_disposable_reoon)],
    ['Phone valid (existing check)', boolean(lead.phone_valid_veriphone)],
    ['Phone type / carrier / region', [lead.phone_line_type, lead.phone_carrier, lead.phone_region].filter(present).join(' / ')],
    ['Existing score / decision', [lead.lead_score, lead.decision].filter(present).join(' / ')],
    ['Existing risk flags', lead.risk_flags], ['Existing score explanation', lead.reason_short],
  ];
  return '<!-- LEAD_DIAGNOSTICS_V1 --><section style="font:14px/1.5 Arial,sans-serif;max-width:760px;margin:0 0 24px;color:#172b3a"><h2>Sender and campaign diagnostics</h2><p>Captured information for manual review. Empty fields are shown explicitly. IP location is approximate; browser details and form values can be spoofed. Sparse details alone do not establish whether this is a bot.</p><table style="border-collapse:collapse;width:100%;table-layout:fixed">' + rows.map(([k,v]) => '<tr><th style="text-align:left;vertical-align:top;width:34%;padding:7px;border:1px solid #ddd;background:#f2f5f7">' + esc(k) + '</th><td style="padding:7px;border:1px solid #ddd;overflow-wrap:anywhere;word-break:break-word;white-space:pre-wrap">' + value(v) + '</td></tr>').join('') + '</table></section><!-- /LEAD_DIAGNOSTICS_V1 -->';
}

// Preserve the existing sales email and its action buttons. Add only fields
// missing from that template, after its details and before the Tern appendix.
function appendLeadDiagnostics(lead = {}, brand = '', original = '') {
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const present = v => v !== null && v !== undefined && String(v).trim() !== '';
  const bool = v => v === true || v === 1 || v === '1' ? 'Yes' : v === false || v === 0 || v === '0' ? 'No' : '';
  const missing = ['destination', 'travel_date', 'duration', 'budget', 'guests'].filter(k => !present(lead[k]));
  const rows = [
    ['User agent', lead.user_agent],
    ...(brand === 'DCT' ? [['IP address', lead.ip_address]] : []),
    ['Trip fields absent', missing.length ? missing.join(', ') : 'None (populated fields may include defaults)'],
    ...(present(lead.honeypot_filled) ? [['Honeypot filled', bool(lead.honeypot_filled)]] : []),
  ];
  const section = '<!-- LEAD_DIAGNOSTICS_V2 --><div style="max-width:600px;font-family:Arial,sans-serif;margin:16px 0"><h3 style="font-size:15px;color:#1A2B3D;margin:0 0 8px">Additional submission details</h3><table style="border-collapse:collapse;width:100%;font-size:14px">' + rows.map(([label, value]) => '<tr><td style="padding:8px 12px;border:1px solid #ddd;background:#f8f9fa;font-weight:bold;width:170px">' + esc(label) + '</td><td style="padding:8px 12px;border:1px solid #ddd;word-break:break-word">' + (present(value) ? esc(value) : 'Not captured / not supplied') + '</td></tr>').join('') + '</table><p style="font-size:12px;color:#666">Browser details can be spoofed; missing fields alone do not prove spam.</p></div><!-- /LEAD_DIAGNOSTICS_V2 -->';
  const marker = '<!-- RCN_TERN_MANUAL_V1 -->';
  const offset = original.indexOf(marker);
  return offset >= 0 ? original.slice(0, offset) + section + original.slice(offset) : original + section;
}

if (typeof module !== 'undefined') module.exports = { renderLeadDiagnostics, appendLeadDiagnostics };
