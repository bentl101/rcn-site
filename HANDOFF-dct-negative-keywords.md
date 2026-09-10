# HANDOFF — DCT negative-keyword list consolidation

**Created:** 10 September 2026
**Audited:** 10 September 2026 (independent read-only verification passed; see Outcome below)
**Project:** Discount Coach Tours
**Purpose:** Have Claude independently double-check the live Google Ads negative-keyword cleanup.

## Status

The cleanup has been applied through the Google Ads REST API v25 and verified successfully. The account should now contain exactly two enabled account-level negative-keyword shared sets attached to the DCT campaign, with no loose campaign-level negative keywords.

No site files, forms, tracking, ads, positive keywords, budget, bidding, or campaign status were changed in this task. No FTP deployment was needed.

## Live account and campaign

- Google Ads customer ID: `3639225242` — Discount Coach Tours
- Campaign: `DCT | Search | Canada | Operators | 2026`
- Campaign resource: `customers/3639225242/campaigns/24230451785`
- At final verification the campaign reported `ENABLED` / `LEARNING` with the existing C$65/day budget and `MAXIMIZE_CONVERSIONS` bidding.
- The earlier positive-keyword cleanup removing Canada/Morocco terms remains separate and untouched.

## What was changed in Google Ads

Before this task there was one shared country list and 71 campaign-level negative keyword criteria.

The API work:

1. Kept the existing `DCT | Global Country Negatives` list unchanged.
2. Confirmed that Kiran's approved destinations did not appear in that list:
   `England, Britain, Scotland, Ireland, Italy, Sicily, Greece, Spain, France,
   Croatia, Portugal, Scandinavian Countries, Germany, Switzerland, Netherlands,
   Holland, Austria, Hungary, Czech Republic, Prague, Budapest, Turkey, Japan,
   Egypt, Africa, South Africa, Peru`.
3. Created `DCT | Global Search Exclusions` as an enabled `NEGATIVE_KEYWORDS` shared set.
4. Copied all 71 unique campaign-level negative terms into the new list, retaining each term's original match type.
5. Attached both shared sets to the DCT campaign.
6. Removed the 71 loose campaign-level negative criteria only after the copied terms and attachments were verified.

Final expected state:

| Shared list | Resource | Criteria | Attached |
|---|---|---:|---|
| `DCT | Global Country Negatives` | `customers/3639225242/sharedSets/12229326229` | 176 | Yes |
| `DCT | Global Search Exclusions` | `customers/3639225242/sharedSets/12228813141` | 71 | Yes |

The final campaign-level negative-keyword count is `0`. The campaign still has its normal location and language criteria; those are not negative keywords.

Google describes shared sets as reusable account-level collections that must be linked to campaigns: <https://developers.google.com/google-ads/api/docs/targeting/shared-sets?hl=en>.

## Verification already completed

The consolidation script returned:

- `negative_shared_list_count: 2`
- both lists `ENABLED`
- both lists attached
- `search_list_criteria_count: 71` (now 70 - `brochure` removed 10 Sep 2026)
- `campaign_negative_count: 0`
- `migrated_terms_missing_from_search_list: []`
- `protected_destination_overlap: []`
- `ok: true`

The independent campaign snapshot returned:

- campaign `ENABLED`, primary status `LEARNING`
- budget C$65/day
- bidding `MAXIMIZE_CONVERSIONS`
- 10 ad groups
- 176 positive keyword criteria (175 ENABLED + 1 REMOVED `globus canada tours`; quote the enabled figure)
- 10 approved responsive search ads
- 5 campaign criteria total: one Canada location target, one English language target, three auto-created DESKTOP/MOBILE/TABLET device criteria (no bid modifiers, non-negative), and no negative keywords

A local JSON backup of the pre-removal campaign-level criteria was written to:

`/private/tmp/dct-negative-backup-20260910-142411.json`

## Local implementation

New idempotent tool:

`dct-site/tools/consolidate_google_ads_negatives.py`

It supports:

```bash
cd dct-site/tools
python3 consolidate_google_ads_negatives.py --plan
python3 consolidate_google_ads_negatives.py --verify
python3 consolidate_google_ads_negatives.py --apply
```

