/* DCT enquiry assistance: native validation and the existing submit path stay intact. */
(() => {
  'use strict';
  document.querySelectorAll('form[data-lead-form][action="/submit.php"]').forEach((form, formIndex) => {
    const fields = Array.from(form.elements).filter(field => field.willValidate && field.closest('.field'));
    const errors = new Map();
    let pending = null;
    let summaryKey = '';
    const summary = document.createElement('div');
    summary.className = 'dct-form-errors';
    summary.hidden = true;
    summary.setAttribute('role', 'alert');
    summary.setAttribute('aria-atomic', 'true');
    form.insertBefore(summary, form.firstChild);

    function label(field) {
      return field.labels?.[0]?.textContent.replace(/\s*\*\s*$/, '').trim() || 'This field';
    }
    function message(field) {
      if (field.validity.valueMissing) {
        if (field.name === 'destination') return 'Please enter the country, region or tour you are interested in.';
        if (field.name === 'travel_date') return 'Please choose your preferred travel month and year.';
        if (field.name === 'budget' || field.name === 'duration') {
          const choice = Array.from(field.options).find(option => /^(Not sure yet|Flexible)$/.test(option.textContent.trim()));
          return 'Please choose ' + (field.name === 'budget' ? 'a budget' : 'a trip length') + (choice ? ', or select ' + choice.textContent.trim() : '') + '.';
        }
        if (field.name === 'guests') return 'Please choose the number of travellers.';
        return 'Please ' + (field.tagName === 'SELECT' ? 'choose ' : 'enter your ') + label(field).toLowerCase() + '.';
      }
      if (field.name === 'email' && field.validity.typeMismatch) return 'Please enter a valid email address, such as name@example.com.';
      return field.validationMessage || 'Please check this field.';
    }
    function syncField(field) {
      let error = errors.get(field);
      if (!field.validity.valid) {
        if (!error) {
          error = document.createElement('p');
          error.id = 'dct-field-error-' + formIndex + '-' + fields.indexOf(field);
          error.className = 'dct-field-error';
          field.insertAdjacentElement('afterend', error);
          const describedBy = (field.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
          describedBy.push(error.id);
          field.setAttribute('aria-describedby', describedBy.join(' '));
          errors.set(field, error);
        }
        error.textContent = message(field);
        field.setAttribute('aria-invalid', 'true');
      } else if (error) {
        const remaining = (field.getAttribute('aria-describedby') || '').split(/\s+/).filter(id => id && id !== error.id);
        if (remaining.length) field.setAttribute('aria-describedby', remaining.join(' '));
        else field.removeAttribute('aria-describedby');
        field.removeAttribute('aria-invalid');
        error.remove();
        errors.delete(field);
      }
    }
    function focusField(field) {
      field.focus({ preventScroll: true });
      field.scrollIntoView({ block: 'center', behavior: 'instant' });
    }
    function updateSummary() {
      const invalid = fields.filter(field => errors.has(field));
      const key = invalid.map(field => field.id).join('|');
      if (key === summaryKey) return; // Avoid repeating an alert on every keystroke.
      summaryKey = key;
      summary.replaceChildren();
      summary.hidden = invalid.length === 0;
      if (!invalid.length) return;
      const title = document.createElement('p');
      title.textContent = 'Please check ' + invalid.length + (invalid.length === 1 ? ' field' : ' fields') + ' before sending your enquiry:';
      summary.appendChild(title);
      const list = document.createElement('ul');
      invalid.forEach(field => {
        const item = document.createElement('li');
        const link = document.createElement('a');
        link.href = '#' + field.id;
        link.textContent = label(field);
        link.addEventListener('click', event => { event.preventDefault(); focusField(field); });
        item.appendChild(link);
        list.appendChild(item);
      });
      summary.appendChild(list);
    }
    form.addEventListener('invalid', event => {
      if (!fields.includes(event.target)) return;
      syncField(event.target);
      // Suppress only the transient browser bubble, not native validation or its
      // events. DCT analytics still receives the original invalid-field events.
      event.preventDefault();
      if (pending !== null) return;
      pending = setTimeout(() => {
        pending = null;
        fields.filter(field => errors.has(field)).forEach(syncField);
        updateSummary();
        const first = fields.find(field => errors.has(field));
        if (first) focusField(first);
      }, 0);
    }, true);
    function recheck(event) {
      if (!errors.has(event.target)) return;
      syncField(event.target);
      updateSummary();
    }
    form.addEventListener('input', recheck);
    form.addEventListener('change', recheck);

    const destination = form.elements.namedItem('destination');
    const card = form.closest('.form-card');
    let lastSelection = null;
    document.querySelectorAll('#destinations a.tag[href="#enquire"]').forEach(link => {
      link.addEventListener('click', event => {
        if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        if (!destination || !card) return;
        if (!destination.value.trim() || destination.value === lastSelection) {
          destination.value = link.textContent.trim();
          lastSelection = destination.value;
          if (errors.has(destination)) { syncField(destination); updateSummary(); }
        }
        event.preventDefault();
        // Focus outside the form: no mobile keyboard or artificial form-start.
        card.setAttribute('tabindex', '-1');
        card.setAttribute('role', 'group');
        card.setAttribute('aria-label', 'Tour enquiry form');
        card.focus({ preventScroll: true });
        card.scrollIntoView({ block: 'start', behavior: 'instant' });
      });
    });
  });
})();
