# Discount Coach Tours production site

Static HTML/CSS/JS with a PHP lead handler, live at `https://book.discountcoachtours.ca/`.

## Production status

- Approved pages are public and indexable; thank-you and 404 remain `noindex`.
- Separate PPC pages and forms exist for Trafalgar, Globus, Cosmos and Insight Vacations.
- `submit.php` writes every valid lead to `~/dct-private-data/leads.csv` before calling n8n.
- Delivery attempts are audited in `~/dct-private-data/n8n-deliveries.csv`.
- The dedicated n8n webhook is `/webhook/dct-form`, protected by `X-DCT-Token`.
- Production emails route to `sales@discountcoachtours.ca` and `btl101@gmail.com`; QA submissions (`qa_test=1`) route only to Ben.
- UTMs, click IDs, landing page, referrer, operator, source page, device and time on page are captured.
- DCT-specific GTM/GA4 and Google Ads conversion tags still require an approved active DCT Ads account and tag IDs.

## Deployment

The cPanel document root is `/home/unitcostdominanc/book.discountcoachtours.ca/`. Secrets and lead files must remain outside it in `/home/unitcostdominanc/dct-private-data/`.

Before upload, set directories to `755` and files to `644`. Never upload tools, documentation, lead CSVs or secrets into the public document root. After deployment, test every HTML, CSS, JS and image URL for HTTP 200.

Rebuild operator pages with `python3 tools/build_operator_pages.py`.
