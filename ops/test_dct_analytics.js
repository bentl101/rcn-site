// No network requests or lead submissions. Run: node ops/test_dct_analytics.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('dct-site/assets/js/dct-analytics.js', 'utf8');
function scenario(host = 'book.discountcoachtours.ca', settings = {}) {
  const events = [], listeners = {}, docListeners = {}, scripts = [], clarityCalls = [], winListeners = {};
  let options;
  const ph = {init: (token, config) => {options = config; config.loaded(ph);},
    capture: (event, properties) => events.push(options.before_send({event, properties}))};
  const form = {addEventListener: (name, callback, capture) => {listeners[name] = {callback, capture};}};
  const location = {hostname:host,pathname:'/globus-journeys.html',origin:'https://' + host,
    search:settings.search === undefined ? '?dct_analytics_test=1' : settings.search,href:'https://' + host + '/globus-journeys.html?dct_analytics_test=1'};
  if (settings.path) location.pathname = settings.path;
  const document = {title:'Globus',referrer:'',createElement:()=>({}),head:{appendChild:el=>scripts.push(el)},
    addEventListener:(name,cb)=>{docListeners[name]=cb;},querySelectorAll:()=>[form]};
  const window = {posthog:ph,addEventListener:(name,callback)=>{winListeners[name]=callback;}};
  if (!settings.absent) window.clarity = function(...args) {
    if (settings.broken) throw new Error('Unavailable');
    clarityCalls.push(args);
  };
  vm.runInNewContext(source, {location,document,URL,URLSearchParams,window});
  if (docListeners.DOMContentLoaded) docListeners.DOMContentLoaded();
  return {events,listeners,scripts,clarityCalls,winListeners,window};
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
  assert(html.includes('dct-analytics.js?v=20261018claritywatch'),file);
}
const tag = (sample,key,value) => sample.clarityCalls.some(c=>c[0]==='set' && c[1]===key && c[2]===value);
assert.equal(isolated.clarityCalls.length,0);
assert(tag(s,'watch','qa'));
assert(!tag(s,'watch','yes'));
assert(!JSON.stringify(s.clarityCalls).includes('private'));
assert(!JSON.stringify(s.clarityCalls).includes('field_name'));
const first = scenario(undefined,{search:''});
for (const name of ['first_name','email','phone']) first.listeners.invalid.callback({target:{name,validity:{valueMissing:true}}});
assert(!tag(first,'watch_reason','repeated_validation'));
first.listeners.invalid.callback({target:{name:'email',validity:{typeMismatch:true}}});
assert(tag(first,'watch_reason','repeated_validation'));
assert(tag(first,'watch','yes'));
first.listeners.focusin.callback(); first.listeners.focusin.callback();
assert.equal(first.clarityCalls.filter(c=>c[0]==='event' && c[1]==='dct_form_started').length,1);
assert(tag(first,'enquiry_started','yes'));
const err = scenario(undefined,{search:'?form_error=server'});
err.winListeners.error({message:'private@example.org https://example.org/?secret=private'});
err.winListeners.unhandledrejection({reason:'private rejection'});
assert(tag(err,'watch_reason','form_handler_error'));
assert(tag(err,'watch_reason','javascript_error'));
assert(tag(err,'watch_reason','unhandled_rejection'));
err.scripts[0].onload();
const exceptionCount=err.events.filter(e=>e.event==='$exception').length;
err.winListeners.error({message:'after init'}); err.winListeners.unhandledrejection({reason:'after init'});
assert.equal(err.events.filter(e=>e.event==='$exception').length,exceptionCount);
assert.equal(err.clarityCalls.filter(c=>c[1]==='watch_reason' && c[2]==='javascript_error').length,1);
const after = scenario(); after.scripts[0].onload(); after.winListeners.error({message:'after init'});
assert(tag(after,'watch_reason','javascript_error'));
assert(!JSON.stringify(err.clarityCalls).includes('private'));
const thanks = scenario(undefined,{path:'/thank-you.html',search:''});
assert(tag(thanks,'enquiry_thank_you_viewed','yes'));
assert(!tag(thanks,'enquiry_received','yes'));
const absent = scenario(undefined,{absent:true,search:'?form_error=server&dct_analytics_test=1'});
assert(absent.window.clarity.q.some(c=>c[1]==='watch' && c[2]==='qa'));
assert.equal(absent.scripts.length,1,'No second Clarity SDK');
const broken = scenario(undefined,{broken:true});
broken.scripts[0].onload(); broken.listeners.focusin.callback(); broken.listeners.submit.callback();
assert(broken.events.some(e=>e.event==='dct_form_submit_attempted'));
console.log('PASS: native validation capture, field/reason deduplication, missing/format/other errors, SDK queue, no field values, test flags, site isolation and submit semantics.');
console.log('PASS: Clarity late/broken SDK, watch tags, repeated-field validation, QA isolation, exception handoff and no false confirmed leads.');
