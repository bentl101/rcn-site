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
