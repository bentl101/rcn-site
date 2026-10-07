/* Operational email for blocked quote attempts; never send these values to analytics. */
(function () {
  'use strict';
  var fields = ['first_name', 'last_name', 'email', 'phone', 'destination',
    'travel_date', 'duration', 'guests', 'budget', 'operator', 'additional_info'];

  document.querySelectorAll('form[action="submit-v2.php"]').forEach(function (form) {
    var pending = null;
    var recent = new Map();
    form.addEventListener('invalid', function (event) {
      if (!event.target.validity.valueMissing || pending !== null) return;
      // Native validation emits one event per invalid field in the same turn.
      // Take one snapshot now, then send once after that validation burst.
      var values = {};
      fields.forEach(function (name) {
        var input = form.elements.namedItem(name);
        values[name] = input ? input.value.trim().slice(0, name === 'additional_info' ? 4000 : 300) : '';
      });
      var missing = Array.from(form.elements).filter(function (input) {
        return input.willValidate && input.validity.valueMissing;
      }).map(function (input) { return input.name; });
      var signature = JSON.stringify([values, missing]);
      pending = setTimeout(function () {
        pending = null;
        var now = Date.now();
        recent.forEach(function (time, key) { if (now - time >= 600000) recent.delete(key); });
        if (recent.has(signature)) return;
        recent.set(signature, now);
        var payload = JSON.stringify({
          page: window.location.pathname,
          fields: values,
          is_test: new URLSearchParams(window.location.search).get('rcn_analytics_test') === '1'
        });
        function send(retry) {
          // No changes to validation, submit handlers, lead cookies or redirects.
          fetch('/incomplete-form.php', {
            method: 'POST', credentials: 'same-origin', keepalive: true,
            headers: { 'Content-Type': 'application/json' }, body: payload
          }).then(function (response) {
            if (response.status >= 500) throw new Error('Notification unavailable');
          }).catch(function () {
            if (retry) setTimeout(function () { send(false); }, 3000);
            else recent.delete(signature);
          });
        }
        send(true);
      }, 0);
    }, true);
  });
}());
