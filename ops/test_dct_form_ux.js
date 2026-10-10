// Node-only regression checks. No network calls, lead submissions or credentials.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(tag='div') { this.tagName=tag.toUpperCase();this.attrs={};this.children=[];this.listeners={};this.value=''; }
  setAttribute(k,v) {this.attrs[k]=v;}
  getAttribute(k) {return this.attrs[k]??null;}
  removeAttribute(k) {delete this.attrs[k];}
  appendChild(el) {this.children.push(el);return el;}
  insertBefore(el) {this.children.unshift(el);}
  insertAdjacentElement(position,el) {this.error=el;}
  replaceChildren() {this.children=[];this.rebuilds=(this.rebuilds||0)+1;}
  remove() {this.removed=true;}
  addEventListener(type,fn) {(this.listeners[type]??=[]).push(fn);}
  dispatch(type,event={}) {for(const fn of this.listeners[type]||[]) fn({target:this,...event});}
  focus() {active=this;}
  scrollIntoView() {this.scrolled=true;}
  closest() {return card;}
}
let active;
const card=new Element();
const form=new Element('form');
const names=['first_name','last_name','email','phone','destination','travel_date','duration','guests','budget'];
const fields=names.map(name=>{
  const el=new Element(['duration','guests','budget'].includes(name)?'select':'input');
  el.id=name;el.name=name;el.willValidate=true;el.validity={valid:false,valueMissing:true};
  el.labels=[{textContent:name.replaceAll('_',' ')+' *'}];
  el.options=[{textContent:name==='budget'?'Not sure yet':'Flexible'}];return el;
});
const optional=new Element('select');optional.id='operator';optional.name='operator';optional.willValidate=true;optional.validity={valid:true};
const hidden=new Element('input');hidden.name='gclid';hidden.value='PRIVATE-CLICK';hidden.willValidate=false;
const honeypot=new Element('input');honeypot.name='website';honeypot.willValidate=true;honeypot.closest=()=>null;
form.elements=[...fields,optional,hidden,honeypot];form.elements.namedItem=name=>form.elements.find(el=>el.name===name);
const destinations=['Britain & Ireland','Continental Europe'].map(title=>{const link=new Element('a');link.textContent=title;return link;});
const timers=[];
vm.runInNewContext(fs.readFileSync('dct-site/assets/js/dct-form-ux.js','utf8'),{
  document:{querySelectorAll:selector=>selector.startsWith('form')?[form]:destinations,createElement:tag=>new Element(tag)},
  setTimeout:fn=>{timers.push(fn);return timers.length;}
});
const summary=form.children[0];
assert.equal(summary.hidden,true);
assert.equal(form.listeners.submit,undefined,'Original submit path untouched');
assert.equal(form.attrs.novalidate,undefined,'Native validation retained');
let prevented=0;
fields.forEach(field=>form.dispatch('invalid',{target:field,preventDefault:()=>prevented++}));
assert.equal(timers.length,1);timers.shift()();assert.equal(prevented,9);assert.equal(active,fields[0]);
assert.match(summary.children[0].textContent,/9 fields/);
assert.match(fields[8].error.textContent,/Not sure yet/);assert.match(fields[6].error.textContent,/Flexible/);
assert.equal(optional.error,undefined);assert.equal(hidden.error,undefined);assert.equal(honeypot.error,undefined);
const initialRebuilds=summary.rebuilds;
form.dispatch('input',{target:fields[2]});assert.equal(summary.rebuilds,initialRebuilds,'Unchanged errors are not re-announced per keystroke');
fields[2].validity={valid:false,typeMismatch:true};form.dispatch('input',{target:fields[2]});assert.match(fields[2].error.textContent,/valid email/);
fields[0].validity={valid:true};form.dispatch('input',{target:fields[0]});assert.equal(fields[0].getAttribute('aria-invalid'),null);
assert.match(summary.children[0].textContent,/8 fields/);
// Summary links use the corresponding field's focus, not a separate submit path.
summary.children[1].children.at(-1).children[0].dispatch('click',{preventDefault:()=>{}});assert.equal(active,fields[8]);
const destination=fields[4],click={button:0,preventDefault:()=>{}};destination.validity={valid:true};
destinations[0].dispatch('click',click);assert.equal(destination.value,'Britain & Ireland');assert.equal(active,card,'Focus stays outside the form, preserving form-start semantics');
destinations[1].dispatch('click',click);assert.equal(destination.value,'Continental Europe');
destination.value='My own tour';destinations[0].dispatch('click',click);assert.equal(destination.value,'My own tour');
destination.value='';destinations[1].dispatch('click',{...click,metaKey:true});assert.equal(destination.value,'');
assert.equal(hidden.value,'PRIVATE-CLICK');
fields.forEach(field=>{field.validity={valid:true};form.dispatch('change',{target:field});});assert.equal(summary.hidden,true);
fields[0].setAttribute('aria-describedby','existing-help');fields[0].validity={valid:false,valueMissing:true};
form.dispatch('invalid',{target:fields[0],preventDefault:()=>{}});timers.shift()();assert.match(fields[0].getAttribute('aria-describedby'),/^existing-help dct-field-error/);
fields[0].validity={valid:true};form.dispatch('change',{target:fields[0]});assert.equal(fields[0].getAttribute('aria-describedby'),'existing-help');
for(const name of ['index.html','trafalgar-tours.html','globus-journeys.html','cosmos-tours.html','insight-vacations.html']) {
  const html=fs.readFileSync('dct-site/'+name,'utf8');
  assert.equal((html.match(/src="\/assets\/js\/dct-form-ux.js/g)||[]).length,1,name);
  assert(!/<form[^>]*novalidate/.test(html),name);
  assert.match(html,/action="\/submit.php" method="post" data-lead-form/);
  assert.match(html,/name="last_name"[^>]*required/);assert.match(html,/name="travel_date"[^>]*required/);
  assert(!/rcn-form-ux|GTM-5B2VFP82|AW-10929471967/.test(html));
}
const builder=fs.readFileSync('dct-site/tools/build_operator_pages.py','utf8');
assert.match(builder,/dct-form-ux.js\?v=20261010a/);assert.match(builder,/dct-analytics.js\?v=20261008validation/);
console.log('PASS: nine required-field errors, first-error/keyboard focus, correction and format errors, deduplicated announcements, described-by preservation, optional/hidden/honeypot exclusion, destination prefill/manual text, attribution preserved, five-page and builder wiring.');
