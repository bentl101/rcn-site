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

The production launch still needs approved CRM/email routing, tracking IDs, privacy language, operator artwork rights and conversion rules. See `CLIENT-QUESTIONS.md`.
