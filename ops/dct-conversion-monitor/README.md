# DCT conversion monitor — n8n, no AI

Installed 8 November 2026 on `n8.copperchunk.com`:

- Main: `nYykpcjg66A1gGsy` — <https://n8.copperchunk.com/workflow/nYykpcjg66A1gGsy>
- Failure handler: `7YF3Kx5wsBeHM0fs`
- Schedule: **09:40 Europe/Dublin every day**, including DST changes.
- Recipient: **btl101@gmail.com only**, through the existing Google Workspace SMTP credential.
- Replaces the daily Codex automation `monitor-dct-data-manager`, paused after
  the verified production run on 8 November 2026 at 20:43 UTC.

There are no model nodes, paid research calls or AI tokens in either workflow.
All business-data requests are reads. The monitor cannot upload conversions,
adjust bids, retract conversions or edit lead/queue/action records. Its only
writes are private monitoring checkpoints and notification emails.

## Checks and coverage

Reads selected non-contact columns from the private DCT Leads and Lead Actions
sheets, the conversion queue, authenticated n8n intake executions, Google Ads
offline upload diagnostics for account `3639225242`, and conversion action
`7762251563`. No UI automation or hosting credentials are used.

- Reconciles eligible, non-QA GCLID leads from the last 32 days. Unresolved
  watched orders remain checked when they age beyond that window.
- Retains a seven-day cache of non-PII intake Order IDs and statuses to survive
  n8n execution pruning. At installation, the server retained intake history
  from 6 November, so the cache starts there and grows naturally.
- Explicitly recognizes the scorer's quarantine/spam triplets. Unknown statuses
  are flagged rather than silently excluded.
- Validates action name, click-ID agreement, duplicate queue orders, active bad
  or withheld rows, and bad leads whose inactive queue label is not `retracted`.
- Accepts `uploaded_api` and `uploaded_dm` for already-accepted conversions;
  these must not be reactivated or replayed. Pending fallback uses `active`.
- Checks overdue retractions (30-minute worker grace), expiry, terminal failure
  and repeated retry milestones. Future scheduled first/second attempts are quiet.
- Checks Google upload statuses/errors and fallback rows older than 36 hours
  without a newer connector upload receipt.
- Validates schemas and bounded intake coverage. Source failures cannot resolve
  existing discrepancies or report a falsely healthy result.

**Coverage limits are deliberate and visible in each report/email:**

1. Google's upload diagnostics show the last **nonempty upload**, in
   `America/Toronto`. They do not expose successful empty scheduled runs or the
   connection screen's schedule, mapping or credential status. This monitor
   cannot prove that an empty daily import ran by 09:30. It checks real upload
   errors and stalled active fallback rows instead.
2. The private hosting CSV is not accessible from this environment. Independent
   reconciliation uses authenticated n8n intake history. A website submission
   that never reaches n8n is outside this monitor's coverage.
3. The monitor itself runs in n8n. If the whole n8n service is unavailable,
   its own email nodes cannot run; infrastructure monitoring remains separate.

Reference: [Google Ads upload diagnostics](https://developers.google.com/google-ads/api/docs/conversions/upload-summaries).

## Alerts, retries and privacy

Read nodes retry up to three total attempts, five seconds apart. A separate
active error workflow sends monitor-execution failures. This installed n8n
runtime requires the error workflow to be active; an initial forced test
confirmed the inactive handler would not run, so deployment activates both.

Emails include non-PII Order IDs, concise classifications, attempt/retry counts,
Google's latest available nonempty-upload timestamp/status and next actions.
Unchanged issues are deduplicated; new issues and resolutions are emailed.
Retry milestones count as worsening issues. Dedupe commits only after successful
email delivery. Failed sources preserve existing unresolved checkpoints.

Raw execution data is not retained by the monitor, because upstream intake
executions contain contacts and tokens. Only sanitized reports, a bounded
non-PII ID cache and counts persist in workflow static data. Credentials remain
in n8n's encrypted credential store or existing environment expressions. The
private test webhook requires its own random header credential.

The initial acknowledgement contains five previously reported discrepancies:

- Missing queue mirrors for `DCT-20261022-161336-9ecd047a` and
  `DCT-20261031-174655-c7b28629`. Both were accepted by the API: repair mirrors
  with `uploaded_api`, **do not resend**.
- Inactive stale queue labels after accepted retractions for
  `DCT-20260921-155556-6fa3536e`, `DCT-20260924-020525-58936292`, and
  `DCT-20261003-182611-f39e1163`.

These were not repaired by this monitoring migration. They remain visible in
the saved report without repeating old alerts.

## Maintenance and verification

Source files are `audit.js`, `build.py`, `deploy.py`, and `test.js` here. Server
installation: `/home/ben/infra/dct-conversion-monitor/`. Registry, trigger key
and backups there are private; never commit them.

```sh
node ops/dct-conversion-monitor/test.js
python3 ops/dct-conversion-monitor/build.py --output /tmp/dct-monitor-build
```

On the n8n VPS, `deploy.py install` idempotently updates only these two workflows,
preserves static state, backs up old versions, and publishes both. It does not
modify DCT intake or action/retraction workers.

```sh
python3 /home/ben/infra/dct-conversion-monitor/deploy.py dry-run
python3 /home/ben/infra/dct-conversion-monitor/deploy.py run
python3 /home/ben/infra/dct-conversion-monitor/deploy.py status
```

`test-alert` emails a labelled delivery test; `test-failure` deliberately fails
only the private monitor branch to test its independent alert handler. Neither
submits a form or changes business data. Normal checks with no changes send
nothing.

Initial validation: 36 deterministic regression tests; supported-node JS and
graph validation; live read-only reconciliation; normal production run;
SMTP delivery test received in Ben's Gmail; separate forced-failure path.
The first live check read 193 lead rows and 162 queue rows, checked 123 recent
GCLID leads (112 eligible, 11 withheld), found no pending retractions, and
matched the five acknowledged discrepancies. Both Ads clients were `EXCELLENT`.
