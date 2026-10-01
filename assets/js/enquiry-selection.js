(() => {
  'use strict';
  document.addEventListener('click', (event) => {
    if (!(event.target instanceof Element) || event.button !== 0 ||
        event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const choice = event.target.closest('a[data-itinerary]');
    if (!choice) return;
    const destination = document.querySelector('#enquire input[name="destination"]');
    if (!destination) return;
    destination.value = choice.dataset.itinerary;
    destination.dispatchEvent(new Event('input', { bubbles: true }));
    destination.dispatchEvent(new Event('change', { bubbles: true }));
    const status = document.querySelector('[data-enquiry-selection]');
    if (status) status.textContent = `Your selected cruise: ${destination.value}. You can change it below.`;
    destination.focus({ preventScroll: true });
  });
})();
