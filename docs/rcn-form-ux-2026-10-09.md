# RCN form assistance — 9 October 2026

Scope: the six root RCN enquiry pages only. DCT is unchanged.

## Behaviour

- Keep native `required` / email validation. No `novalidate`, replacement submit
  listener, handler changes or synthetic submit events.
- After a blocked attempt, show persistent field messages and an accessible
  linked error summary. Focus the first invalid field in view, clear errors as
  fields become valid, and avoid repeating identical announcements on typing.
- Budget and duration hints reference choices already available in that form.
- An operator offer card copies its existing heading into an empty itinerary,
  or replaces a previous automatic selection. It does not replace typed text.
- Offer activation focuses the form heading (not an input), keeps it below the
  sticky header, and supports keyboard activation. This avoids automatically
  opening a mobile keyboard or firing an input-based form-start event.
- Native invalid events still reach the existing incomplete-notification and
  analytics listeners. No entered values are newly sent anywhere.
- Sales copy, required fields, date defaults, CTA wording, attribution, order-key
  creation, duplicate-submit guard, PHP, n8n and Ads conversion tags are unchanged.

## Verification before deployment

- Downloaded six HTML pages and CSS over SFTP; all matched both public HTTPS and
  local source before edits. Rollback copies are in
  `/private/tmp/rcn-form-fix-0LQjFR/baseline/` (public files only).
- `node ops/test_rcn_form_ux.js`, `node ops/test_rcn_incomplete_forms.js`,
  `node ops/test_rcn_analytics.js`, syntax and whitespace checks passed.
- Isolated localhost browser tests blocked all third-party connections and
  replaced POST endpoints with local stubs. No live lead/email/conversion was
  created. The Avalon two-missing-field case showed itinerary/budget errors;
  corrections removed errors and allowed the existing normal submit path.
- Local successful submit retained the generated RCN order key and QA click ID.
  Two changed invalid attempts reached the local notification stub beforehand.
- Desktop Avalon appearance checked. At 390px width, all six pages had no
  horizontal overflow and showed missing-field errors. All five operator offer
  selections carried the correct heading into itinerary and focused the form
  heading around 100px below the viewport top. Keyboard error links focused
  their corresponding input. A manually typed itinerary was preserved.

## Release constraints

Commit and push before staging. Deploy only the six HTML pages,
`assets/css/style.css` and `assets/js/rcn-form-ux.js`, with explicit atomic SFTP
temporary-file/rename uploads to the verified RCN document root. Recheck live
originals against the baseline immediately before upload. Keep handlers, private
data, analytics and incomplete-notification scripts untouched.

After release, verify every allowlisted public HTML/CSS/JS/image against source,
protected endpoints, live mobile/desktop rendering and browser errors. Technical
passing checks are not proof of improved genuine delivered lead volume; compare
subsequent account-local periods with QA excluded.

## Production verification

- Release `2946ce0` pushed to `codex/clarity-2026-2027` before staging/upload.
  The live-baseline recheck passed, then all eight files were uploaded with
  temporary-file/rename operations to the verified RCN root.
- All **78** allowlisted HTML/CSS/JS/image files returned HTTP 200 and exactly
  matched source. `leads.csv` and `rcn-secrets.php` returned 403; `mockup/` and the
  nonexistent `leads-archive.csv` probe returned 404. No private bodies fetched.
- Live Avalon at 1280px and 390px: correct offer itinerary, form-heading focus
  below the sticky header, native validation enabled, no horizontal overflow.
  The persistent-error component was installed. No browser errors observed in
  the checked live session. Existing form action is still `submit-v2.php`.
- No production form submission or incomplete-form email was triggered by QA.
  All submission/invalid-attempt tests used isolated localhost endpoints.
- User's pre-existing changes and untracked material were left untouched.
