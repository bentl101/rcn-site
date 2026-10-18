// Run with node ops/test_rcn_analytics.js. No network requests or sales leads.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('assets/js/rcn-analytics.js', 'utf8');
function scenario({host = 'book.rivercruisenetwork.com', path = '/index.html', search = '', blockedStorage = false, optOut = false, cookie = '', clarityMode = 'existing', loadSdk = true} = {}) {
  const events = [], clarityCalls = [], docListeners = {}, winListeners = {}, formListeners = {}, scripts = [];
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
  const existingClarity = function () {
    if (clarityMode === 'throws') throw Error('Clarity unavailable');
    clarityCalls.push(Array.from(arguments));
  };
  if (clarityMode !== 'absent') window.clarity = existingClarity;
  const context = {window, location, document, URL, URLSearchParams, setTimeout: cb => cb(),
    localStorage: {getItem: () => {if (blockedStorage) throw Error('blocked'); return optOut ? '1' : null;}},
    performance: {getEntriesByType: () => [{loadEventEnd: 2400, domContentLoadedEventEnd: 1100, responseStart: 450, requestStart: 50, type: 'navigate'}]}
  };
  window.performance = context.performance;
  vm.runInNewContext(source, context);
  if (loadSdk && scripts[0]) scripts[0].onload();
  if (docListeners.DOMContentLoaded) docListeners.DOMContentLoaded();
  return {events, config, formListeners, document, scripts, winListeners, docListeners, window, clarityCalls, existingClarity};
}
function tagged(s, name, value) {
  return s.clarityCalls.some(call => call[0] === 'set' && call[1] === name && call[2] === value);
}
function clarityEventCount(s, name) {
  return s.clarityCalls.filter(call => call[0] === 'event' && call[1] === name).length;
}
function invalid(s, name, validity = {valueMissing: true}) {
  s.formListeners.invalid({target: {name, value: 'private@example.org', validity}});
}
let s = scenario({host: 'book.discountcoachtours.ca'});
assert.equal(s.scripts.length, 0, 'DCT must not load RCN analytics');
assert.equal(s.clarityCalls.length, 0, 'DCT must not receive RCN Clarity tags');
s = scenario({optOut: true, clarityMode: 'absent'});
assert.equal(s.scripts.length, 0, 'Opt-out must suppress the SDK');
assert.equal(s.window.clarity, undefined, 'Opt-out must suppress the Clarity queue');
s = scenario({blockedStorage: true, search: '?rcn_analytics_test=1&email=private@example.org'});
assert.equal(s.window.clarity, s.existingClarity, 'Respect the existing Clarity function');
assert(tagged(s, 'site', 'rcn'));
assert(tagged(s, 'analytics_test', 'true'));
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
assert.equal(clarityEventCount(s, 'rcn_form_started'), 1);
assert(tagged(s, 'enquiry_started', 'yes'));
for (let i = 0; i < 2; i++) s.formListeners.invalid({target: {name: 'email', value: 'private@example.org', validity: {typeMismatch: true}}});
assert.equal(s.events.filter(e => e.event === 'rcn_form_validation_error').length, 1);
assert(!JSON.stringify(s.events).includes('private@example.org'));
assert.equal(clarityEventCount(s, 'rcn_form_validation_error'), 1);
assert(tagged(s, 'watch_reason', 'repeated_validation'));
assert(tagged(s, 'watch', 'qa'));
assert(!tagged(s, 'watch', 'yes'), 'QA must stay out of the ordinary watch queue');
s.formListeners.submit({defaultPrevented: true});
assert(!s.events.some(e => e.event === 'rcn_form_submit_attempted'));
assert(!tagged(s, 'enquiry_submit_attempted', 'yes'));
s.formListeners.submit({defaultPrevented: false});
s.formListeners.submit({defaultPrevented: false});
assert.equal(s.events.filter(e => e.event === 'rcn_form_submit_attempted').length, 1);
assert.equal(clarityEventCount(s, 'rcn_form_submit_attempted'), 1);
assert(tagged(s, 'enquiry_submit_attempted', 'yes'));
assert(!tagged(s, 'enquiry_received', 'yes'), 'A submit attempt is not a received lead');
assert(!JSON.stringify(s.clarityCalls).includes('private'), 'No form values, URLs or referrers in Clarity calls');
s.winListeners.load();
assert.equal(s.events.find(e => e.event === 'rcn_page_load').properties.ttfb_ms, 400);
let scrubbed = s.config.before_send({event: '$exception', properties: {$current_url:'https://example.org/?secret=private', $exception_list: [{value: 'Failed for private@example.org at https://example.org/?secret=private'}]}});
assert(!JSON.stringify(scrubbed).includes('private'));
s = scenario({path: '/thank-you.html'});
assert(!s.events.some(e => e.event === 'rcn_lead_received'), 'Direct thank-you visits are not leads');
assert(tagged(s, 'analytics_test', 'false'));
assert(tagged(s, 'enquiry_thank_you_viewed', 'yes'));
assert(tagged(s, 'watch_reason', 'thank_you_visit'));
assert(!tagged(s, 'enquiry_received', 'yes'), 'Direct thank-you visits must not be tagged as received leads');
assert.equal(clarityEventCount(s, 'rcn_lead_received'), 0);
s = scenario({path: '/thank-you.html', cookie: 'other=1; rcn_lead_received=1'});
assert(s.events.some(e => e.event === 'rcn_lead_received'));
assert(s.document.cookie.includes('Max-Age=0'), 'Confirmation marker is consumed');
assert(tagged(s, 'enquiry_received', 'yes'));
assert(tagged(s, 'watch_reason', 'lead_received'));
assert.equal(clarityEventCount(s, 'rcn_lead_received'), 1);
s.docListeners.DOMContentLoaded();
assert.equal(clarityEventCount(s, 'rcn_lead_received'), 1, 'Confirmation event is deduplicated');
assert.equal(clarityEventCount(s, 'rcn_thank_you_viewed'), 1, 'Thank-you event is deduplicated');
s = scenario({search: '?error=1'});
assert(s.events.some(e => e.event === 'rcn_form_handler_error'));
assert(tagged(s, 'watch', 'yes'));
assert(tagged(s, 'watch_reason', 'form_handler_error'));
assert.equal(clarityEventCount(s, 'rcn_form_handler_error'), 1);
s.docListeners.DOMContentLoaded();
assert.equal(clarityEventCount(s, 'rcn_form_handler_error'), 1, 'Clarity reasons/events are once per page');
assert.equal(s.clarityCalls.filter(call => call[1] === 'watch_reason').length, 1);
s = scenario();
['first_name', 'last_name', 'email', 'phone', 'destination'].forEach(name => invalid(s, name));
assert(!tagged(s, 'watch_reason', 'repeated_validation'), 'One native invalid burst across several fields is not repeated validation');
invalid(s, 'unknown_private_field');
invalid(s, 'unknown_private_field');
assert(!tagged(s, 'watch_reason', 'repeated_validation'), 'Unknown fields must not create watch tags');
invalid(s, 'email', {typeMismatch: true});
assert(tagged(s, 'watch_reason', 'repeated_validation'), 'Second invalid event for the same allowlisted field is repeated validation');
assert.equal(s.events.filter(e => e.event === 'rcn_form_validation_error' && e.properties.field_name === 'email').length, 2, 'PostHog retains its existing field/reason deduplication');
assert.equal(clarityEventCount(s, 'rcn_form_validation_error'), 1, 'Clarity receives no field names or validation reasons');
const callsBeforeClick = s.clarityCalls.length;
s.docListeners.click({target: {closest: () => ({getAttribute: () => 'tel:123456789'})}});
assert(s.events.some(e => e.event === 'rcn_phone_click'));
assert.equal(s.clarityCalls.length, callsBeforeClick, 'Unrelated click events remain outside the Clarity review scope');

