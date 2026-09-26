# Two separate production sites — read before editing or deploying

This repository contains TWO businesses' websites. The folder name `rivercruise`
is not a deployment source. Choose the site explicitly before doing any work.

| Detail | River Cruise Network (RCN) | Discount Coach Tours (DCT) |
|---|---|---|
| Public domain | https://book.rivercruisenetwork.com | https://book.discountcoachtours.ca |
| Canonical source | Tracked root HTML/PHP, `assets/`, `images/`, `.htaccess` | `dct-site/` only |
| Thank-you page | Root `thank-you.html` | `dct-site/thank-you.html` |
| Form handler | `submit-v2.php`; legacy `submit.php` includes it | `dct-site/submit.php` |
| Operators | Avalon, Scenic, Emerald, AmaWaterways, Viking | Trafalgar, Globus, Cosmos, Insight |
| Lead ID | `RCN-...` | `DCT-...` |
| n8n webhook | `/webhook/rcn-form`, `X-RCN-Token` | `/webhook/dct-form`, `X-DCT-Token` |
| Main n8n workflow | `zYw4HtTy1OTH7jUy` | `PmntlqBanV9ZMy3O` |
| Ads customer | `5306933986` | `3639225242` |
| Tracking | `GTM-5B2VFP82`, `AW-10929471967` | Separate DCT offline actions; never copy RCN tags |
| Deployment | FTPS `ftp.unitcostdominance.com`; RCN user; FTP root `/` | cPanel `/home/unitcostdominanc/book.discountcoachtours.ca/` |
| Private data | RCN server CSVs and secret include: preserve in place | `/home/unitcostdominanc/dct-private-data/` |

Both sites legitimately share phone 1-877-977-8586 and the agreed sales mailbox.
RCN's “a division of Discount Coach Tours” footer and shared business reviews are intentional.
Those shared details DO NOT make their pages, tracking, handlers or deployment paths interchangeable.

## Mandatory boundaries

1. **Never deploy the workspace recursively. Never upload `dct-site/` to RCN.**
2. **`rcn-site/` is an obsolete, incomplete, untracked duplicate, NOT the source.**
   It caused a stale RCN deployment. Do not edit, copy or deploy it. Its local-only
   contents are retained for recovery. Do not recreate a second RCN source there.
3. Use `sites.json` and `python3 ops/stage_site.py --site rcn|dct --output /tmp/UNIQUE_DIR FILE...`
   to prepare an explicit allowlisted upload. File names are relative to the chosen site's source.
   The staging tool is not a deployer. It refuses untracked/uncommitted files,
   symlinks, documentation, CSVs, secrets, and files belonging to the other site.
4. Read `SITE-BOUNDARIES.md` before deployment. Review the exact diff AND compare
   current live files before upload. Preserve live changes; do not assume Git is newer.
5. Commit only the intended files, push to GitHub, THEN upload the checked stage.
   Use the selected site's credentials and verified destination. Never use mirror deletion.
6. Before upload run `find STAGE -type f -exec chmod 644 {} \;` and
   `find STAGE -type d -exec chmod 755 {} \;`. Do not upload the repo or lead data.
7. After upload check every public HTML/CSS/JS/image URL, compare uploaded bytes,
   check all form actions/thank-you links, inspect desktop/mobile appearance, and
   verify private endpoints remain blocked. Ordinary GETs must not create test leads.
8. Never roll back tracking, change Ads customer IDs, copy n8n workflows between
   brands, or upload/replace live secrets as part of a visual website repair.

## RCN conversion and handler boundaries

The thank-you page's browser conversion is the **legacy baseline**
`AW-10929471967/wib4COjkqbQcEN-Dytso`, CAD 10, with lead-order deduplication.
Do not restore browser firing of main action `wiFkCM3XupwYEN-Dytso`; the main
conversion is handled server-side. Preserve form-start events, click attribution,
lead IDs and CSV-first persistence. Do not submit a real form just to test layout.

On 26 September 2026, the root `submit-v2.php` was aligned with the running
handler and the six pages retained the running attribution resolver. The server
handler was not redeployed. Historical July handler changes need a separate
review before restoration; old comments/history are not current production truth.

## Historical records

The previous mixed instruction files are retained locally in ignored
`.project-history/`. They contain historical status and outdated deploy commands.
This file and `SITE-BOUNDARIES.md` supersede those deployment instructions.
DCT-specific current details are in `dct-site/README.md`.

## Treg hosted catalog policy

Use the installed Treg skill and hosted treg.to catalog when external structured
APIs materially help. Prefer free/connected tools. Inspect endpoint parameters
and quoted price before each paid call. Ask before any call over $0.25 or task
spend over $1; batch requests. Use hosted endpoints only. Never upload or scan
local secrets/credentials, register credentials, expose tokens, or print
`~/.treg/config.json`. Report exact settled task spend after paid calls.
