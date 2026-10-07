/* RCN funnel, replay and performance instrumentation. No form values are sent. */
(function () {
  'use strict';
  if (location.hostname !== 'book.rivercruisenetwork.com') return;
  var test = new URLSearchParams(location.search).get('rcn_analytics_test') === '1';
  var disabled = false;
  try { disabled = localStorage.getItem('rcn_analytics_opt_out') === '1'; } catch (_) {}
  if (disabled) return;
  var queue = [], client = null;
  var page = location.pathname === '/' ? '/index.html' : location.pathname;
  function cleanUrl(value) {
    try { var u = new URL(value, location.origin); return u.origin + u.pathname; }
    catch (_) { return ''; }
  }
  function capture(event, properties) {
    var props = Object.assign({ site: 'rcn', page_path: page, is_test: test }, properties || {});
    if (client) client.capture(event, props);
    else queue.push([event, props]);
  }
  function scrub(value) {
    if (typeof value === 'string') return value
      .replace(/https?:\/\/[^\s"<>]+/g, function (url) { return cleanUrl(url); })
      .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[email]')
      .replace(/\+?\d[\d ()-]{7,}\d/g, '[number]');
    if (Array.isArray(value)) return value.map(scrub);
    if (value && typeof value === 'object') {
      var out = {};
      Object.keys(value).forEach(function (k) { out[k] = scrub(value[k]); });
      return out;
    }
    return value;
  }
  // Catch startup failures while the SDK is still loading. After initialization
  // PostHog's own exception handlers take over, avoiding duplicate reports.
  window.addEventListener('error', function (e) {
    if (!client && e.message) capture('$exception', { $exception_list: [{
      type: 'Error', value: scrub(e.message),
      mechanism: { type: 'onerror', handled: false }
    }] });
  });
  window.addEventListener('unhandledrejection', function (e) {
    if (!client) capture('$exception', { $exception_list: [{
      type: 'UnhandledRejection', value: scrub(String(e.reason && e.reason.message || e.reason || 'Unhandled promise rejection')),
      mechanism: { type: 'onunhandledrejection', handled: false }
    }] });
  });
  var sdk = document.createElement('script');
  sdk.async = true;
  sdk.src = 'https://eu-assets.i.posthog.com/static/array.js';
  sdk.onload = function () {
    if (!window.posthog) return;
    window.posthog.init('phc_yoDmHvTJjzMERbY9uurs8kemRp3VRd5zW8CoAPxfLEP2', {
      api_host: 'https://eu.i.posthog.com', ui_host: 'https://eu.posthog.com',
      person_profiles: 'never', autocapture: false,
      capture_pageview: false, capture_pageleave: false,
      capture_dead_clicks: false, capture_exceptions: true,
      capture_performance: { web_vitals: true, network_timing: false },
      enable_recording_console_log: false,
      session_recording: {
        maskAllInputs: true, maskTextSelector: 'form',
        recordBody: false, recordHeaders: false, recordCrossOriginIframes: false,
        maskCapturedNetworkRequestFn: function () { return undefined; }
      },
      before_send: function (event) {
        if (!event) return event;
        var p = event.properties || {};
        ['$current_url', '$referrer', '$initial_current_url', '$initial_referrer'].forEach(function (k) {
          if (p[k]) p[k] = cleanUrl(p[k]);
        });
        // Avoid retaining query strings, click IDs or arbitrary campaign values.
        Object.keys(p).forEach(function (k) {
          if (/^(\$initial_)?(utm_|gclid|fbclid|msclkid|gbraid|wbraid)/.test(k)) delete p[k];
        });
        p.site = 'rcn'; p.is_test = test; p.page_path = page;
        if (p.$exception_list) p.$exception_list = scrub(p.$exception_list);
        if (p.$exception_message) p.$exception_message = scrub(p.$exception_message);
        return event;
      },
      loaded: function (ph) {
        client = ph;
        queue.forEach(function (item) { ph.capture(item[0], item[1]); });
        queue = [];
      }
    });
  };
  document.head.appendChild(sdk);
  capture('$pageview', { $current_url: cleanUrl(location.href), $referrer: cleanUrl(document.referrer) });
  document.addEventListener('click', function (e) {
    var link = e.target.closest('a');
    if (!link) return;
    var href = link.getAttribute('href') || '';
    if (href.indexOf('tel:') === 0) capture('rcn_phone_click');
    else if (href.indexOf('mailto:') === 0) capture('rcn_email_click');
    else {
      var url;
      try { url = new URL(href, location.href); } catch (_) { return; }
      if (url.origin !== location.origin) return;
      if (url.hash === '#enquire') capture('rcn_enquiry_cta_click', { target_path: url.pathname });
      else if (/\/(avalon-waterways|scenic-river-cruise|emerald-river-cruise|amawaterways-river-cruise|viking-river-cruise)\.html$/.test(url.pathname)) {
        capture('rcn_operator_click', { target_path: url.pathname });
      }
    }
  });
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('form[action="submit-v2.php"]').forEach(function (form) {
      var started = false, viewed = false, submitted = false;
      var invalidFields = {};
      if ('IntersectionObserver' in window) {
        var observer = new IntersectionObserver(function (entries) {
          if (!viewed && entries.some(function (entry) { return entry.isIntersecting; })) {
            viewed = true; capture('rcn_form_viewed'); observer.disconnect();
          }
        }, { threshold: 0.05 });
        observer.observe(form);
      }
      form.addEventListener('focusin', function (e) {
        if (!started && e.target.matches('input:not([type="hidden"]),select,textarea')) {
          started = true; capture('rcn_form_started');
        }
      });
      form.addEventListener('invalid', function (e) {
        var field = e.target.name;
        if (!/^(first_name|last_name|email|phone|destination|travel_date|duration|guests|budget|operator)$/.test(field)) return;
        var v = e.target.validity;
        var reason = v.valueMissing ? 'required' : v.typeMismatch ? 'format' : 'invalid';
        var key = field + ':' + reason;
        if (!invalidFields[key]) {
          invalidFields[key] = true;
          capture('rcn_form_validation_error', { field_name: field, validation_reason: reason });
        }
      }, true);
      form.addEventListener('submit', function (e) {
        if (e.defaultPrevented || submitted) return;
        submitted = true; capture('rcn_form_submit_attempted');
      });
    });
    if (new URLSearchParams(location.search).get('error') === '1') {
      capture('rcn_form_handler_error');
    }
    if (page === '/thank-you.html') {
      capture('rcn_thank_you_viewed');
      if (document.cookie.split('; ').indexOf('rcn_lead_received=1') !== -1) {
        document.cookie = 'rcn_lead_received=; Max-Age=0; Path=/; Secure; SameSite=Lax';
        capture('rcn_lead_received', { confirmation_source: 'server_persistence_cookie' });
      }
    }
  });
  window.addEventListener('load', function () {
    // Defer until loadEventEnd has been recorded by the browser.
    setTimeout(function () {
      if (!window.performance || !performance.getEntriesByType) return;
      var nav = performance.getEntriesByType('navigation')[0];
      if (!nav) return;
      capture('rcn_page_load', {
        load_ms: Math.round(nav.loadEventEnd),
        dom_ready_ms: Math.round(nav.domContentLoadedEventEnd),
        ttfb_ms: Math.round(nav.responseStart - nav.requestStart),
        navigation_type: nav.type
      });
    }, 0);
  });
})();
