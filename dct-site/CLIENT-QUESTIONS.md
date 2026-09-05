# Discount Coach Tours — post-launch items

Updated 5 September 2026. The approved website is live at `https://book.discountcoachtours.ca/`.

## Completed

- Approved design, copy, contact details, operator pages, responsive logo and desktop header.
- Production lead capture with private CSV source-of-truth and a dedicated secured n8n workflow.
- Email routing to Discount Coach Tours sales, with Ben copied for monitoring.
- Attribution capture for UTMs, click IDs, landing page, referrer, operator and device.
- Public indexing, canonical URLs, robots.txt and sitemap.
- Google Ads account selection: retain `363-922-5242`; accidental duplicate `536-272-2800` is cancelled and can be reactivated if ever needed.
- Google Ads API v25 offline uploads are live in the retained account, with separate GCLID and braid conversion actions, validate-only QA, partial-failure detection and Ben-only failure alerts. Synthetic end-to-end tests passed without recording a conversion.

## Still to confirm

1. Which production CRM should receive DCT leads when the client migration is complete?
2. Suri should accept the pending ADMIN invitation for Google Ads account `363-922-5242`.
3. Add billing to `363-922-5242` before campaigns are launched; billing is not required to create or test conversion actions.
4. Confirm that DCT accepts Google's Customer Data Terms and approve privacy wording that explicitly covers sending hashed email/phone to Google. Until then, click-ID conversions can run but Enhanced Conversions user identifiers stay off.
5. Supply or approve a DCT-specific GTM/GA4 measurement ID if browser analytics is wanted. It is not required for the server-side Ads conversion upload.
6. Confirm the retention period and deletion process for private lead records.

Recommendation: keep DCT in a separate Google Ads client account under the existing Copperchunk manager account so its conversion data and bidding signals remain separate from River Cruise Network.
