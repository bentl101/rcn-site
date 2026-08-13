# Discount Coach Tours review site

Static HTML/CSS/JS with a small PHP staging handler. It is intentionally marked `noindex` and stores QA submissions in a Docker volume without emailing the client or writing to a CRM.

## Pages

- `/` — lead-generation homepage and comparison form
- `/trafalgar-tours.html`
- `/globus-journeys.html`
- `/cosmos-tours.html`
- `/insight-vacations.html`
- `/thank-you.html`
- `/privacy.html` — draft wording awaiting client approval

## Logo pack

Vector masters and high-resolution PNG exports are in `assets/images/`:

- `dct-logo-horizontal.svg` / `.png` (2400 × 780 PNG)
- `dct-logo-square.svg` / `.png` (2048 × 2048 PNG)

## Local preview

```bash
docker compose up -d
curl -I http://127.0.0.1:8094/
```

Photography was generated for this review build. The source PNG files are retained locally; optimized WebP files are served by the site. Rebuild optimized assets with the bundled workspace Python runtime and `tools/build_assets.py`; rebuild operator pages with `tools/build_operator_pages.py`.

The production launch still needs approved CRM/email routing, tracking IDs, privacy language, operator artwork rights and conversion rules. See `CLIENT-QUESTIONS.md`.
