// Run with node ops/test_rcn_analytics.js. No network requests or sales leads.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('assets/js/rcn-analytics.js', 'utf8');
function scenario({host = 'book.rivercruisenetwork.com', path = '/index.html', search = '', blockedStorage = false, cookie = ''} = {}) {
  const events = [], docListeners = {}, winListeners = {}, formListeners = {}, scripts = [];
  let config;
  const form = {addEventListener: (type, cb) => {formListeners[type] = cb;}};
  const location = {hostname: host, pathname: path, search, origin: 'https://' + host, href: 'https://' + host + path + search};
  const document = {
    referrer: 'https://example.org/?email=private@example.org', cookie,
    head: {appendChild: script => scripts.push(script)},
    createElement: () => ({}), addEventListener: (type, cb) => {docListeners[type] = cb;},
    querySelectorAll: () => [form]
  };
  const ph = {capture: (event, properties) => {
    const item = config.before_send({event, properties}); if (item) events.push(item);
  }, init: (token, options) => {assert.match(token, /^phc_/); config = options; options.loaded(ph);}};
  const window = {posthog: ph, addEventListener: (type, cb) => {winListeners[type] = cb;}};
  const context = {window, location, document, URL, URLSearchParams, setTimeout: cb => cb(),
    localStorage: {getItem: () => {if (blockedStorage) throw Error('blocked'); return null;}},
    performance: {getEntriesByType: () => [{loadEventEnd: 2400, domContentLoadedEventEnd: 1100, responseStart: 450, requestStart: 50, type: 'navigate'}]}
  };
  window.performance = context.performance;
  vm.runInNewContext(source, context);
  if (scripts[0]) scripts[0].onload();
  if (docListeners.DOMContentLoaded) docListeners.DOMContentLoaded();
  return {events, config, formListeners, document, scripts, winListeners, docListeners};
}
let s = scenario({host: 'book.discountcoachtours.ca'});
assert.equal(s.scripts.length, 0, 'DCT must not load RCN analytics');
s = scenario({blockedStorage: true, search: '?rcn_analytics_test=1&email=private@example.org'});
assert.equal(s.events[0].event, '$pageview');
assert.equal(s.events[0].properties.is_test, true);
assert(!JSON.stringify(s.events).includes('private@example.org'), 'URL and referrer query strings must be removed');
assert.equal(s.config.autocapture, false, 'Do not autocapture input values');
assert.equal(s.config.session_recording.maskAllInputs, true);
assert.equal(s.config.session_recording.recordBody, false);
assert.equal(s.config.session_recording.recordHeaders, false);
assert.equal(s.config.person_profiles, 'never');
s.formListeners.focusin({target: {matches: () => true}});
s.formListeners.focusin({target: {matches: () => true}});
assert.equal(s.events.filter(e => e.event === 'rcn_form_started').length, 1);
for (let i = 0; i < 2; i++) s.formListeners.invalid({target: {name: 'email', value: 'private@example.org', validity: {typeMismatch: true}}});
assert.equal(s.events.filter(e => e.event === 'rcn_form_validation_error').length, 1);
assert(!JSON.stringify(s.events).includes('private@example.org'));
s.formListeners.submit({defaultPrevented: true});
assert(!s.events.some(e => e.event === 'rcn_form_submit_attempted'));
s.formListeners.submit({defaultPrevented: false});
s.formListeners.submit({defaultPrevented: false});
assert.equal(s.events.filter(e => e.event === 'rcn_form_submit_attempted').length, 1);
s.winListeners.load();
assert.equal(s.events.find(e => e.event === 'rcn_page_load').properties.ttfb_ms, 400);
let scrubbed = s.config.before_send({event: '$exception', properties: {$current_url:'https://example.org/?secret=private', $exception_list: [{value: 'Failed for private@example.org at https://example.org/?secret=private'}]}});
assert(!JSON.stringify(scrubbed).includes('private'));
s = scenario({path: '/thank-you.html'});
assert(!s.events.some(e => e.event === 'rcn_lead_received'), 'Direct thank-you visits are not leads');
s = scenario({path: '/thank-you.html', cookie: 'other=1; rcn_lead_received=1'});
assert(s.events.some(e => e.event === 'rcn_lead_received'));
assert(s.document.cookie.includes('Max-Age=0'), 'Confirmation marker is consumed');
s = scenario({search: '?error=1'});
assert(s.events.some(e => e.event === 'rcn_form_handler_error'));
for (const file of ['index.html', 'avalon-waterways.html', 'scenic-river-cruise.html', 'emerald-river-cruise.html', 'amawaterways-river-cruise.html', 'viking-river-cruise.html']) {
  const html = fs.readFileSync(file, 'utf8');
  assert(html.includes('<label for="destination">Preferred Itinerary *</label>'), file);
  assert(html.includes('name="destination"') && /name="destination"[^>]*required/.test(html), file);
  assert.equal((html.match(/src="assets\/js\/rcn-analytics.js/g) || []).length, 1);
  assert(html.includes('action="submit-v2.php"'));
}
const thanks = fs.readFileSync('thank-you.html', 'utf8');
assert(thanks.includes('AW-10929471967/wib4COjkqbQcEN-Dytso'));
assert(!thanks.includes('AW-10929471967/wiFkCM3XupwYEN-Dytso'));
console.log('PASS: RCN isolation, privacy, blocked storage, funnel events, confirmation deduplication, load timing, destination asterisks and Ads baseline.');
