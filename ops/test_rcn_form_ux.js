// Run with node ops/test_rcn_form_ux.js. No browser/network or lead creation.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(tag='div') { this.tagName=tag.toUpperCase(); this.attrs={}; this.children=[]; this.listeners={}; this.value=''; }
  setAttribute(k,v) {this.attrs[k]=v;}
  getAttribute(k) {return this.attrs[k]??null;}
  removeAttribute(k) {delete this.attrs[k];}
  appendChild(el) {this.children.push(el);return el;}
  insertBefore(el) {this.children.unshift(el);}
  insertAdjacentElement(position,el) {this.error=el;}
  replaceChildren() {this.children=[];}
  remove() {this.removed=true;}
  addEventListener(type,fn) {(this.listeners[type]??=[]).push(fn);}
  dispatch(type,event={}) {for(const fn of this.listeners[type]||[]) fn({target:this,...event});}
  focus() {active=this;}
  scrollIntoView() {this.scrolled=true;}
  closest() {return formBox;}
}
let active;
const heading = new Element('h3');
const formBox={querySelector:()=>heading};
const form = new Element('form');
const fields=['first_name','email','phone','destination','travel_date','duration','guests','budget'].map((name,i)=>{
  const el=new Element(['duration','guests','budget'].includes(name)?'select':'input');
  el.id=name;el.name=name;el.willValidate=true;el.validity={valid:false,valueMissing:true};el.labels=[{textContent:name.replaceAll('_',' ')+' *'}];el.options=[{textContent:'Not sure yet'}];return el;
});
const hidden=new Element('input');hidden.name='click_id';hidden.value='PRIVATE';hidden.willValidate=false;
form.elements=[...fields,hidden];form.elements.namedItem=name=>form.elements.find(f=>f.name===name);
const cards=['Rhine & Normandy','Danube'].map(title=>{const card=new Element('a');card.querySelector=()=>({textContent:title});return card;});
const timers=[];
vm.runInNewContext(fs.readFileSync('assets/js/rcn-form-ux.js','utf8'),{
  document:{querySelectorAll:selector=>selector.startsWith('form')?[form]:cards,createElement:tag=>new Element(tag)},
  setTimeout:fn=>{timers.push(fn);return timers.length;}
});
const summary=form.children[0];
assert.equal(summary.hidden,true);
assert.equal(form.listeners.submit,undefined,'No replacement submission path');
assert.equal(form.attrs.novalidate,undefined,'Native validation stays enabled');
let cancelled=0;
fields.forEach(field=>form.dispatch('invalid',{target:field,preventDefault:()=>cancelled++}));
assert.equal(timers.length,1,'Native invalid burst coalesces');
timers.shift()();
assert.equal(cancelled,8);
assert.equal(active,fields[0]);
assert.equal(summary.hidden,false);
assert.match(summary.children[0].textContent,/8 fields/);
assert.match(fields[7].error.textContent,/Flexible/);
assert.match(fields[5].error.textContent,/Not sure yet/);
fields[5].options=[{textContent:'Flexible'}];form.dispatch('change',{target:fields[5]});
assert.match(fields[5].error.textContent,/Flexible/,'Homepage duration hint matches its actual options');
assert.equal(hidden.value,'PRIVATE');
assert.equal(hidden.error,undefined,'No errors for hidden attribution');
fields[0].validity={valid:true};form.dispatch('input',{target:fields[0]});
assert.equal(fields[0].getAttribute('aria-invalid'),null);
assert.equal(fields[0].getAttribute('aria-describedby'),null);
assert.match(summary.children[0].textContent,/7 fields/);
fields[1].validity={valid:false,typeMismatch:true};form.dispatch('change',{target:fields[1]});
assert.match(fields[1].error.textContent,/valid email/);
const itinerary=fields[3];
itinerary.validity={valid:true};
const click={button:0,preventDefault:()=>{}};
cards[0].dispatch('click',click);
assert.equal(itinerary.value,'Rhine & Normandy');
assert.equal(active,heading,'Offer focus does not create an input form-start');
cards[1].dispatch('click',click);assert.equal(itinerary.value,'Danube');
itinerary.value='My own itinerary';cards[0].dispatch('click',click);assert.equal(itinerary.value,'My own itinerary');
itinerary.value='';cards[1].dispatch('click',{...click,ctrlKey:true});assert.equal(itinerary.value,'','Modified clicks keep native link behavior');
fields.forEach(field=>{field.validity={valid:true};form.dispatch('input',{target:field});});
assert.equal(summary.hidden,true);
// Existing aria-describedby help must survive an error lifecycle.
fields[0].setAttribute('aria-describedby','existing-help');fields[0].validity={valid:false,valueMissing:true};
form.dispatch('invalid',{target:fields[0],preventDefault:()=>{}});timers.shift()();
assert.match(fields[0].getAttribute('aria-describedby'),/^existing-help rcn-field-error/);
fields[0].validity={valid:true};form.dispatch('change',{target:fields[0]});
assert.equal(fields[0].getAttribute('aria-describedby'),'existing-help');
for(const name of ['index.html','avalon-waterways.html','scenic-river-cruise.html','emerald-river-cruise.html','amawaterways-river-cruise.html','viking-river-cruise.html']) {
  const html=fs.readFileSync(name,'utf8');
  assert.equal((html.match(/src="assets\/js\/rcn-form-ux.js/g)||[]).length,1,name);
  assert(!/<form[^>]*novalidate/.test(html),name);
  assert.match(html,/action="submit-v2.php" method="POST"/);
  assert.match(html,/rcn-incomplete-forms.js/);
}
console.log('PASS: native validation preserved, error batching/focus, correction, accessible descriptions, itinerary prefill, manual edits preserved, no submit interception or attribution mutation; six pages included.');
