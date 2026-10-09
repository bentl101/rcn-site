/* RCN enquiry assistance. Keep native validation and the existing submission path. */
(function () {
  'use strict';
  document.querySelectorAll('form[action="submit-v2.php"]').forEach(function (form, formIndex) {
    var fields = Array.from(form.elements).filter(function (field) {
      return field.willValidate && field.closest('.form-group');
    });
    var errors = new Map();
    var pending = null;
    var summaryKey = '';
    var summary = document.createElement('div');
    summary.className = 'rcn-form-errors';
    summary.hidden = true;
    summary.setAttribute('role', 'alert');
    summary.setAttribute('aria-atomic', 'true');
    form.insertBefore(summary, form.firstChild);

    function label(field) {
      return field.labels && field.labels[0]
        ? field.labels[0].textContent.replace(/\s*\*\s*$/, '').trim() : 'This field';
    }
    function message(field) {
      if (field.validity.valueMissing) {
        if (field.name === 'destination') return 'Please enter the river or itinerary you are interested in.';
        if (field.name === 'budget') return 'Please choose a budget, or select Flexible if you are unsure.';
        if (field.name === 'duration') {
          var flexible = Array.from(field.options).find(function (option) { return /^(Not sure yet|Flexible)$/.test(option.textContent.trim()); });
          return 'Please choose a trip duration' + (flexible ? ', or select ' + flexible.textContent.trim() : '') + '.';
        }
        if (field.name === 'travel_date') return 'Please choose your preferred travel month and year.';
        return 'Please ' + (field.tagName === 'SELECT' ? 'choose ' : 'enter ') + label(field).toLowerCase() + '.';
      }
      if (field.name === 'email' && field.validity.typeMismatch) return 'Please enter a valid email address, such as name@example.com.';
      return field.validationMessage || 'Please check this field.';
    }
    function syncField(field) {
      var error = errors.get(field);
      if (!field.validity.valid) {
        if (!error) {
          error = document.createElement('p');
          error.id = 'rcn-field-error-' + formIndex + '-' + fields.indexOf(field);
          error.className = 'rcn-field-error';
          field.insertAdjacentElement('afterend', error);
          var describedBy = (field.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
          describedBy.push(error.id);
          field.setAttribute('aria-describedby', describedBy.join(' '));
          errors.set(field, error);
        }
        error.textContent = message(field);
        field.setAttribute('aria-invalid', 'true');
      } else if (error) {
        var remaining = (field.getAttribute('aria-describedby') || '').split(/\s+/).filter(function (id) { return id && id !== error.id; });
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
      var invalid = fields.filter(function (field) { return errors.has(field); });
      var key = invalid.map(function (field) { return field.id; }).join('|');
      if (key === summaryKey) return; // Do not repeat an alert on every keystroke.
      summaryKey = key;
      summary.replaceChildren();
      summary.hidden = invalid.length === 0;
      if (!invalid.length) return;
      var title = document.createElement('p');
      title.textContent = 'Please check ' + invalid.length + (invalid.length === 1 ? ' field' : ' fields') + ' before sending your enquiry:';
      summary.appendChild(title);
      var list = document.createElement('ul');
      invalid.forEach(function (field) {
        var item = document.createElement('li');
        var link = document.createElement('a');
        link.href = '#' + field.id;
        link.textContent = label(field);
        link.addEventListener('click', function (event) { event.preventDefault(); focusField(field); });
        item.appendChild(link);
        list.appendChild(item);
      });
      summary.appendChild(list);
    }
    form.addEventListener('invalid', function (event) {
      if (fields.indexOf(event.target) === -1) return;
      // Do not turn off validation, stop propagation or dispatch a submit event.
      // Existing missing-field emails and analytics still see the native events.
      syncField(event.target);
      event.preventDefault(); // Replace the transient browser bubble with persistent errors.
      if (pending !== null) return;
      pending = setTimeout(function () {
        pending = null;
        fields.filter(function (field) { return errors.has(field); }).forEach(syncField);
        updateSummary();
        var first = fields.find(function (field) { return errors.has(field); });
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

    var itinerary = form.elements.namedItem('destination');
    var lastSelectedItinerary = null;
    document.querySelectorAll('a.offer-card[href="#enquire"]').forEach(function (card) {
      card.addEventListener('click', function (event) {
        if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        var offerTitle = card.querySelector('h3');
        if (!itinerary || !offerTitle) return;
        // Update our own previous selection, never replace a visitor's typed enquiry.
        if (!itinerary.value.trim() || itinerary.value === lastSelectedItinerary) {
          itinerary.value = offerTitle.textContent.trim();
          lastSelectedItinerary = itinerary.value;
          if (errors.has(itinerary)) { syncField(itinerary); updateSummary(); }
        }
        var heading = form.closest('.form-box').querySelector('h3');
        if (!heading) return;
        event.preventDefault();
        heading.setAttribute('tabindex', '-1');
        heading.focus({ preventScroll: true });
        heading.scrollIntoView({ block: 'start', behavior: 'instant' });
        // Focus the heading, not an input: no mobile keyboard or artificial form-start.
      });
    });
  });
}());
