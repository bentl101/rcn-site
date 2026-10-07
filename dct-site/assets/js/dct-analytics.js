/* Discount Coach Tours error monitoring. No enquiry values are collected. */
(function () {
  'use strict';
  if (location.hostname !== 'book.discountcoachtours.ca') return;
  var test = new URLSearchParams(location.search).get('dct_analytics_test') === '1';
  var client = null, queue = [];
  function cleanUrl(value) {
    try { var u = new URL(value, location.origin); return u.origin + u.pathname; }
    catch (_) { return ''; }
  }
  function scrub(value) {
    if (typeof value === 'string') return value
      .replace(/https?:\/\/[^\s"<>]+/g, function (url) { return cleanUrl(url); })
      .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[email]')
      .replace(/\+?\d[\d ()-]{7,}\d/g, '[number]');
    if (Array.isArray(value)) return value.map(scrub);
    if (value && typeof value === 'object') {
      var out = {}; Object.keys(value).forEach(function (k) { out[k] = scrub(value[k]); }); return out;
    }
    return value;
  }
  function capture(name, props) {
    var data = Object.assign({site:'dct',page_path:location.pathname,is_test:test},props || {});
    if (client) client.capture(name,data); else queue.push([name,data]);
  }
  window.addEventListener('error',function(e){
    if (!client && e.message) capture('$exception',{$exception_list:[{type:'Error',value:scrub(e.message),mechanism:{type:'onerror',handled:false}}]});
    if (!e.message && e.target && /^(SCRIPT|LINK|IMG)$/.test(e.target.tagName)) capture('dct_resource_error',{resource_type:e.target.tagName,resource_url:cleanUrl(e.target.src || e.target.href || '')});
  },true);
  window.addEventListener('unhandledrejection',function(e){
    if (!client) capture('$exception',{$exception_list:[{type:'UnhandledRejection',value:scrub(String(e.reason && e.reason.message || e.reason || 'Unhandled promise rejection')),mechanism:{type:'onunhandledrejection',handled:false}}]});
  });
  var sdk=document.createElement('script'); sdk.async=true;
  sdk.src='https://eu-assets.i.posthog.com/static/array.js';
  sdk.onload=function(){
    if (!window.posthog) return;
    window.posthog.init('phc_z4tZPtzYJK6oDj7pEofSkNhg6RAeNejNxrbBTYvc9tYC',{
      api_host:'https://eu.i.posthog.com',ui_host:'https://eu.posthog.com',
      person_profiles:'never',autocapture:false,capture_pageview:false,capture_pageleave:false,
      capture_dead_clicks:false,capture_exceptions:true,capture_performance:false,
      enable_recording_console_log:false,
      session_recording:{maskAllInputs:true,maskTextSelector:'form',recordBody:false,recordHeaders:false,recordCrossOriginIframes:false,maskCapturedNetworkRequestFn:function(){return undefined;}},
      before_send:function(event){
        if (!event) return event; var p=event.properties || {};
        ['$current_url','$referrer','$initial_current_url','$initial_referrer'].forEach(function(k){if(p[k])p[k]=cleanUrl(p[k]);});
        Object.keys(p).forEach(function(k){if(/^(\$initial_)?(utm_|gclid|fbclid|msclkid|gbraid|wbraid)/.test(k))delete p[k];});
        p.site='dct';p.is_test=test;p.page_path=location.pathname;
        if(p.$exception_list)p.$exception_list=scrub(p.$exception_list);
        if(p.$exception_message)p.$exception_message=scrub(p.$exception_message);
        return event;
      },
      loaded:function(ph){client=ph;queue.forEach(function(item){ph.capture(item[0],item[1]);});queue=[];}
    });
  };
  document.head.appendChild(sdk);
  capture('$pageview',{$current_url:cleanUrl(location.href),$referrer:cleanUrl(document.referrer)});
  var reason=new URLSearchParams(location.search).get('form_error');
  if(reason)capture('dct_form_handler_error',{reason:['missing','email','server'].indexOf(reason)>=0?reason:'other'});
  if(location.pathname==='/404.html')capture('dct_page_not_found');
  document.addEventListener('DOMContentLoaded',function(){
    if(document.title.indexOf('Page not found')===0 && location.pathname!='/404.html')capture('dct_page_not_found');
    document.querySelectorAll('[data-lead-form]').forEach(function(form){
      var started=false;
      form.addEventListener('focusin',function(){if(!started){started=true;capture('dct_form_started');}});
      form.addEventListener('submit',function(){capture('dct_form_submit_attempted');},true);
    });
    if(location.pathname==='/thank-you.html')capture('dct_thank_you_viewed');
  });
})();
