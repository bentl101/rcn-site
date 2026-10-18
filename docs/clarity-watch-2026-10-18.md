# Clarity review tags — 18 October 2026

The website instrumentation is deployed to both production sites. Clarity's
saved segments and My Watchlist entries are **pending**: the new custom tags
were not available in the filter picker during verification. Receipt of the
new tags in Clarity's processed recordings has not yet been confirmed.

## Deployed changes

- RCN: commit `4c0a0f6`, eight public files (analytics script and seven HTML pages).
- DCT: commit `8e24896`, nine public files (analytics script and eight HTML pages).
- Both commits pushed to `codex/clarity-2026-2027` before upload.
- HTML changes only update the analytics script version to
  `20261018claritywatch`. Existing forms, offers, Ads tags, lead handling,
  attribution, and PostHog settings are preserved.
- The DCT page generator and its wiring assertion use the same version so a
  future page regeneration does not restore the old cached script URL.

The existing Clarity installations receive fixed event names and session tags.
No form values, raw error text, lead IDs, or URLs are added to these calls.
See [RCN tracking](rcn-posthog.md#clarity-review-tags) and
[DCT tracking](dct-posthog.md#clarity-review-queue) for the tag contracts.

`watch=yes` marks production sessions worth reviewing. `watch_reason` explains
why: form handler errors, JavaScript errors, unhandled rejections, repeated
validation failures on the same field, and thank-you visits. RCN also marks a
confirmed persistence signal as `lead_received`; DCT additionally marks resource
failures and missing pages. A thank-you visit is not a confirmed delivered lead.
Test sessions use `watch=qa` and `analytics_test=true`.

## Verification

- Fresh remote baselines matched the local files before either deployment.
- Explicit site-specific stages were prepared using `ops/stage_site.py`;
  files were set to 644 and directories to 755. Only the 17 intended public
  files were uploaded, through temporary names followed by replacement.
- All 17 uploaded files matched the staged bytes when downloaded again.
- All 129 allowlisted public HTML/CSS/JS/image URLs returned HTTP 200 and
  matched source bytes: 78 RCN and 51 DCT.
- HEAD-only private endpoint checks returned 403/404. No private file bodies
  were downloaded.
- RCN analytics, form UX, and incomplete-form regression checks passed.
  DCT analytics and form UX checks passed. Both analytics scripts passed
  JavaScript syntax checks; the DCT generator passed Python syntax parsing.
- Browser checks on RCN Avalon and DCT Globus confirmed correct Clarity
  project/script URLs, versioned analytics scripts, enquiry link navigation,
  form action, and keyboard focus. Desktop and 390px mobile layouts had no
  horizontal overflow. QA URLs carried the corresponding analytics test flag.
- No enquiry form was submitted and no thank-you page was visited in browser QA.
  No sales lead or incomplete-enquiry notification was intentionally generated.
- Independent code review checked tag allowlisting, QA isolation, event
  deduplication, privacy, and preservation of existing tracking behavior.

## Remaining Clarity UI configuration

Projects:

- [RCN](https://clarity.microsoft.com/projects/view/w1fe60o6ei/dashboard)
- [DCT](https://clarity.microsoft.com/projects/view/yfndqty55t/dashboard)

Once the keys and values appear under Filters → Custom filters → Custom tags,
create these segments in each project and add the saved segments to My Watchlist:

1. **Flagged enquiries:** `site=rcn` or `site=dct`, `watch=yes`, and exclude
   `analytics_test=true`.
2. **Potential incomplete enquiries:** the matching `site`,
   `enquiry_started=yes`, exclude `enquiry_thank_you_viewed=yes`, and exclude
   `analytics_test=true`. For RCN also exclude `enquiry_received=yes`.

Use exclusion of `analytics_test=true`, rather than inclusion of false, because
multiple tag values can accumulate in one session. Potential incomplete enquiries
are review candidates, not proven lost leads. Confirm a labelled QA recording
contains the expected tags before treating the new review views as verified.
My Watchlist is personal to the signed-in Clarity user; these tags do not
automatically star/favorite recordings. PostHog replay and billing settings
remain unchanged.
