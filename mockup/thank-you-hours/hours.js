/* Local mockup only. No tracking, storage access or form submissions. */
(() => {
  const zone = 'America/Toronto';
  function isPhoneHours(date = new Date()) {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: zone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
    }).formatToParts(date);
    const hour = Number(parts.find(part => part.type === 'hour').value);
    const minute = Number(parts.find(part => part.type === 'minute').value);
    return hour * 60 + minute >= 540 && hour * 60 + minute < 1200;
  }
  window.isPhoneHours = isPhoneHours;
  function render() {
    // Overrides belong to this isolated design preview; omit when implementing.
    const preview = new URLSearchParams(location.search).get('preview');
    const open = preview === 'open' ? true : preview === 'closed' ? false : isPhoneHours();
    document.querySelector('[data-open]').hidden = !open;
    document.querySelector('[data-closed]').hidden = open;
    document.body.dataset.phoneHours = open ? 'open' : 'closed';
  }
  render();
  setInterval(render, 1000);
  document.addEventListener('visibilitychange', render);
})();
