/**
 * River Cruise Network — Real-Time Phone Validation
 * Calls /verify-phone.php (server-side proxy) on blur.
 * Exposes validity via phoneInput.dataset.phoneInvalid ('true' | absent).
 * The main form submit handler checks this before allowing submission.
 */
(function () {
  var phoneInput = document.getElementById('phone');
  if (!phoneInput) return;

  var group = phoneInput.closest('.form-group');
  var msgEl = null;
  var lastChecked = '';

  function clearState() {
    if (msgEl) { msgEl.remove(); msgEl = null; }
    if (group) { group.classList.remove('has-error', 'has-success'); }
    delete phoneInput.dataset.phoneInvalid;
  }

  function showError(text) {
    clearState();
    msgEl = document.createElement('div');
    msgEl.className = 'phone-error';
    msgEl.textContent = text;
    phoneInput.parentNode.appendChild(msgEl);
    if (group) group.classList.add('has-error');
    phoneInput.dataset.phoneInvalid = 'true';
  }

  function showValid() {
    clearState();
    msgEl = document.createElement('div');
    msgEl.className = 'phone-valid';
    msgEl.textContent = 'Phone number verified';
    phoneInput.parentNode.appendChild(msgEl);
    if (group) group.classList.add('has-success');
  }

  phoneInput.addEventListener('blur', function () {
    var val = phoneInput.value.replace(/\s+/g, '');

    if (!val) {
      clearState();
      lastChecked = '';
      return;
    }

    if (val.length < 6) {
      lastChecked = '';
      showError('Please enter a valid phone number');
      return;
    }

    if (val === lastChecked) return;
    lastChecked = val;

    fetch('/verify-phone.php?phone=' + encodeURIComponent(val))
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.phone_valid) {
          showValid();
        } else {
          showError('Phone number not valid');
        }
      })
      .catch(function () {
        clearState();
        lastChecked = '';
      });
  });
})();
