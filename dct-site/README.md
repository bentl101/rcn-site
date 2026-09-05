# Discount Coach Tours production site

Static HTML/CSS/JS with a PHP lead handler, live at `https://book.discountcoachtours.ca/`.

## Production status

- Approved pages are public and indexable; thank-you and 404 remain `noindex`.
- Separate PPC pages and forms exist for Trafalgar, Globus, Cosmos and Insight Vacations.
- `submit.php` writes every valid lead to `~/dct-private-data/leads.csv` before calling n8n.
- Delivery attempts are audited in `~/dct-private-data/n8n-deliveries.csv`.
- The dedicated n8n webhook is `/webhook/dct-form`, protected by `X-DCT-Token`.
- Production emails route to `sales@discountcoachtours.ca` and `btl101@gmail.com`; QA submissions (`qa_test=1`) route only to Ben.
- UTMs, Google ValueTrack fields, separate GCLID/GBRAID/WBRAID values, landing page, referrer, operator, source page, device and time on page are captured. A first-party 90-day attribution cookie preserves the visit across pages, while a newer campaign visit replaces an older stored click bundle.
- Email and phone are normalized and SHA-256 hashed server-side for a future Enhanced Conversions for Leads rollout. Those identifiers are not sent to Google until DCT approves the disclosure and accepts Google's Customer Data Terms.
- The retained Google Ads client is `363-922-5242` under Copperchunk MCC `381-427-8874`. The later accidental duplicate `536-272-2800` was cancelled on 5 September 2026.
- `tools/google_ads_offline.py` configures two `UPLOAD_CLICKS` actions: ONE_PER_CLICK for GCLID and MANY_PER_CLICK for GBRAID/WBRAID, as required by Google.
- `tools/deploy_n8n_workflow.py` deploys API v25 click uploads, validate-only QA, partial-failure-first parsing and Ben-only failure alerts. Action IDs are supplied at deployment time and no secret is committed.
- DCT-specific GA4/GTM remains optional and needs a DCT measurement ID/container if browser analytics is required. Offline Google Ads conversion tracking does not depend on it.

## Google Ads API status

The integration targets Google Ads API `v25`, the current major REST version as of 5 September 2026. Google released the `v25.1` client-library/schema update on 19 August, but REST endpoints remain `/v25`. Version 25 is scheduled to sunset in August 2027. Upload requests always use `partialFailure: true`, inspect `partialFailureError` before `results`, use Google-compatible space-separated timestamps, and support `validateOnly` QA without recording a conversion.

Google's post-15-June-2026 offline-upload eligibility change should not block Copperchunk's developer token because the same token already has successful RCN upload history. A live validate-only call is still required after the DCT actions are created; newly created actions may return `TOO_RECENT_CONVERSION_ACTION` during Google's six-hour activation window.

## Deployment

The cPanel document root is `/home/unitcostdominanc/book.discountcoachtours.ca/`. Secrets and lead files must remain outside it in `/home/unitcostdominanc/dct-private-data/`.

Before upload, set directories to `755` and files to `644`. Never upload tools, documentation, lead CSVs or secrets into the public document root. After deployment, test every HTML, CSS, JS and image URL for HTTP 200.

Rebuild operator pages with `python3 tools/build_operator_pages.py`.

Configure the Ads account with `python3 tools/google_ads_offline.py --validate-config`, then `--apply` after the target customer is explicitly confirmed. Deploy n8n from the VPS with both public conversion action IDs:

```bash
python3 deploy_n8n_workflow.py --gclid-action-id 123 --braid-action-id 456
```