`--plan` and `--verify` are read-only. `--apply` is the only mutating mode. The script refuses to continue if it finds unexpected negative shared sets, an unexpected attached shared set, a disabled target list, or an approved destination in the country list. It will not remove criteria until coverage has been checked.

The campaign builder was also changed so future runs do not recreate the old campaign-level negatives. Negative-list changes should go through the consolidation tool instead.

Relevant documentation was updated in `dct-site/README.md`.

Git commit: `96fa03e` — `Consolidate DCT negative keywords into shared lists`
Remote branch pushed: `origin/feature/gclid-valuetrack`

## Claude's independent double-check

Please perform a read-only audit first. Do not use `--apply`, delete shared sets, pause/enable campaigns, change budgets, or modify positive keywords unless a separate issue is found and explicitly discussed.

1. Run the two verification commands from `dct-site/tools`:

   ```bash
   python3 consolidate_google_ads_negatives.py --verify
   python3 build_google_ads_campaign.py --verify
   ```

2. Independently query the Google Ads API and confirm:

   - exactly two `NEGATIVE_KEYWORDS` shared sets exist in customer `3639225242`;
   - their names are exactly the two names above;
   - both are `ENABLED`;
   - the country list has 176 criteria and the search-exclusion list has 71;
   - both are linked to campaign `24230451785`;
   - no other negative shared set is attached;
   - the campaign has zero negative `campaign_criterion` rows;
   - every pre-migration campaign negative term/match-type is present in the search-exclusion list;
   - no approved destination listed above appears in the country list;
   - Canada, USA/United States, Morocco and other non-approved destinations remain excluded as intended;
   - no positive keyword containing Canada or Morocco has been reintroduced.

3. Review the local diff and confirm the builder no longer contains an active loop that creates campaign-level negative keywords:

   ```bash
   git show --stat --oneline 96fa03e
   rg -n "NEGATIVES|negative.*campaign|shared" dct-site/tools/build_google_ads_campaign.py dct-site/tools/consolidate_google_ads_negatives.py
   ```

4. Confirm no secrets are present in the handoff, script, diff, or output. The API helper loads credentials from the existing untracked environment file; do not print or commit it.

## Acceptance criteria

The handoff is complete when Claude can independently report that the two enabled shared lists are present and attached, the 71 terms were preserved, campaign-level negative criteria are zero, approved destinations are not blocked, and campaign delivery settings remain unchanged.


---

## Outcome of the independent audit (10 September 2026)

Audit passed. Verified independently of the consolidation script's own logic:
two enabled `NEGATIVE_KEYWORDS` shared sets and no others in the account, both
attached with `ENABLED` link status, 176 + 71 unique criteria, zero campaign-level
negative criteria, all 71 migrated terms present with match types preserved and
no extras, no approved destination present in either list, and no enabled positive
keyword containing Canada or Morocco. A conflict check of all 175 enabled positive
keywords against all 247 negatives found no keyword blocked by its own negatives.
Campaign delivery settings were unchanged.

Follow-up items raised by the audit and since actioned, all 10 September 2026:

1. `build_google_ads_campaign.py` had lost negative coverage entirely. The
   consolidation removed its `NEGATIVES` loop but added no shared-set attachment,
   so a rebuild would have produced a campaign with no negatives, and its
   `--verify` reported `negative_keyword_count: 0` without checking shared sets,
   making that look healthy. Fixed via `ensure_shared_sets()` plus
   `negative_coverage_ok` in the snapshot.
2. The ad group structure was consolidated from ten groups to six.
3. `brochure` was removed from the search-exclusion list.
4. Live destination RSAs still advertised Morocco and tours of Canada. Replaced
   with approved destinations during the ad group merge.

Open item, not actioned. `Canada` is a BROAD negative in a campaign that targets
Canada geographically. Broad negatives match the search query, not the user's
location, so this blocks queries such as `trafalgar tours canada`, which the
account's own RSA headline `Trafalgar Tours Canada` is written to serve. It does
not conflict with any positive keyword, so it was left in place pending a decision
on whether to narrow it to phrase negatives (`canada tours`, `tours of canada`,
`canadian rockies`, `banff`, `jasper`, `niagara falls`) that still exclude tours
of Canada without blocking Canadians who name their own country in the query.
