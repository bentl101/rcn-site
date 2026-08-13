(() => {
  'use strict';

  const root = document.documentElement;
  const themeButton = document.querySelector('[data-theme-toggle]');
  const menuButton = document.querySelector('[data-menu-toggle]');
  const navLinks = document.querySelector('[data-nav-links]');
  const forms = document.querySelectorAll('[data-lead-form]');
  const storageKey = 'dct_theme';
  const attributionKey = 'dct_attribution';

  const icons = {
    light: '<path d="M12 3v2m0 14v2M3 12h2m14 0h2M5.6 5.6 7 7m10 10 1.4 1.4M18.4 5.6 17 7M7 17l-1.4 1.4"/><circle cx="12" cy="12" r="4"/>',
    dark: '<path d="M20 15.3A8.5 8.5 0 0 1 8.7 4a8.5 8.5 0 1 0 11.3 11.3Z"/>'
  };

  function setTheme(theme) {
    root.dataset.theme = theme;
    if (themeButton) {
      const next = theme === 'dark' ? 'light' : 'dark';
      themeButton.setAttribute('aria-label', `Use ${next} theme`);
      themeButton.querySelector('svg').innerHTML = icons[next];
    }
  }

  const savedTheme = localStorage.getItem(storageKey);
  const preferredTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  setTheme(savedTheme || preferredTheme);

  themeButton?.addEventListener('click', () => {
    const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem(storageKey, next);
    setTheme(next);
  });

  function closeMenu() {
    navLinks?.classList.remove('open');
    document.body.classList.remove('nav-open');
    menuButton?.setAttribute('aria-expanded', 'false');
  }

  menuButton?.addEventListener('click', () => {
    const open = !navLinks?.classList.contains('open');
    navLinks?.classList.toggle('open', open);
    document.body.classList.toggle('nav-open', open);
    menuButton.setAttribute('aria-expanded', String(open));
  });

  navLinks?.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeMenu));
  window.addEventListener('resize', () => {
    if (window.innerWidth > 1088) closeMenu();
  });

  function getAttribution() {
    const params = new URLSearchParams(window.location.search);
    const clickTypes = ['gclid', 'gbraid', 'wbraid', 'fbclid', 'msclkid', 'ttclid'];
    let saved = {};
    try { saved = JSON.parse(sessionStorage.getItem(attributionKey) || '{}'); } catch (_) { saved = {}; }

    const current = {
      utm_source: params.get('utm_source') || saved.utm_source || '',
      utm_medium: params.get('utm_medium') || saved.utm_medium || '',
      utm_campaign: params.get('utm_campaign') || saved.utm_campaign || '',
      utm_term: params.get('utm_term') || saved.utm_term || '',
      utm_content: params.get('utm_content') || saved.utm_content || '',
      landing_page: saved.landing_page || window.location.href,
      referrer: saved.referrer || document.referrer,
      click_id: saved.click_id || '',
      click_id_type: saved.click_id_type || ''
    };

    for (const type of clickTypes) {
      if (params.get(type)) {
        current.click_id = params.get(type);
        current.click_id_type = type;
        break;
      }
    }

    sessionStorage.setItem(attributionKey, JSON.stringify(current));
    return current;
  }

  function createOrderId() {
    const now = new Date();
    const date = now.toISOString().slice(0, 10).replaceAll('-', '');
    const time = now.toISOString().slice(11, 19).replaceAll(':', '');
    const bytes = new Uint8Array(4);
    crypto.getRandomValues(bytes);
    const suffix = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
    return `DCT-${date}-${time}-${suffix}`;
  }

  const attribution = getAttribution();
  const pageStart = Date.now();

  forms.forEach((form) => {
    const operatorParam = new URLSearchParams(window.location.search).get('operator');
    const operatorField = form.querySelector('[name="operator"]');
    if (operatorParam && operatorField) operatorField.value = operatorParam;

    let started = false;
    form.addEventListener('focusin', () => {
      if (started) return;
      started = true;
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({ event: 'form_start', form_name: 'dct_enquiry' });
    });

    form.addEventListener('submit', () => {
      const orderId = createOrderId();
      form.querySelector('[name="lead_order_id"]').value = orderId;
      form.querySelector('[name="time_on_page"]').value = Math.round((Date.now() - pageStart) / 1000);
      Object.entries(attribution).forEach(([name, value]) => {
        const field = form.querySelector(`[name="${name}"]`);
        if (field) field.value = value;
      });
      sessionStorage.setItem('dct_lead_order_id', orderId);
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({ event: 'form_submission', form_name: 'dct_enquiry', lead_order_id: orderId });
      const button = form.querySelector('button[type="submit"]');
      if (button) {
        button.disabled = true;
        button.textContent = 'Sending your enquiry…';
      }
    });
  });

  document.querySelectorAll('[data-current-year]').forEach((node) => {
    node.textContent = String(new Date().getFullYear());
  });

  const orderDisplay = document.querySelector('[data-order-id]');
  if (orderDisplay) {
    const orderId = sessionStorage.getItem('dct_lead_order_id');
    if (orderId) orderDisplay.textContent = orderId;
    else orderDisplay.closest('[data-order-wrap]')?.remove();
  }
})();
