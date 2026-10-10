# DCT form assistance — 10 October 2026

Scope: DCT homepage, Trafalgar, Globus, Cosmos and Insight enquiry forms.
RCN is not changed by this release.

## Changes

- Persistent inline errors and an accessible linked summary after a native
  invalid attempt. Focus moves to the first invalid field, clear of the header.
- Corrected fields clear immediately; unchanged summaries are not re-announced
  on every keystroke. Existing accessible descriptions are preserved.
- Hints use DCT's actual choices: budget **Not sure yet**, trip length **Flexible**.
  Error colours support both themes; grid fields remain top-aligned beside errors.
- Operator-page destination tags populate the destination input. Later tag
  selections can replace a previous automatic selection, never a typed value.
- Destination selection focuses the form card outside the form element. This
  avoids opening the mobile keyboard or triggering DCT's input/focus-based
  form-start events just from destination selection.
- Native required/email validation, all nine required fields, optional operator
  on the homepage, contact preferences, existing submit/attribution script,
  order IDs, lead handler, privacy copy, analytics and Ads routing are retained.
  No new collection or partial-enquiry email feature is introduced.
- The operator-page builder gains the form script and current existing analytics
  reference so a later rebuild retains both. Pages were not regenerated, avoiding
  unrelated differences in current live content and image optimisations.

## Baseline and tests

- The five HTML pages and CSS matched SFTP, public HTTPS and repository source.
  Rollback copies: `/private/tmp/dct-form-fix-jZ221R/baseline/` (public files only).
- Node checks: `ops/test_dct_form_ux.js`, `ops/test_dct_analytics.js` and
  `ops/test_rcn_form_ux.js`; new script syntax and Git whitespace checks passed.
- Isolated localhost preview blocked external connections and stubbed POSTs.
  Empty attempts produced nine errors, no order ID and an enabled submit button.
  Email format corrections, required-field corrections, keyboard error links,
  pre-fill changes and manual-text preservation were checked.
- A valid local Trafalgar submission retained its DCT order ID, GCLID/generic
  click ID, operator, destination and all required values. No live lead, email or
  conversion was created.
- At 390px width, all five forms had no horizontal overflow, focused the first
  invalid input visibly, and did not run their valid-submit path on errors.
  All four operator destination selections matched the clicked text and focused
  outside the form, with its top about 118px below the viewport top.
- Desktop light/dark rendering checked. Homepage operator remained optional.
  With the enhancement script removed in the local fixture, native validation
  still focused the first required field and blocked submission.

## Deployment procedure

Commit and push first; stage with `ops/stage_site.py --site dct`.
Upload only `assets/js/dct-form-ux.js`, `assets/css/site.css` and the five HTML
pages to `/home/unitcostdominanc/book.discountcoachtours.ca/`, with explicit
temporary-file/rename SFTP operations. Recheck live baselines before upload.
Never upload the builder, tests, docs, handler, secrets or lead data.
Verify all allowlisted public assets, private-path protections and live rendering
without submitting a production form. Technical success does not prove a lead
conversion-rate improvement; evaluate genuine delivered leads with QA excluded.

## Production verification

- Release `d7c1d3a` was pushed before staging and deployment. The seven public
  files above were uploaded individually after live-baseline comparisons, using
  temporary files and rename; staged file/directory permissions were 644/755.
- All 51 allowlisted public HTML/CSS/JS/image URLs returned HTTP 200 and matched
  the repository bytes. All five enquiry forms still post to `/submit.php`.
- HEAD probes of `leads.csv`, `dct-secrets.php`, `data/` and `tools/` returned
  HTTP 404. DCT's actual private leads and secrets remain outside the public
  directory and were not accessed or replaced. The verification helper initially
  expected 403 for the first two nonexistent public paths; that test expectation
  was corrected to 404, without changing server protections.
- Live Trafalgar desktop and 390px mobile destination links populated the
  selected destination and focused the form card outside the form, approximately
  116px below the viewport top. Keyboard activation worked, native validation
  remained enabled, and neither viewport had horizontal overflow. No browser
  console errors were recorded on that live page.
- No production form was submitted. No live test lead, email or conversion was
  created. Existing unrelated working-tree changes were left untouched.
