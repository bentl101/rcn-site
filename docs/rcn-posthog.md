# River Cruise Network PostHog integration

EU project: [River Cruise Network](https://eu.posthog.com/project/296667).
Dashboard: [Visitor friction and enquiries](https://eu.posthog.com/project/296667/dashboard/1003001).

The private personal API key stays in Bitwarden Secrets Manager (`POSTHOG`).
The public browser ingestion token in `assets/js/rcn-analytics.js` cannot administer
the account. DCT and SpyOnAds are separate from this project.

## Events

| Event | Meaning |
|---|---|
| `$pageview` | Page opened; query strings removed |
| `rcn_operator_click` | Internal operator-page link clicked |
| `rcn_enquiry_cta_click` | Link to the enquiry section clicked |
| `rcn_phone_click`, `rcn_email_click` | Contact link clicked; no address or phone value |
| `rcn_form_viewed` | At least 5% of the form entered the viewport, once per page |
| `rcn_form_started` | First focus in an editable form field, once per page |
| `rcn_form_validation_error` | Native browser validation failure; field name and reason only, deduplicated per field/reason per page |
| `rcn_form_submit_attempted` | Valid form submit event; not a confirmed lead |
| `rcn_form_handler_error` | Handler returned to `?error=1`; not a PHP exception monitor |
| `rcn_thank_you_viewed` | Thank-you page opened, including direct visits |
| `rcn_lead_received` | Thank-you page consumed a one-use cookie set when the handler's CSV persistence flag was true |
| `rcn_page_load` | Real browser full-load, DOM-ready and server-response timings in milliseconds |
| `$web_vitals` | SDK Core Web Vitals, including LCP, INP and CLS where supported |
| `$exception` | Browser JavaScript errors and unhandled promise rejections |

All events carry `site=rcn`, `page_path` and `is_test`. The funnel is pageview →
form viewed → started → submit attempted → lead received, within one day.
Received is not qualified, CRM-delivered or Ads-converted. Browser blocking or
navigation can prevent analytics delivery even when a real lead was persisted.
The marker contains no lead ID or personal data and expires after ten minutes.

## Privacy and recordings

All form inputs are masked, as is form text. Autocapture, console recording,
network body/header capture and person profiles are disabled. URL queries and
fragments are removed from analytics URL properties; exception messages have
email addresses, long numbers and URL queries redacted. No form values or
existing GTM enhanced-conversion payloads are forwarded to PostHog.

Replay is enabled at 100% with 30-day retention. Monitor usage against the
account's recording allowance; adjust sampling in the dedicated RCN project's
replay settings as traffic warrants. The SDK is loaded asynchronously; blocked
analytics does not prevent enquiries. Existing Clarity and Ads tags remain.

## Email alerts

Two enabled hourly trend alerts notify the existing PostHog user
`btl101@gmail.com` when browser errors or handler-error redirects exceed zero.
These are scheduled checks, not an immediate email per exception. Both exclude
test events. PHP fatal errors, silent mail-delivery failures and downstream n8n
failures are outside this browser integration's coverage.

## Safe verification

Use `?rcn_analytics_test=1` on a public RCN page for analytics-only QA. All saved
insights and email alerts exclude `is_test=true`. Do not submit a sales form.
For a persistent browser opt-out, set `rcn_analytics_opt_out=1` in localStorage.

Run `node ops/test_rcn_analytics.js` for isolation, privacy, event semantics,
deduplication, timing, mandatory-destination labels and the legacy Ads baseline.
Deploy only the explicit RCN allowlist with `ops/stage_site.py`; compare fresh
live versions before upload and preserve all live secrets and lead CSVs.
