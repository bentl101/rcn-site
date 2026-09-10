# Discount Coach Tours production site

Static HTML/CSS/JS with a PHP lead handler, live at `https://book.discountcoachtours.ca/`.

## Production status

- Approved pages are public and indexable; thank-you and 404 remain `noindex`.
- Separate PPC pages and forms exist for Trafalgar, Globus, Cosmos and Insight Vacations.
- `submit.php` writes every valid lead to `~/dct-private-data/leads.csv` before calling n8n.
- Delivery attempts are audited in `~/dct-private-data/n8n-deliveries.csv`.
- The dedicated n8n webhook is `/webhook/dct-form`, protected by `X-DCT-Token`.
- Production emails route to `sales@rivercruisenetwork.com`; QA submissions (`qa_test=1`) route only to Ben.
- Google Ads has a reusable account-level list named `DCT | Global Country Negatives` with 176 broad-match non-approved country/destination terms, including Canada, USA and United States. It is applied to the current DCT campaign; Kiran's approved destinations are excluded. On 10 September 2026, all 28 live positive keyword criteria containing Canada or Morocco were removed, and the campaign builder no longer recreates them. The campaign's Canada geographic audience targeting remains in place so Canadian customers can still find the approved European-tour offers.
- UTMs, Google ValueTrack fields, separate GCLID/GBRAID/WBRAID values, landing page, referrer, operator, source page, device and time on page are captured. A first-party 90-day attribution cookie preserves the visit across pages, while a newer campaign visit replaces an older stored click bundle.
- Email and phone are normalized and SHA-256 hashed server-side for a future Enhanced Conversions for Leads rollout. Those identifiers are not sent to Google until DCT approves the disclosure and accepts Google's Customer Data Terms.
- The retained Google Ads client is `363-922-5242` under Copperchunk MCC `381-427-8874`. The later accidental duplicate `536-272-2800` was cancelled on 5 September 2026.
- Two primary `UPLOAD_CLICKS` actions are live: `DCT - Submit Lead Form (Offline - GCLID)` (`7748271517`, ONE_PER_CLICK) and `DCT - Submit Lead Form (Offline - Braid)` (`7748270854`, MANY_PER_CLICK). Both use a 90-day lookback and a CAD $50 default value.
- The live `DCT Form Handler` workflow (`PmntlqBanV9ZMy3O`) has 10 nodes: secured intake, isolated lead email, Google OAuth/upload, partial-failure-first parsing and a Ben-only failure alert. The email branch cannot be blocked by an Ads failure.
- DCT-specific GA4/GTM remains optional and needs a DCT measurement ID/container if browser analytics is required. Offline Google Ads conversion tracking does not depend on it.

## Google Ads API status

The integration targets Google Ads API `v25`, the current major REST version as of 5 September 2026. Google released the non-breaking `v25.1` update on 19 August, but REST endpoints remain `/v25`. Version 25 is scheduled to sunset in August 2027. Upload requests always use `partialFailure: true`, inspect `partialFailureError` before `results`, use Google-compatible space-separated timestamps, identify the conversion environment as `WEB`, and support `validateOnly` QA without recording a conversion.

The current click-only path sends exactly one of GCLID, GBRAID or WBRAID. If DCT later authorizes Enhanced Conversions for Leads, the same workflow can send hashed email/phone and Google's documented GCLID+GBRAID combination; it never combines GCLID with WBRAID or GBRAID with WBRAID.

Google's post-15-June-2026 offline-upload eligibility change does not block Copperchunk's developer token because the token already has successful RCN upload history. On 5 September 2026, a live `validateOnly` request returned HTTP 200 from the conversion service and the expected `UNPARSEABLE_GBRAID` partial failure for a deliberately fake ID. This confirms OAuth, developer-token access, account routing, v25 request shape and partial-failure handling without recording a conversion. Final n8n execution `84421` also confirmed braid routing, no user identifiers, successful lead email, rejected-upload detection and the isolated failure alert. Execution `84409` confirmed ordinary QA leads bypass OAuth and Ads entirely while email still succeeds. Both PHP-to-n8n deliveries returned HTTP 200. A real conversion cannot be attribution-tested until there is a genuine click from a live DCT campaign; newly created actions also have Google's normal six-hour activation window.

## Deployment

The cPanel document root is `/home/unitcostdominanc/book.discountcoachtours.ca/`. Secrets and lead files must remain outside it in `/home/unitcostdominanc/dct-private-data/`.

Before upload, set directories to `755` and files to `644`. Never upload tools, documentation, lead CSVs or secrets into the public document root. After deployment, test every HTML, CSS, JS and image URL for HTTP 200.

Rebuild operator pages with `python3 tools/build_operator_pages.py`.

Configure or audit the Ads account with `python3 tools/google_ads_offline.py --validate-config`; `--apply` is idempotent after the target customer is explicitly confirmed. Deploy n8n from the VPS with both public conversion action IDs:

```bash
python3 deploy_n8n_workflow.py --gclid-action-id 7748271517 --braid-action-id 7748270854
```

For a non-sensitive node-level QA summary, run `python3 inspect_n8n_execution.py EXECUTION_ID` on the n8n VPS. It reports routing and error classifications without printing PII, click IDs, OAuth tokens or other secrets.
