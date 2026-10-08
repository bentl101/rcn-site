// No network requests or lead submissions. Run: node ops/test_dct_analytics.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('dct-site/assets/js/dct-analytics.js', 'utf8');
function scenario(host = 'book.discountcoachtours.ca') {
  const events = [], listeners = {}, docListeners = {}, scripts = [];
  let options;
  const ph = {init: (token, config) => {options = config; config.loaded(ph);},
    capture: (event, properties) => events.push(options.before_send({event, properties}))};
  const form = {addEventListener: (name, callback, capture) => {listeners[name] = {callback, capture};}};
  const location = {hostname:host,pathname:'/globus-journeys.html',origin:'https://' + host,
    search:'?dct_analytics_test=1',href:'https://' + host + '/globus-journeys.html?dct_analytics_test=1'};
  const document = {title:'Globus',referrer:'',createElement:()=>({}),head:{appendChild:el=>scripts.push(el)},
    addEventListener:(name,cb)=>{docListeners[name]=cb;},querySelectorAll:()=>[form]};
  vm.runInNewContext(source, {location,document,URL,URLSearchParams,
    window:{posthog:ph,addEventListener:()=>{}}});
  if (docListeners.DOMContentLoaded) docListeners.DOMContentLoaded();
  return {events,listeners,scripts};
}
const isolated = scenario('book.rivercruisenetwork.com');
assert.equal(isolated.scripts.length, 0, 'DCT tracking stays off RCN');
const s = scenario();
assert.equal(s.listeners.invalid.capture, true, 'Native invalid events need capture phase');
function invalid(name, validity) {
  s.listeners.invalid.callback({target:{name,validity,value:'private@example.com',validationMessage:'Private text'}});
}
invalid('email',{valueMissing:true});
invalid('email',{valueMissing:true});
invalid('email',{typeMismatch:true});
invalid('phone',{patternMismatch:true});
invalid('destination',{valueMissing:true});
invalid('gclid',{valueMissing:true});
invalid('website',{valueMissing:true});
assert.equal(s.events.length,0,'Validation queues safely while the SDK loads');
s.scripts[0].onload();
const failures=s.events.filter(e=>e.event==='dct_form_validation_error');
assert.deepEqual(failures.map(e=>[e.properties.field_name,e.properties.validation_reason]),
  [['email','required'],['email','format'],['phone','invalid'],['destination','required']]);
assert(failures.every(e=>e.properties.is_test && e.properties.site==='dct'));
assert(failures.every(e=>e.properties.page_path==='/globus-journeys.html'));
assert(!JSON.stringify(s.events).includes('private@example.com'));
assert(!JSON.stringify(s.events).includes('Private text'));
assert(!s.events.some(e=>e.event==='dct_form_submit_attempted'),'Invalid attempts are not valid submits');
s.listeners.submit.callback();
assert.equal(s.events.filter(e=>e.event==='dct_form_submit_attempted').length,1);
for (const file of ['index.html','trafalgar-tours.html','globus-journeys.html','cosmos-tours.html','insight-vacations.html']) {
  const html=fs.readFileSync('dct-site/'+file,'utf8');
  assert(html.includes('action="/submit.php"'),file);
  assert(html.includes('dct-analytics.js?v=20261008validation'),file);
}
console.log('PASS: native validation capture, field/reason deduplication, missing/format/other errors, SDK queue, no field values, test flags, site isolation and submit semantics.');
