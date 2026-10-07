# RCN incomplete quote notifications

Enabled at Ben's request on 7 October 2026. Scope: the six RCN enquiry pages only.

- Native browser validation with at least one missing required field triggers a
  snapshot of the enquiry fields and an email to **btl101@gmail.com only**.
- No capture on typing, page views or valid submissions. Existing form validation,
  lead handling, CSV, n8n, CRM and Ads paths are unchanged. These notifications are
  not completed leads and are not evidence that the visitor abandoned the form.
- The email lists missing fields, entered details, page, reference and Ireland,
  Toronto and UTC timestamps. Blank attempts are included, even without contact
  details. A malformed email is noted when other required fields are also missing.
- The form notice explains that entered details from blocked attempts go to the
  website administrator. Never infer marketing consent from these notifications.
- `assets/js/rcn-incomplete-forms.js` coalesces the native invalid-field events into
  one notification. Identical details are deduplicated for ten minutes. Changed
  attempts can generate a new email. A failed request retries once after 3 seconds.
- `incomplete-form.php` uses the existing host's PHP mail transport with a fixed
  recipient. It accepts JSON from the RCN origin, validates page and field types,
  restricts payload size, and limits notifications to 30 per IP/hour and 300 total
  per hour. No recipient or mail header is accepted from visitor input.
- Deduplication/rate state contains only hashes, counts and expiry times in a
  mode-0600 file in PHP's temporary directory, outside the public document root.
  Stale entries expire within an hour and are removed on the next request. The
  notification body is never written to a public file or sent to PostHog.
- These are best-effort operational alerts: disabled JavaScript, connection loss,
  request blockers, rate limits or mail delivery failures can prevent notification.
  PHP mail acceptance is not proof of inbox delivery; check Gmail for the test.
  Old partial entries cannot be reconstructed from masked PostHog recordings.

Tests:

```sh
node ops/test_rcn_incomplete_forms.js
node ops/test_rcn_analytics.js
python3 ops/test_rcn_incomplete_endpoint.py
```

The endpoint test needs PHP and `/usr/bin/tee`. It runs a loopback PHP server with
mail redirected to a temporary file, creates no real leads and sends no emails.
For an end-to-end test use `?rcn_analytics_test=1`, identify the name and message as
TEST, leave a required field blank, and click Request Quote. Expect one email with
`[TEST] [RCN incomplete form]` and no thank-you redirect. Do not complete the form
for this test. Check the sole recipient and missing-field list in Gmail.

Deployment uses the RCN explicit stage allowlist. Removing the script reference
from the six pages disables collection without modifying the normal handler.
