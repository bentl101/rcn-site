(() => {
  'use strict';

  const root = document.documentElement;
  const themeButton = document.querySelector('[data-theme-toggle]');
  const menuButton = document.querySelector('[data-menu-toggle]');
  const navLinks = document.querySelector('[data-nav-links]');
  const forms = document.querySelectorAll('[data-lead-form]');
  const storageKey = 'dct_theme';
  const attributionKey = 'dct_attribution';
  const attributionCookie = 'dct_attr';
  const attributionMaxAge = 60 * 60 * 24 * 90;
  const attributionFields = [
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'utm_id',
    'matchtype', 'gad_device', 'network', 'adgroupid', 'targetid', 'loc_physical',
    'loc_interest', 'gclid', 'gbraid', 'wbraid', 'click_id', 'click_id_type',
    'landing_page', 'referrer'
  ];

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

  function readAttributionCookie() {
    const match = document.cookie.match(/(?:^|;\s*)dct_attr=([^;]*)/);
    if (!match) return {};
    try { return JSON.parse(decodeURIComponent(match[1])) || {}; } catch (_) { return {}; }
  }

  function readAttributionSession() {
    try { return JSON.parse(sessionStorage.getItem(attributionKey) || '{}') || {}; }
    catch (_) { return {}; }
  }

  function writeAttribution(attribution) {
    const value = JSON.stringify(attribution);
    try { sessionStorage.setItem(attributionKey, value); } catch (_) {}
    try {
      const secure = window.location.protocol === 'https:' ? ';Secure' : '';
      document.cookie = `${attributionCookie}=${encodeURIComponent(value)};path=/;max-age=${attributionMaxAge};SameSite=Lax${secure}`;
    } catch (_) {}
  }

  function mergeFirstTouch(target, source) {
    attributionFields.forEach((key) => {
      if (!target[key] && source[key]) target[key] = source[key];
    });
    return target;
  }

  function hasCampaignAttribution(values) {
    return [
      'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'utm_id',
      'matchtype', 'gad_device', 'network', 'adgroupid', 'targetid', 'loc_physical',
      'loc_interest', 'gclid', 'gbraid', 'wbraid', 'click_id'
    ].some((key) => Boolean(values[key]));
  }

  function applyLatestCampaign(target, latest, landingUrl, referrer) {
    if (!hasCampaignAttribution(latest)) return target;

    // A fresh campaign visit must supersede an older stored paid-click bundle.
    // Otherwise a 90-day-old click ID could be uploaded for a newer ad visit.
    const campaignFields = [
      'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'utm_id',
      'matchtype', 'gad_device', 'network', 'adgroupid', 'targetid', 'loc_physical',
      'loc_interest', 'gclid', 'gbraid', 'wbraid', 'click_id', 'click_id_type'
    ];
    campaignFields.forEach((key) => { delete target[key]; });
    Object.assign(target, latest);
    target.landing_page = landingUrl;
    target.referrer = referrer || 'direct';
    return target;
  }

  function parseAttribution(url) {
    let params;
    try { params = new URL(url, window.location.origin).searchParams; }
    catch (_) { return {}; }

    const parsed = {};
    const directFields = [
      'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'utm_id',
      'matchtype', 'network', 'adgroupid', 'targetid', 'loc_physical', 'loc_interest'
    ];
    directFields.forEach((key) => {
      const value = params.get(key);
      if (value) parsed[key] = value;
    });
    const adsDevice = params.get('device');
    if (adsDevice) parsed.gad_device = adsDevice;

    // Keep Google click identifiers individually. A URL can legitimately carry
    // both gclid and gbraid, while click_id remains a backwards-compatible key.
    ['gclid', 'gbraid', 'wbraid'].forEach((key) => {
      const value = params.get(key);
      if (value) parsed[key] = value;
    });
    for (const type of ['gclid', 'gbraid', 'wbraid', 'fbclid', 'msclkid', 'ttclid']) {
      const value = params.get(type);
      if (value) {
        parsed.click_id = value;
        parsed.click_id_type = type;
        break;
      }
    }
    return parsed;
  }

  function getAttribution() {
    // Restore durable visit context, then let a fresh campaign visit replace the
    // stored click bundle so an older ad ID can never override a newer one.
    const current = mergeFirstTouch({}, readAttributionCookie());
    mergeFirstTouch(current, readAttributionSession());
    const fromCurrentUrl = parseAttribution(window.location.href);
    applyLatestCampaign(current, fromCurrentUrl, window.location.href, document.referrer);

    if (!current.landing_page) current.landing_page = window.location.href;
    if (!current.referrer) current.referrer = document.referrer || 'direct';

    if (!hasCampaignAttribution(fromCurrentUrl) && !current.click_id && document.referrer) {
      try {
        const referrerUrl = new URL(document.referrer);
        if (referrerUrl.origin === window.location.origin) {
          const fromReferrer = parseAttribution(referrerUrl.href);
          applyLatestCampaign(current, fromReferrer, referrerUrl.href, 'direct');
        }
      } catch (_) {}
    }

    // Recover the generic pair if an older store contains only an individual ID.
    if (!current.click_id) {
      for (const type of ['gclid', 'gbraid', 'wbraid']) {
        if (current[type]) {
          current.click_id = current[type];
          current.click_id_type = type;
          break;
        }
      }
    }

    writeAttribution(current);
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
  const deviceType = window.matchMedia('(max-width: 767px)').matches
    ? 'mobile'
    : window.matchMedia('(max-width: 1088px)').matches ? 'tablet' : 'desktop';

  forms.forEach((form) => {
    const operatorParam = new URLSearchParams(window.location.search).get('operator');
    const operatorField = form.querySelector('[name="operator"]');
    if (operatorParam && operatorField) operatorField.value = operatorParam;

    let started = false;
    form.addEventListener('focusin', () => {
      if (started) return;
      started = true;
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({
        event: 'form_start',
        form_name: 'dct_enquiry',
        form_operator: operatorField?.value || '',
        form_page: document.title
      });
    });

    form.addEventListener('submit', () => {
      const orderId = createOrderId();
      form.querySelector('[name="lead_order_id"]').value = orderId;
      form.querySelector('[name="time_on_page"]').value = Math.round((Date.now() - pageStart) / 1000);
      const deviceField = form.querySelector('[name="device_type"]');
      if (deviceField) deviceField.value = deviceType;
      const languageField = form.querySelector('[name="browser_language"]');
      if (languageField) languageField.value = navigator.language || '';
      const pageLoadField = form.querySelector('[name="page_load_time"]');
      if (pageLoadField) pageLoadField.value = String(pageStart);
      Object.entries(attribution).forEach(([name, value]) => {
        const field = form.querySelector(`[name="${name}"]`);
        if (field) field.value = value;
      });
      sessionStorage.setItem('dct_lead_order_id', orderId);
      sessionStorage.setItem('dct_lead_operator', operatorField?.value || 'Help me compare');
      sessionStorage.setItem('dct_lead_source', form.querySelector('[name="source_page"]')?.value || '');
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({
        event: 'form_submission',
        form_name: 'dct_enquiry',
        form_operator: operatorField?.value || '',
        form_source: form.querySelector('[name="source_page"]')?.value || '',
        lead_order_id: orderId
      });
      const button = form.querySelector('button[type="submit"]');
      if (button) {
        button.disabled = true;
        button.textContent = 'Sending your enquiry…';
      }
    });
  });

  document.addEventListener('click', (event) => {
    const phoneLink = event.target.closest('a[href^="tel:"]');
    if (!phoneLink) return;
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'LP_PhoneClick',
      phoneNumber: phoneLink.getAttribute('href').replace('tel:', ''),
      pageName: document.title
    });
  });

  document.querySelectorAll('[data-current-year]').forEach((node) => {
    node.textContent = String(new Date().getFullYear());
  });

  const orderDisplay = document.querySelector('[data-order-id]');
  if (orderDisplay) {
    const orderId = sessionStorage.getItem('dct_lead_order_id');
    if (orderId) {
      orderDisplay.textContent = orderId;
      const completeKey = `dct_complete_${orderId}`;
      if (sessionStorage.getItem(completeKey) !== '1') {
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({
          event: 'lead_form_complete',
          form_name: 'dct_enquiry',
          form_operator: sessionStorage.getItem('dct_lead_operator') || '',
          form_source: sessionStorage.getItem('dct_lead_source') || '',
          lead_order_id: orderId
        });
        sessionStorage.setItem(completeKey, '1');
      }
    }
    else orderDisplay.closest('[data-order-wrap]')?.remove();
  }
})();
