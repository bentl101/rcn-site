# RCN site repair and separation — 26 September 2026

## Findings

- The six live RCN enquiry pages and handler matched the obsolete untracked
  `rcn-site/` copy byte-for-byte; their FTP timestamps were 10 September.
- The thank-you HTML and stylesheet were May versions. The thank-you page fired
  the main Ads action in the browser instead of the tracked legacy baseline.
- RCN branding, cruise-line navigation and shared business phone were present;
  no DCT-branded thank-you page was observed at the tested RCN URL.
- The deployed `.htaccess` only blocked `leads.csv`. Archived CSVs were reachable
  (HEAD HTTP 200); the mockup was also public. No lead CSV bodies were downloaded.
- DCT's 33 public pages/assets all matched its tracked files.

## Repair

- Restored the tracked July RCN callback/reviews/frontend improvements, retaining
  the exact running attribution resolver in every enquiry page.
- Restored the thank-you legacy baseline action, CAD 10, order-ID deduplication.
- Restored protection for all CSVs and secrets and blocked the mockup.
- Matched root PHP source to the running handler. Did not upload a PHP handler,
  secret, lead CSV, or change n8n/Ads account settings.
- Replaced conflicting AGENTS/CLAUDE files with explicit RCN/DCT scope tables,
  scoped DCT instructions and stop instructions in the obsolete RCN folder.
- Added `sites.json` and a staging guard requiring a selected site and explicit,
  committed, allowlisted files. Historical instructions remain ignored locally.
- All changes were committed and pushed before their related FTP upload.

## Two verification passes

Before upload:

- Compared every RCN page, stylesheet, image and tracked script against live.
- Confirmed all six form actions remain `submit-v2.php`; required fields and
  options are preserved. The restored optional second honeypot is not required.
- Verified all local links/assets and syntax of all inline JavaScript.
- Offline execution confirmed no conversion on direct visit, one legacy
  conversion with order ID after submission, and no repeat on refresh.
- Checked desktop and 390px layouts, mobile menu, review controls and callback.
- Staging guard rejected cross-site paths, secret files and uncommitted files.

After upload:

- **35/35 RCN public URLs returned 200**: 33 tracked HTML/CSS/JS/images matched
  local bytes, plus the existing phone-validation script and briefing page.
- **33/33 DCT public URLs returned 200 and still matched their original source.**
- Lead CSV and both archived CSVs returned 403; secret include returned 403;
  mockup returned 404.
- FTP readback confirmed the handler was unchanged and `.htaccess` matched.
- Browser reload confirmed CSS version `20260926a`, legacy conversion present,
  main browser conversion absent. Desktop and mobile thank-you checks passed;
  mobile document width was 390px at a 390px viewport.
- A previously opened browser tab used cached HTML until reload.
- Positive staging checks passed independently for both RCN and DCT.

Detailed non-PII URL statuses and hashes: `site-repair-verification-20260926.json`.
Private rollback copies: `/tmp/rcn-audit-20260926/`.
Screenshot and prior instruction files: ignored `.project-history/`.

No synthetic form submission was sent to sales. End-to-end CRM/email delivery
and server-side conversion attribution were not tested or changed in this repair.
