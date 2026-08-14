#!/usr/bin/env node
/* Offline unit matrix for the live n8n Parse Score node. */
const fs = require('fs');

const workflowPath = process.argv[2];
if (!workflowPath) throw new Error('usage: test_rcn_contact_policy.js WORKFLOW.json');
const workflow = JSON.parse(fs.readFileSync(workflowPath, 'utf8'));
const parseNode = workflow.nodes.find((node) => node.name === 'Parse Score');
if (!parseNode) throw new Error('Parse Score node missing');
const parseLead = new Function('$input', '$', parseNode.parameters.jsCode);

function run(overrides = {}, envelope = null) {
  const body = {
    first_name: 'Test', last_name: 'Lead', email: 'lead@example.com',
    phone: '4165550199', destination: 'Danube', additional_info: '',
    page_source: 'Avalon Waterways', operator: 'Avalon Waterways',
    budget: '$5,000 – $8,000', duration: '10 nights', guests: '2',
    ...overrides.body,
  };
  const features = {
    phone_valid_shape: true, phone_valid_veriphone: true,
    phone_fictional: false, phone_repeating: false,
    email_mx_valid: true, email_mailbox_valid: true,
    email_disposable: false, email_disposable_reoon: false,
    months_until_travel: 6,
    ...overrides.features,
  };
  const scorer = envelope || {
    choices: [{message: {content: JSON.stringify({
      lead_score: overrides.score ?? 80,
      lead_quality: 'good', decision: 'send_to_sales',
      destination_validity: 'valid_river_cruise', confidence: 0.9,
      reason_short: 'coherent test lead', risk_flags: [], sales_note: 'test',
    })}}],
    _scorer_model: 'unit-test',
  };
  const input = {first: () => ({json: scorer})};
  const lookup = (name) => {
    if (name !== 'Build Signals') throw new Error(`unexpected node lookup ${name}`);
    return {first: () => ({json: {body, _features: features, _scorer_t0: Date.now()}})};
  };
  return parseLead(input, lookup)[0].json.body;
}

const cases = [
  ['valid phone + valid email scores normally', {}, 80, 'send_to_sales'],
  ['valid phone + invalid email scores normally', {features: {email_mx_valid: false, email_mailbox_valid: false}, score: 70}, 70, 'send_to_sales'],
  ['invalid phone + valid email quarantines', {features: {phone_valid_shape: false, phone_valid_veriphone: false}, body: {phone: '12345'}, score: 95}, 50, 'review'],
  ['missing phone + valid email quarantines', {body: {phone: ''}, features: {phone_valid_shape: false, phone_valid_veriphone: false}, score: 95}, 50, 'review'],
  ['both invalid suppresses as spam', {body: {phone: '', email: 'bad'}, features: {phone_valid_shape: false, phone_valid_veriphone: false, email_mx_valid: false, email_mailbox_valid: false}, score: 95}, 25, 'suppress'],
  ['phone verifier outage fail-opens valid shape', {features: {phone_valid_veriphone: null}, score: 80}, 80, 'send_to_sales'],
  ['verifier outage cannot rescue invalid shape', {body: {phone: '12345'}, features: {phone_valid_shape: false, phone_valid_veriphone: null}, score: 90}, 50, 'review'],
  ['valid international verification overrides local shape', {body: {phone: '+442079460958'}, features: {phone_valid_shape: false, phone_valid_veriphone: true}, score: 80}, 80, 'send_to_sales'],
  ['do-not-phone note does not penalize valid phone', {body: {additional_info: 'Please do not phone; email me.'}, score: 80}, 80, 'send_to_sales'],
];

const results = [];
for (const [name, input, expectedScore, expectedDecision] of cases) {
  const actual = run(input);
  if (actual.lead_score !== expectedScore || actual.decision !== expectedDecision) {
    throw new Error(`${name}: expected ${expectedScore}/${expectedDecision}, got ${actual.lead_score}/${actual.decision}`);
  }
  results.push({name, score: actual.lead_score, decision: actual.decision});
}

const scorerErrorSpam = run({
  body: {phone: '', email: 'bad'},
  features: {phone_valid_shape: false, phone_valid_veriphone: false, email_mx_valid: false, email_mailbox_valid: false},
}, {choices: [{message: {content: ''}}], _scorer_model: 'unit-test-error'});
if (scorerErrorSpam.lead_score !== 25 || scorerErrorSpam.decision !== 'suppress') {
  throw new Error(`scorer error both-invalid: got ${scorerErrorSpam.lead_score}/${scorerErrorSpam.decision}`);
}
results.push({name: 'scorer error cannot bypass both-invalid spam', score: 25, decision: 'suppress'});
console.log(JSON.stringify(results, null, 2));