// Errors must flag Clarity both before and after PostHog initialization, while
// only the startup path captures PostHog exceptions itself.
s = scenario({loadSdk: false});
s.winListeners.error({message: 'private@example.org https://example.org/?lead=secret'});
s.winListeners.unhandledrejection({reason: Error('private@example.org lead-id=RCN-private')});
assert(tagged(s, 'watch_reason', 'javascript_error'));
assert(tagged(s, 'watch_reason', 'unhandled_rejection'));
assert(!JSON.stringify(s.clarityCalls).includes('private'));
s.scripts[0].onload();
assert.equal(s.events.filter(e => e.event === '$exception').length, 2);
s.winListeners.error({message: 'another private error'});
s.winListeners.unhandledrejection({reason: 'another private rejection'});
assert.equal(s.events.filter(e => e.event === '$exception').length, 2, 'PostHog SDK takes over exceptions after initialization');
assert.equal(s.clarityCalls.filter(call => call[1] === 'watch_reason').length, 2, 'Each reason is deduplicated');
s = scenario();
s.winListeners.error({message: 'private after init'});
s.winListeners.unhandledrejection({reason: 'private after init'});
assert(tagged(s, 'watch_reason', 'javascript_error'));
assert(tagged(s, 'watch_reason', 'unhandled_rejection'));
assert.equal(s.events.filter(e => e.event === '$exception').length, 0);

