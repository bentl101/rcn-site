# DCT private CSV schema repair — 10 October 2026

## Scope and cause

User-authorized repair of DCT's private lead CSV only. No RCN files, frontend
assets, recipients, n8n workflows, Sheets, Ads actions or conversions changed.

The original header contained 48 fields. Fifteen older rows matched it; 63 newer
rows contained 46 fields because the handler no longer included `departure_city`
and `pace`. Header-based readers consequently mislabelled later values, including
the QA flag. The named JSON delivery and email paths were unaffected.

## Implementation

Commit `b33a1fa` adds an include-only `dct-site/csv-log.php`, updates the DCT
handler and adds the helper to the explicit deployment allowlist. The live
handler exactly matched the saved pre-change baseline immediately before upload.
The commit was pushed before staging/deploying only `csv-log.php` and `submit.php`.
Both uploaded files were downloaded again and matched the staged bytes.

- Keep the original 48-column schema; new records leave retired fields blank.
- Lock before reading the header; map new values by column name.
- Repair only the known 46-field transition, preserving all original values.
- Require a verified private backup before rewriting under the original file's
  lock. Keep its inode, so an already-open legacy append descriptor is not lost.
- Reject unexpected schemas without changing their data; restore original bytes
  on a detected repair-write failure. A process/server crash during an in-place
  rewrite still requires recovery from the retained backup.
- The repair is an idempotent POST preflight. An empty POST then fails ordinary
  required-field validation, with no lead, email or webhook. GET remains read-only.
- Helper direct web requests return 403 with no content. All data and backups
  remain outside the public document root.

## Verification

PHP 8.3 lint and all 64 synthetic regression checks passed. Coverage includes
mixed historical rows, every field's position/value, multiline/quoted/Unicode
values, formula protection, backup byte equality and permissions, backup failure,
unknown schemas, repeat repair, 20 concurrent first appends, a late legacy writer,
GET/empty POST behavior, and full isolated handler persistence with mail and cURL
disabled. Existing DCT form UX and analytics regression suites also passed.

Live repair ran at approximately **10:00 UTC on 10 October 2026**:

| Check | Result |
|---|---|
| Records before and after | 78 / 78 |
| Misaligned records repaired | 63 |
| Original 48-field records preserved | 15 |
| Historical field values/order | All retained exactly |
| Resulting record width | 48 throughout |
| Backup compared with pre-repair snapshot | Byte-for-byte match |
| Repeated empty POST | Same log bytes; no additional backup |
| Hosting-email and n8n audit logs | Unchanged |
| Existing QA order's header-decoded flags | `qa_test=1`, `ads_validate_only=0` |
| Public HTML/CSS/JS/images | 51 HTTP 200; exact source-byte matches |
| Private CSV/secrets/data/tools URLs | 404 |
| Handler GET / helper GET | 303 to `/` / 403 |
| Enquiry form actions | Correct DCT handler |
| Desktop/mobile appearance | Checked; no frontend changes |

One verification-only SFTP download timed out. The read-only verification was
resumed successfully; no additional repair or lead submission was made for the retry.

## Recovery

The server retains the original private snapshot:

`/home/unitcostdominanc/dct-private-data/leads.csv.schema-backup-20261010-100037-94ee9d943267`

Do not casually replace the current CSV with this old snapshot: that would
reintroduce the mismatch and could discard subsequent leads. Any recovery must
account for new arrivals and acquire the same file lock. Restoring the old PHP
handler alone would also reintroduce short rows. No private lead contents or
secrets are committed with this report.
