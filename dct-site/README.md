# Discount Coach Tours production site

Static HTML/CSS/JS with a PHP lead handler, live at `https://book.discountcoachtours.ca/`.

## Production status

- Approved pages are public and indexable; thank-you and 404 remain `noindex`.
- Separate PPC pages and forms exist for Trafalgar, Globus, Cosmos and Insight Vacations.
- `submit.php` writes every valid lead to `~/dct-private-data/leads.csv` before calling either delivery path.
- The PHP/cPanel handler sends a direct hosting backup email and audits the attempt in `~/dct-private-data/direct-email-deliveries.csv`.
- The n8n handoff is audited separately in `~/dct-private-data/n8n-deliveries.csv`.
- The dedicated n8n webhook is `/webhook/dct-form`, protected by `X-DCT-Token`.
- Production emails route to `sales@rivercruisenetwork.com` through both the hosting backup and n8n. QA submissions (`qa_test=1`) route both copies to Ben at `btl101@gmail.com`.
- **(10 Sep 2026)** Google Ads has exactly two reusable account-level negative-keyword lists, both attached to the current DCT campaign: `DCT | Global Country Negatives` (176 broad-match non-approved country/destination terms, including Canada, USA and United States) and `DCT | Global Search Exclusions` (70 job, support, irrelevant-brand and other search exclusions). Kiran's approved destinations are excluded from the country list. All 28 live positive keyword criteria containing Canada or Morocco were removed, and the campaign builder no longer recreates them. The campaign's Canada geographic audience targeting remains in place so Canadian customers can still find the approved European-tour offers. The consolidation script is `tools/consolidate_google_ads_negatives.py`; it must be used for future negative-list changes rather than adding loose campaign criteria.
- **(10 Sep 2026)** `brochure` (broad) was removed from `DCT | Global Search Exclusions`, taking it from 71 terms to 70. A brochure request is buying intent for a tour agency, so excluding it was costing genuine top-of-funnel traffic. Removals go through `tools/consolidate_google_ads_negatives.py --remove-term "<text>"`, which only ever edits the search-exclusion list; the country list holds the destination policy and is not editable that way, so a typo cannot silently unblock a non-approved destination.
- **(10 Sep 2026)** The search campaign runs six ad groups: one per operator (`DCT | Trafalgar`, `DCT | Insight`, `DCT | Globus`, `DCT | Cosmos`), plus `DCT | Brand` and `DCT | Generic Coach Tours | HOLD`. The paired `Brand & Tours` / `Destinations` groups were merged one-per-operator to stop an already-thin conversion signal being split eight ways on a C$65/day budget. Each merged group holds both keyword sets and both RSAs. The four `| Destinations` groups were PAUSED, not removed, so the merge is reversible. The tool is `tools/consolidate_google_ads_ad_groups.py` (`--plan` / `--verify` are read-only, `--apply` mutates).
- **(10 Sep 2026)** While copying the destination RSAs into the merged groups, ad copy naming destinations DCT does not sell was replaced with approved ones: Morocco headlines and description mentions on Trafalgar and Insight, and 'Canada Tours' headlines and description mentions on Globus and Cosmos. Those assets predated the destination cleanup and were still serving. The originals survive in the paused groups. Note these came from later manual edits, not from `build_google_ads_campaign.py`, whose own `dest_heads` were always clean.
- **(10 Sep 2026)** `tools/build_google_ads_campaign.py` was brought back in sync with the live account and is a usable rebuild path again. It now emits the six-group structure with two RSAs per operator group, uses the live `| HOLD` generic group name, and attaches both negative shared sets via `ensure_shared_sets()`. That attachment matters: after the negatives moved out of the builder, a rebuild would otherwise have produced a campaign with no negative coverage at all. `ensure_ads()` keys on `(ad group, path2)` and only ever creates missing ads, so hand-edited live copy is never overwritten. `--verify` now reports `serving_*` counts alongside raw totals (raw counts include PAUSED groups and REMOVED criteria, so quote the `serving_` figures) plus `negative_coverage_ok`.
- UTMs, Google ValueTrack fields, separate GCLID/GBRAID/WBRAID values, landing page, referrer, operator, source page, device and time on page are captured. A first-party 90-day attribution cookie preserves the visit across pages, while a newer campaign visit replaces an older stored click bundle.
- Email and phone are normalized and SHA-256 hashed server-side for a future Enhanced Conversions for Leads rollout. Those identifiers are not sent to Google until DCT approves the disclosure and accepts Google's Customer Data Terms.
- The retained Google Ads client is `363-922-5242` under Copperchunk MCC `381-427-8874`. The later accidental duplicate `536-272-2800` was cancelled on 5 September 2026.
- Two primary `UPLOAD_CLICKS` actions are live: `DCT - Submit Lead Form (Offline - GCLID)` (`7748271517`, ONE_PER_CLICK) and `DCT - Submit Lead Form (Offline - Braid)` (`7748270854`, MANY_PER_CLICK). Both use a 90-day lookback and a CAD $50 default value.
- The live `DCT Form Handler` workflow (`PmntlqBanV9ZMy3O`) has 15 nodes: secured intake, hashed email-action token, isolated lead email, private Google Sheet append, Google OAuth/upload, Ads outcome update, partial-failure-first parsing and a Ben-only failure alert. The email and sheet branches cannot be blocked by an Ads failure.
- The live `DCT Lead Email Actions` workflow (`Gd8fvkAJjC4rJuJy`) is isolated from intake. It provides two-step good/bad buttons in production lead emails, records confirmed actions in the `Lead Actions` tab, waits at least 24 hours plus a 30-minute buffer before any Google Ads retraction, and stops processing after 54 days. Opening or previewing an email never mutates data.
- The private DCT lead spreadsheet is [Discount Coach Tours Leads & Retractions](https://docs.google.com/spreadsheets/d/1dY5JczBg7qkxMov1HmbPRlOpwPrrKwSndh5NiYXfVTY/edit). `Leads` contains the lead and Ads outcome projection; `Lead Actions` is the append-only confirmation/retraction queue; `Instructions` explains the workflow. Raw email action tokens are never stored in the sheet or CSV, only their SHA-256 digest.
- DCT-specific GA4/GTM remains optional and needs a DCT measurement ID/container if browser analytics is required. Offline Google Ads conversion tracking does not depend on it.

## Google Ads API status

The integration targets Google Ads API `v25`, the current major REST version as of 5 September 2026. Google released the non-breaking `v25.1` update on 19 August, but REST endpoints remain `/v25`. Version 25 is scheduled to sunset in August 2027. Upload requests always use `partialFailure: true`, inspect `partialFailureError` before `results`, use Google-compatible space-separated timestamps, identify the conversion environment as `WEB`, and support `validateOnly` QA without recording a conversion.

The current click-only path sends exactly one of GCLID, GBRAID or WBRAID. If DCT later authorizes Enhanced Conversions for Leads, the same workflow can send hashed email/phone and Google's documented GCLID+GBRAID combination; it never combines GCLID with WBRAID or GBRAID with WBRAID.

Google's post-15-June-2026 offline-upload eligibility change does not block Copperchunk's developer token because the token already has successful RCN upload history. On 5 September 2026, a live `validateOnly` request returned HTTP 200 from the conversion service and the expected `UNPARSEABLE_GBRAID` partial failure for a deliberately fake ID. This confirms OAuth, developer-token access, account routing, v25 request shape and partial-failure handling without recording a conversion. Final n8n execution `84421` also confirmed braid routing, no user identifiers, successful lead email, rejected-upload detection and the isolated failure alert. Execution `84409` confirmed ordinary QA leads bypass OAuth and Ads entirely while email still succeeds. Both PHP-to-n8n deliveries returned HTTP 200. A real conversion cannot be attribution-tested until there is a genuine click from a live DCT campaign; newly created actions also have Google's normal six-hour activation window.

## Deployment

The cPanel document root is `/home/unitcostdominanc/book.discountcoachtours.ca/`. Secrets and lead files must remain outside it in `/home/unitcostdominanc/dct-private-data/`.

Before upload, set directories to `755` and files to `644`. Never upload tools, documentation, lead CSVs or secrets into the public document root. After deployment, test every HTML, CSS, JS and image URL for HTTP 200.

Rebuild operator pages with `python3 tools/build_operator_pages.py`.

Configure or audit the Ads account with `python3 tools/google_ads_offline.py --validate-config`; `--apply` is idempotent after the target customer is explicitly confirmed. Deploy the DCT n8n workflows from the VPS (this updates both the main handler and the isolated email-action/retraction workflow):

```bash
python3 deploy_dct_email_actions.py --phase all
```

The compatibility entry point `python3 deploy_n8n_workflow.py` still patches the main handler only. Do not use it to recreate the workflow from scratch: the email-action deployment script is the authoritative source for the combined setup.

For a non-sensitive node-level QA summary, run `python3 inspect_n8n_execution.py EXECUTION_ID` on the n8n VPS. It reports routing and error classifications without printing PII, click IDs, OAuth tokens or other secrets.
