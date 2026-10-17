# RCN scorer: Sol 6.1 with Anthropic fallback

Scope: RCN workflow `zYw4HtTy1OTH7jUy` only. No website deployment.

The latest enquiries received the emergency default 80 because the primary
requested retired GPT-5.5 and the OpenCode Go fallback key had expired.
The custom runner preferred stderr warnings over the actual model error in
stdout. A direct scorer-only diagnostic established the unsupported model error.

## Change

- Primary: `gpt-6.1-sol`, retaining high reasoning and the live scoring prompt.
- Fallback: Anthropic Messages API, `claude-sonnet-5-5`, with a JSON schema and
  strict response validation. Its prompt uses the current primary scoring policy.
- The current `ANTHROPIC_API_KEY` from Bitwarden was transferred over SSH stdin
  into a dedicated encrypted n8n HTTP Header credential. No key is stored here,
  in workflow JSON, in the helper, or in its state files.
- Fallback input is restored from `Build Signals`; primary error items are not
  trusted to retain the lead. The existing `Parse Score` still owns hard caps.
- The established emergency fail-open score/delivery policy is preserved.
  Its `scorer_error` audit flag now correctly reports an outage.
- OpenCode Go's reusable workflow and DCT are outside the patch.

The shared Codex CLI was 0.147.0 and also rejected Sol 6.1. An RCN-only install
of official `@openai/codex@0.162.1` fixed the compatibility issue. The launcher is
`ops/rcn_codex_sol61.sh`, installed in the container as
`/home/node/.n8n/codex/rcn-codex-sol61`. Its runtime is under
`/home/node/.n8n/codex/rcn-runtime-0.162.1/`. Other launchers were not replaced.

## Verification

The isolated test workflows contain only synthetic lead features and scorer
nodes. They cannot send email, write CRM/Sheets, or upload Google Ads conversions.

- Primary: `codex:gpt-6.1-sol:high`, 95, send to sales, no scorer error.
- Forced primary failure: `anthropic:claude-sonnet-5-5`, 95, send to sales,
  original lead and features preserved, no scorer error.
- Both routes unavailable: existing emergency 80, send to sales, scorer error
  true, original lead preserved.
- Each temporary test workflow and its executions were removed after testing.
- Eight candidate parser regressions passed: valid contacts, invalid phone,
  both contacts invalid, email-only invalidity, Chris/Christmas name collision,
  full scorer outage, outage with invalid phone, and outage with both contacts
  invalid.

## Deployment result

Committed and pushed as `5dd2b4c`, then applied through the n8n API.
Read-back confirmed the workflow is active and its published `activeVersionId`
equals the new `versionId` (`ec5a75e6-bb95-4e17-a178-ad10ab793c6e`).
The dedicated Anthropic credential reference is present and the old OpenCode Go
fallback nodes are absent from RCN. Unrelated nodes and live `staticData` were
unchanged. No real lead was replayed and no test email or conversion was sent.

The helper backs up the immediate live baseline, rejects configuration drift,
and omits `staticData` from PUT to preserve live pacing and deduplication state.
Private snapshots stay in `/home/ben/infra/n8n/workflow-backups/` on the VPS.

Sources: [Codex model retirement](https://learn.chatgpt.com/docs/models#gpt-55-retirement),
[Codex CLI releases](https://learn.chatgpt.com/docs/changelog),
[Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
