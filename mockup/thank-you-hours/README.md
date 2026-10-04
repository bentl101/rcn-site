# Thank-you phone-hours mockups

Open `index.html` to compare two options for each brand, including mobile and after-hours states. The review opens with a forced during-hours preview; choose “Actual Eastern time” to use the visitor-independent schedule. Individual pages use the real schedule unless the local-only `?preview=open|closed` override is supplied.

- Option 1: call first, with a large phone button and travel photo.
- Option 2: confirmation first, with a separate call panel below the acknowledgement.
- Both: toll-free `1-877-977-8586`, existing acknowledgement copy, and no new response-time promise for DCT.
- Schedule assumption: every day, 09:00 inclusive to 20:00 exclusive in `America/Toronto`, following EST/EDT. Rechecks every second and when returning to the tab. It follows Eastern time regardless of the visitor’s location. The user's wording “EST” may mean fixed UTC−5; confirm before production implementation if unanswered.
- After hours: hide the whole proposed call treatment and show the existing acknowledgement wording. Production implementation should retain each site's complete current thank-you page as its outside-hours fallback.

These are isolated design previews. They contain no analytics, conversion scripts, lead references, storage reads, handlers or forms. They do not confirm that a real enquiry was submitted. Existing production HTML, scripts and tracking remain untouched. Published separately at https://rcn-preview.copperchunk.com/thank-you-hours-20261004/ for client review. The existing preview homepage and production sites are unchanged. Only the four mockup pages, review page, CSS, timing JavaScript and four public image assets are uploaded.

When a direction is chosen, implement against each selected site's current live thank-you page, preserving RCN's legacy baseline conversion/deduplication and DCT's own completion event. Remove all forced preview controls and query overrides from the production implementation. Follow the repository's separate site staging and deployment procedures.