// A late GTM tag receives the standard queued calls; no extra script is added.
s = scenario({clarityMode: 'absent', search: '?error=1&rcn_analytics_test=1&lead_id=RCN-private'});
assert.equal(s.scripts.length, 1);
assert(s.scripts[0].src.includes('posthog.com'));
const queued = Array.from(s.window.clarity.q, args => Array.from(args));
assert(queued.some(call => call[1] === 'watch' && call[2] === 'qa'));
assert(!JSON.stringify(queued).includes('private'));
s.window.clarity = (...args) => s.clarityCalls.push(args);
queued.forEach(args => s.window.clarity(...args));
s.formListeners.focusin({target: {matches: () => true}});
assert(tagged(s, 'enquiry_started', 'yes'));
assert.equal(clarityEventCount(s, 'rcn_form_handler_error'), 1);
s = scenario({clarityMode: 'throws', search: '?error=1'});
s.formListeners.focusin({target: {matches: () => true}});
invalid(s, 'email'); invalid(s, 'email');
s.formListeners.submit({defaultPrevented: false});
s.winListeners.error({message: 'unavailable'});
s.winListeners.unhandledrejection({reason: 'unavailable'});
assert(s.events.some(e => e.event === 'rcn_form_started'));
assert(s.events.some(e => e.event === 'rcn_form_submit_attempted'), 'Clarity failures do not stop the form/PostHog flow');
for (const file of ['index.html', 'avalon-waterways.html', 'scenic-river-cruise.html', 'emerald-river-cruise.html', 'amawaterways-river-cruise.html', 'viking-river-cruise.html']) {
  const html = fs.readFileSync(file, 'utf8');
  assert(html.includes('<label for="destination">Preferred Itinerary *</label>'), file);
  assert(html.includes('name="destination"') && /name="destination"[^>]*required/.test(html), file);
  assert.equal((html.match(/src="assets\/js\/rcn-analytics.js/g) || []).length, 1);
  assert(html.includes('assets/js/rcn-analytics.js?v=20261018claritywatch'));
  assert(html.includes('action="submit-v2.php"'));
}
const thanks = fs.readFileSync('thank-you.html', 'utf8');
assert(thanks.includes('assets/js/rcn-analytics.js?v=20261018claritywatch'));
assert(thanks.includes('AW-10929471967/wib4COjkqbQcEN-Dytso'));
assert(!thanks.includes('AW-10929471967/wiFkCM3XupwYEN-Dytso'));
console.log('PASS: RCN isolation, privacy, opt-out, Clarity queue/watch tags/error resilience/QA segregation, funnel semantics, confirmation deduplication, load timing, destination asterisks and Ads baseline.');
