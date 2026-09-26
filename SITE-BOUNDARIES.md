# Deployment map: two independent sites

## River Cruise Network

- URL: https://book.rivercruisenetwork.com/
- Source: tracked root HTML/PHP, `assets/`, `images/`, `.htaccess`.
- **Never deploy the obsolete `rcn-site/` folder.** It lacks the thank-you page
  and assets and contains older page/handler copies.
- FTPS: `ftp.unitcostdominance.com:21`, explicit TLS, user
  `rcn-deploy@book.rivercruisenetwork.com` (verified current credential), root `/` (not `/public_html/`).
- Credentials: untracked `~/.rcn-deploy.env`. Never print or commit them.
- Preserve all live CSV logs and `rcn-secrets.php`; never upload local copies.

## Discount Coach Tours

- URL: https://book.discountcoachtours.ca/
- Source: `dct-site/` only.
- cPanel root: `/home/unitcostdominanc/book.discountcoachtours.ca/`.
- Private storage: `/home/unitcostdominanc/dct-private-data/`.
- RCN FTP credentials are never a DCT deployment route.
- Details: `dct-site/README.md` and `dct-site/AGENTS.md`.

## Required deployment procedure

1. Name the target site and read its scoped instructions. Fetch the current live
   versions of each intended file and review their differences from Git.
2. Review content, links, form action, tracking IDs and redirect destination.
   Run relevant behavioural checks locally. Check the changes a second time
   against the live baseline. Do not submit synthetic sales leads for visual QA.
3. Commit only the reviewed changes and push. Stage explicit files:

   ```sh
   python3 ops/stage_site.py --site rcn --output /tmp/rcn-UNIQUE thank-you.html
   # Or, for DCT:
   python3 ops/stage_site.py --site dct --output /tmp/dct-UNIQUE thank-you.html
   ```

   Check the printed domain and destination. `sites.json` is the public-file
   allowlist. New public files require a reviewed manifest update. The guard
   rejects the other site's paths, secrets, lead data, docs and uncommitted files.
4. Run the required permissions commands on that stage:

   ```sh
   find /tmp/SELECTED_STAGE -type f -exec chmod 644 {} \;
   find /tmp/SELECTED_STAGE -type d -exec chmod 755 {} \;
   ```

5. Upload ONLY the staged files to the selected destination. Use explicit `put`
   commands or a stage-only upload. Never mirror the repository or stale
   `rcn-site/`, and never use deletion flags. Keep a private local rollback copy.
6. Fetch all public HTML/CSS/JS/images and require HTTP 200. Verify uploaded
   files byte-for-byte. Check desktop/mobile appearance and navigation. Verify
   all CSVs and secrets return 403 and mockup returns 404 on RCN. Retain the
   result counts in the repair report. Do not fetch lead CSV bodies for this test.

## 26 September 2026 repair

The live RCN six enquiry pages and PHP handler exactly matched the obsolete
`rcn-site/` duplicate. Their FTP timestamps were 10 September. The thank-you
page and stylesheet were older May versions. This proves a stale deployment;
it does not identify the actor responsible. No DCT-branded thank-you content
was found at the tested RCN URL.

Restored the reviewed RCN frontend, retaining the running attribution resolver.
The thank-you page again uses the legacy baseline action rather than the main
server-side conversion action. Restored access rules for archived CSVs,
secret includes and mockups. Root PHP now mirrors the running handler for
source accuracy; no PHP handler, live secret, lead log or n8n workflow was
uploaded or changed by this repair.

The obsolete folder remains locally for recovery, with stop instructions and
Git ignores. The old mixed AGENTS/CLAUDE documents are preserved locally in
ignored `.project-history/`. Current instructions are short, explicit and tracked.
