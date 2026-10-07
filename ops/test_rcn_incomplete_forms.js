// Behavioural checks without a browser, network calls or lead creation.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const callbacks = {}, timers = [], requests = [];
const fields = ['first_name', 'email', 'phone', 'destination', 'travel_date', 'duration', 'guests', 'budget', 'operator'];
const elements = fields.map(name => ({name, value: '', willValidate: true, validity: {valueMissing: true}}));
elements.push({name: 'click_id', value: 'secret-click-id', willValidate: false, validity: {valueMissing: false}});
elements.namedItem = name => elements.find(el => el.name === name);
const form = {elements, addEventListener: (event, cb) => { callbacks[event] = cb; }};
vm.runInNewContext(fs.readFileSync('assets/js/rcn-incomplete-forms.js', 'utf8'), {
  document: {querySelectorAll: () => [form]}, window: {location: {pathname: '/index.html', search: '?rcn_analytics_test=1&gclid=private'}},
  URLSearchParams, setTimeout: cb => {timers.push(cb); return timers.length;},
  fetch: (url, options) => { requests.push({url, options}); return Promise.resolve({status: 200}); }
});
assert.equal(requests.length, 0, 'No capture on load');
assert.deepEqual(Object.keys(callbacks), ['invalid'], 'No typing or successful-submission interception');
elements[0].value = 'TEST'; elements[0].validity.valueMissing = false;
callbacks.invalid({target: elements[0]});
assert.equal(timers.length, 0, 'Non-missing validation errors do not trigger these emails');
elements.slice(1, 9).forEach(target => callbacks.invalid({target}));
assert.equal(timers.length, 1, 'One notification for the native invalid-field burst');
timers.shift()();
assert.equal(requests.length, 1);
const payload = JSON.parse(requests[0].options.body);
assert.equal(payload.fields.first_name, 'TEST');
assert.equal(payload.fields.email, '');
assert.equal(payload.is_test, true);
assert.equal(payload.page, '/index.html');
assert(!requests[0].options.body.includes('secret-click-id'));
assert(!requests[0].options.body.includes('gclid'));
assert.equal(requests[0].url, '/incomplete-form.php');
callbacks.invalid({target: elements[1]}); timers.shift()();
assert.equal(requests.length, 1, 'Repeated identical attempt is deduplicated');
elements[0].value = 'CHANGED';
callbacks.invalid({target: elements[1]}); timers.shift()();
assert.equal(requests.length, 2, 'Changed attempt gets a new notification');
console.log('PASS: one notification per missing-field burst, no typing capture, field allowlist, deduplication, changed-attempt capture, test labelling.');
