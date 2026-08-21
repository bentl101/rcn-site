# Discount Coach Tours review site

Static HTML/CSS/JS with a small PHP staging handler, deployed at `https://book.discountcoachtours.ca/`. It is intentionally marked `noindex` and stores QA submissions privately without emailing the client or writing to a CRM. Docker deployments use the `dct_lead_data` volume; cPanel stores them outside the document root in `~/dct-private-data/`.

## Status — 21 August 2026

The review build is close to client sign-off.

- Live review domain and SSL are working at `https://book.discountcoachtours.ca/`.
- Separate PPC landing pages and preselected enquiry forms are complete for Trafalgar, Globus, Insight Vacations and Cosmos.
- The original client-supplied DCT logo and official operator marks are installed.
- Kiran's copy, budget, ordering and testimonial revisions are complete.
- The operator-only navigation, mobile callback CTA and responsive logo treatment are complete.
- The site remains `noindex` until production tracking, privacy wording and lead routing are approved.

## Google Ads account structure

Recommended setup: create a separate **Discount Coach Tours** Google Ads client account under the existing Copperchunk Ltd manager account (`381-427-8874`). Do not place DCT campaigns inside the River Cruise Network account, and do not create a second manager account unless a different billing owner or access hierarchy requires it.

Use DCT-specific conversion actions initially so its Smart Bidding learns from coach-tour leads rather than RCN's river-cruise data. Keep keyword coverage distinct between the brands and avoid using the two accounts to compete for the same queries.

## Pages

- `/` — lead-generation homepage and comparison form
- `/trafalgar-tours.html`
- `/globus-journeys.html`
- `/cosmos-tours.html`
- `/insight-vacations.html`
- `/thank-you.html`
- `/privacy.html` — draft wording awaiting client approval

## Logo pack

The review site now uses Kiran's client-supplied original artwork:

- `dct-logo-original.png` (2941 × 1558 high-resolution export)

The earlier concept variants remain in `assets/images/` for reference:

- `dct-logo-horizontal.svg` / `.png` (3000px-wide PNG)
- `dct-logo-square.svg` / `.png` (2048 × 2048 PNG)
- `dct-logo-mark.svg` / `.png` (1024 × 1024 icon/avatar)

## Local preview

```bash
docker compose up -d
curl -I http://127.0.0.1:8094/
```

Photography was generated for this review build. The source PNG files are retained locally; optimized WebP files are served by the site. Rebuild optimized assets with the bundled workspace Python runtime and `tools/build_assets.py`; rebuild operator pages with `tools/build_operator_pages.py`.

The production launch still needs final client sign-off, approved CRM/email routing, DCT-specific tracking IDs, privacy language, operator artwork rights and conversion rules. See `CLIENT-QUESTIONS.md`.
