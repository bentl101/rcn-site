# Discount Coach Tours PostHog

Dedicated EU project: https://eu.posthog.com/project/297565/activity/events

Only `book.discountcoachtours.ca` is instrumented by `assets/js/dct-analytics.js`.
This script is loaded on all eight public HTML pages before the existing site script.
Existing Clarity, forms and attribution are preserved. No PHP files are changed.

Captured events include pageviews, form starts/submit attempts, thank-you views,
JavaScript exceptions and unhandled promise rejections (`$exception`), resource
load failures (`dct_resource_error`), missing pages (`dct_page_not_found`), and
handler redirects (`dct_form_handler_error`, recognised `form_error` values).
A thank-you view is not proof of persisted or delivered lead data.

From 8 October, `dct_form_validation_error` records browser validation failures
on all five enquiry pages. Properties are allowlisted `field_name` and
`validation_reason` (`required`, `format`, or `invalid`), alongside the existing
page/site/test context. No entered value or browser validation-message text is
collected. The listener uses capture phase for native non-bubbling `invalid`
events, preserves native validation, and deduplicates each field/reason pair
per form/page load. These counts represent distinct field/reason failures on a
page visit, not the number of submit-button clicks. Existing submit events still
mean the form passed native validation. Historical missing-field failures cannot
be reconstructed. This adds PostHog events, not incomplete-enquiry emails.

Run `node ops/test_dct_analytics.js` for validation/privacy/queue/isolation checks.

Four enabled hourly email alerts notify btl101@gmail.com when the previous hour
has at least one matching non-test error. These are scheduled checks rather than
instant notifications. Existing RCN JavaScript and handler alerts remain enabled.
PostHog test-delivery responses confirmed one email recipient and no failed channels.

Session replay is enabled with inputs and form text masked. Autocapture, console
recording and network body/header recording are disabled. Analytics removes URL
query strings, campaign/click IDs, and redacts email addresses and long numbers
in exception text. No field values or lead identifiers are sent by this script.
The public ingestion token cannot administer PostHog; the private API credential
is accessed through the Bitwarden secrets wrapper.

Use `?dct_analytics_test=1` for QA. All alert queries exclude `is_test=true`.
Browser monitoring cannot detect every server-side error, email delivery failure,
or downstream processing issue. Existing server delivery monitoring is separate.
If the analytics library is blocked, browser error reporting may be unavailable.

## Verification, 7 October 2026

- Commits `ee64a38` and `e72681a` pushed before allowlisted SFTP deployment.
- Nine public tracking/page files matched uploaded bytes; all 50 public HTML,
  CSS, JavaScript and image URLs returned HTTP 200.
- Live pageviews and `dct_form_handler_error` arrived in project 297565;
  diagnostic visits carry `is_test=true` and are excluded from alert queries.
- Behaviour checks passed for DCT/RCN isolation, startup errors, unhandled
  rejections, handler and resource failures, URL scrubbing and input masking.
- The DCT CSP now permits only the required EU PostHog asset/ingestion hosts.
- Two existing raw PHP backups were found reachable using HEAD requests only;
  a narrow FilesMatch deny rule now returns 403 for both. Private lead/secret
  checks returned 404. No backup body or lead data was retrieved.
- No sales enquiry was submitted. Shell access is disabled on this account;
  SFTP with the existing Mac SSH key succeeded.

## Validation-event verification, 8 October 2026

Commit `1132cea` deployed through an explicit nine-file DCT stage using SFTP
uploads to temporary names followed by atomic replacements. All nine deployed
files matched staged bytes; all 50 public page/asset URLs returned 200 and matched
source. Private endpoints remained inaccessible. The labelled Globus browser
test generated nine `required` events and one email `format` event, verified in
PostHog with a fresh query at 17:02 UTC. Repeated missing-field checks did not
multiply those events. Native validation prevented submission; no lead created.
Desktop and 390px mobile checks passed. Existing open/cached pages require a
fresh page load to use the versioned script reference.
