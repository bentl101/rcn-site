#!/usr/bin/env python3
"""Merge the paired operator ad groups in the DCT campaign into one per brand.

Before: each operator has a "Brand & Tours" group and a "Destinations" group,
both pointing at the same landing page. That splits an already-thin conversion
signal eight ways on a small daily budget.

After: one ad group per operator holding both keyword sets and both RSAs, plus
the untouched ``DCT | Brand`` and ``DCT | Generic Coach Tours | HOLD`` groups.

The source groups are PAUSED rather than removed so the merge is reversible.

Destination RSA assets naming a destination RCN does not sell (Morocco, tours
of Canada) are replaced with an approved destination during the copy, so the
merge does not re-publish off-offer ad copy into the surviving group.

Mutations require the explicit ``--apply`` flag.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import time
from typing import Any

import google_ads_offline as ads

CID = "3639225242"
CAMPAIGN = "customers/3639225242/campaigns/24230451785"

HEADLINE_MAX = 30
DESCRIPTION_MAX = 90

# survivor (renamed to `new_name`)            source group folded into it
MERGES = [
    {
        "survivor": "DCT | Trafalgar | Brand & Tours",
        "source": "DCT | Trafalgar | Destinations",
        "new_name": "DCT | Trafalgar",
    },
    {
        "survivor": "DCT | Insight | Brand & Tours",
        "source": "DCT | Insight | Destinations",
        "new_name": "DCT | Insight",
    },
    {
        "survivor": "DCT | Globus | Brand & Tours",
        "source": "DCT | Globus | Destinations",
        "new_name": "DCT | Globus",
    },
    {
        "survivor": "DCT | Cosmos | Brand & Tours",
        "source": "DCT | Cosmos | Destinations",
        "new_name": "DCT | Cosmos",
    },
]

UNTOUCHED = ["DCT | Brand", "DCT | Generic Coach Tours | HOLD"]

# Destinations Kiran approved. Used to validate every replacement asset.
APPROVED_DESTINATIONS = {
    "england", "britain", "scotland", "ireland", "italy", "sicily", "greece",
    "spain", "france", "croatia", "portugal", "scandinavian countries",
    "germany", "switzerland", "netherlands", "holland", "austria", "hungary",
    "czech republic", "prague", "budapest", "turkey", "japan", "egypt",
    "africa", "south africa", "peru",
}

# Off-offer RSA copy -> approved replacement. Applied only when copying a
# source RSA into the survivor group.
ASSET_REPLACEMENTS = {
    "Trafalgar Morocco Tours": "Trafalgar Portugal Tours",
    "Italy, Ireland, Scotland, Greece, Spain and Morocco. Ask about Trafalgar tour dates.":
        "Italy, Ireland, Scotland, Greece, Spain and Portugal. Ask about Trafalgar tour dates.",
    "Insight Vacations Morocco": "Insight Vacations Greece",
    "Italy, Ireland, Scotland, England, Spain and Morocco. Ask about Insight tour dates.":
        "Italy, Ireland, Scotland, England, Spain and Greece. Ask about Insight tour dates.",
    "Globus Canada Tours": "Globus Spain Tours",
    "Italy, Ireland, Scotland, France, Greece and Canada. Ask about Globus tour dates.":
        "Italy, Ireland, Scotland, France, Greece and Spain. Ask about Globus tour dates.",
    "Cosmos Canada Tours": "Cosmos Portugal Tours",
    "Italy, Ireland, Scotland, Spain, Greece, France and Canada. Ask about tour dates.":
        "Italy, Ireland, Scotland, Spain, Greece, France and Portugal. Ask about tour dates.",
}


def search(env: dict[str, str], token: str, query: str) -> list[dict[str, Any]]:
    """Read query with retries. The RSA asset query is heavy and times out."""
    last: Exception | None = None
    for attempt in range(4):
        try:
            return ads.search(env, token, CID, query)
        except (TimeoutError, OSError) as exc:
            last = exc
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"search failed after retries: {last}")


def mutate(
    env: dict[str, str],
    token: str,
    service: str,
    operations: list[dict[str, Any]],
) -> dict[str, Any]:
    if not operations:
        return {"results": []}
    status, payload = ads.request_json(
        env,
        token,
        "POST",
        f"{ads.API_ROOT}/customers/{CID}/{service}:mutate",
        {"operations": operations, "partialFailure": False},
    )
    if status != 200 or payload.get("partialFailureError"):
        message = (
            payload.get("error", {}).get("message")
            or payload.get("partialFailureError", {}).get("message")
            or "unknown error"
        )
        raise RuntimeError(f"{service} mutate failed ({status}): {message}")
    return payload


def read_state(env: dict[str, str], token: str) -> dict[str, Any]:
    groups = {}
    for row in search(
        env, token,
        "SELECT ad_group.resource_name, ad_group.id, ad_group.name, ad_group.status "
        f"FROM ad_group WHERE campaign.resource_name = '{CAMPAIGN}'",
    ):
        g = row["adGroup"]
        groups[g["name"]] = {
            "resource_name": g["resourceName"],
            "id": g["id"],
            "name": g["name"],
            "status": g.get("status"),
        }

    keywords: dict[str, list[dict[str, Any]]] = {}
    for row in search(
        env, token,
        "SELECT ad_group.resource_name, ad_group_criterion.resource_name, "
        "ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type, "
        "ad_group_criterion.status FROM ad_group_criterion "
        f"WHERE campaign.resource_name = '{CAMPAIGN}' "
        "AND ad_group_criterion.type = KEYWORD "
        "AND ad_group_criterion.status = 'ENABLED'",
    ):
        crit = row["adGroupCriterion"]
        keywords.setdefault(row["adGroup"]["resourceName"], []).append({
            "text": crit["keyword"]["text"],
            "match_type": crit["keyword"]["matchType"],
        })

    ads_by_group: dict[str, list[dict[str, Any]]] = {}
    for row in search(
        env, token,
        "SELECT ad_group.resource_name, ad_group_ad.ad.id, ad_group_ad.status, "
        "ad_group_ad.ad.final_urls, "
        "ad_group_ad.ad.responsive_search_ad.headlines, "
        "ad_group_ad.ad.responsive_search_ad.descriptions, "
        "ad_group_ad.ad.responsive_search_ad.path1, "
        "ad_group_ad.ad.responsive_search_ad.path2 "
        f"FROM ad_group_ad WHERE campaign.resource_name = '{CAMPAIGN}' "
        "AND ad_group_ad.status != 'REMOVED'",
    ):
        ad = row["adGroupAd"]["ad"]
        rsa = ad.get("responsiveSearchAd", {})
        ads_by_group.setdefault(row["adGroup"]["resourceName"], []).append({
            "id": ad.get("id"),
            "status": row["adGroupAd"].get("status"),
            "final_urls": ad.get("finalUrls", []),
            "path1": rsa.get("path1"),
            "path2": rsa.get("path2"),
            "headlines": [h.get("text") for h in rsa.get("headlines", [])],
            "descriptions": [d.get("text") for d in rsa.get("descriptions", [])],
        })

    return {"groups": groups, "keywords": keywords, "ads": ads_by_group}


def resolve(state: dict[str, Any], merge: dict[str, str]) -> dict[str, Any]:
    """Find the survivor group by either its old or its post-rename name."""
    groups = state["groups"]
    survivor = groups.get(merge["new_name"]) or groups.get(merge["survivor"])
    source = groups.get(merge["source"])
    return {"survivor": survivor, "source": source}


def sanitize(texts: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    out, changes = [], []
    for text in texts:
        replacement = ASSET_REPLACEMENTS.get(text)
        if replacement:
            changes.append({"from": text, "to": replacement})
            out.append(replacement)
        else:
            out.append(text)
    return out, changes


def validate_assets(headlines: list[str], descriptions: list[str], label: str) -> list[str]:
    problems = []
    for h in headlines:
        if len(h) > HEADLINE_MAX:
            problems.append(f"{label}: headline over {HEADLINE_MAX} chars: {h!r} ({len(h)})")
    for d in descriptions:
        if len(d) > DESCRIPTION_MAX:
            problems.append(f"{label}: description over {DESCRIPTION_MAX} chars: {d!r} ({len(d)})")
    if len(set(headlines)) != len(headlines):
        problems.append(f"{label}: duplicate headline after replacement")
    if len(set(descriptions)) != len(descriptions):
        problems.append(f"{label}: duplicate description after replacement")
    if len(headlines) < 3:
        problems.append(f"{label}: fewer than 3 headlines")
    if len(descriptions) < 2:
        problems.append(f"{label}: fewer than 2 descriptions")
    return problems


def build_plan(state: dict[str, Any]) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "customer_id": CID,
        "campaign": CAMPAIGN,
        "merges": [],
        "untouched": [],
        "blockers": [],
    }

    for name in UNTOUCHED:
        g = state["groups"].get(name)
        if not g:
            plan["blockers"].append(f"expected ad group missing: {name}")
            continue
        plan["untouched"].append({
            "name": name,
            "status": g["status"],
            "keywords": len(state["keywords"].get(g["resource_name"], [])),
            "ads": len(state["ads"].get(g["resource_name"], [])),
        })

    for merge in MERGES:
        found = resolve(state, merge)
        survivor, source = found["survivor"], found["source"]
        entry: dict[str, Any] = {"new_name": merge["new_name"]}

        if not survivor:
            plan["blockers"].append(f"survivor ad group missing: {merge['survivor']}")
            plan["merges"].append(entry)
            continue
        if not source:
            plan["blockers"].append(f"source ad group missing: {merge['source']}")
            plan["merges"].append(entry)
            continue

        s_rn, src_rn = survivor["resource_name"], source["resource_name"]
        entry["survivor"] = {"name": survivor["name"], "status": survivor["status"]}
        entry["source"] = {"name": source["name"], "status": source["status"]}

        entry["rename_needed"] = survivor["name"] != merge["new_name"]

        existing = {(k["text"].lower(), k["match_type"])
                    for k in state["keywords"].get(s_rn, [])}
        to_move = [k for k in state["keywords"].get(src_rn, [])
                   if (k["text"].lower(), k["match_type"]) not in existing]
        entry["keywords_in_survivor"] = len(existing)
        entry["keywords_to_copy"] = len(to_move)
        entry["keywords_already_present"] = (
            len(state["keywords"].get(src_rn, [])) - len(to_move)
        )

        survivor_ads = state["ads"].get(s_rn, [])
        survivor_headline_sets = [tuple(a["headlines"]) for a in survivor_ads]
        ads_to_copy, all_changes = [], []
        for ad in state["ads"].get(src_rn, []):
            if ad["status"] == "REMOVED":
                continue
            headlines, h_changes = sanitize(ad["headlines"])
            descriptions, d_changes = sanitize(ad["descriptions"])
            if tuple(headlines) in survivor_headline_sets:
                continue  # already copied on an earlier run
            problems = validate_assets(headlines, descriptions,
                                       f"{merge['new_name']} / ad {ad['id']}")
            plan["blockers"].extend(problems)
            all_changes.extend(h_changes + d_changes)
            ads_to_copy.append({
                "source_ad_id": ad["id"],
                "final_urls": ad["final_urls"],
                "path1": ad["path1"],
                "path2": ad["path2"],
                "headlines": headlines,
                "descriptions": descriptions,
            })
        entry["ads_in_survivor"] = len(survivor_ads)
        entry["ads_to_copy"] = len(ads_to_copy)
        entry["_ads_to_copy"] = ads_to_copy
        entry["_to_move"] = to_move
        entry["_survivor_rn"] = s_rn
        entry["_source_rn"] = src_rn
        entry["copy_replacements"] = all_changes
        entry["pause_source_needed"] = source["status"] != "PAUSED"

        plan["merges"].append(entry)

    # Every replacement must name an approved destination.
    for src, dest in ASSET_REPLACEMENTS.items():
        low = dest.lower()
        if not any(d in low for d in APPROVED_DESTINATIONS):
            plan["blockers"].append(
                f"replacement names no approved destination: {dest!r}")

    plan["ad_groups_before"] = len(state["groups"])
    plan["ad_groups_after_enabled"] = (
        len([g for g in state["groups"].values() if g["status"] == "ENABLED"])
        - len([m for m in plan["merges"] if m.get("pause_source_needed")])
    )
    plan["ok"] = not plan["blockers"]
    return plan


def public(plan: dict[str, Any]) -> dict[str, Any]:
    """Strip internal keys so --plan output stays readable."""
    out = json.loads(json.dumps(plan))
    for merge in out.get("merges", []):
        for key in [k for k in merge if k.startswith("_")]:
            merge.pop(key)
    return out


def apply_changes(env: dict[str, str], token: str, plan: dict[str, Any]) -> dict[str, Any]:
    if not plan["ok"]:
        raise SystemExit("refusing to apply: " + "; ".join(plan["blockers"]))

    backup = pathlib.Path(
        f"/tmp/dct-adgroup-backup-{dt.datetime.now():%Y%m%d-%H%M%S}.json")
    backup.write_text(json.dumps(plan, indent=2))

    result = {"backup": str(backup), "renamed": 0, "keywords_copied": 0,
              "ads_copied": 0, "sources_paused": 0}

    for merge in plan["merges"]:
        if not merge.get("_survivor_rn"):
            continue
        s_rn, src_rn = merge["_survivor_rn"], merge["_source_rn"]

        # 1. copy keywords into the survivor
        ops = [{"create": {
            "adGroup": s_rn,
            "status": "ENABLED",
            "keyword": {"text": k["text"], "matchType": k["match_type"]},
        }} for k in merge["_to_move"]]
        if ops:
            mutate(env, token, "adGroupCriteria", ops)
            result["keywords_copied"] += len(ops)

        # 2. recreate the source RSA in the survivor, sanitised
        ops = []
        for ad in merge["_ads_to_copy"]:
            rsa: dict[str, Any] = {
                "headlines": [{"text": t} for t in ad["headlines"]],
                "descriptions": [{"text": t} for t in ad["descriptions"]],
            }
            if ad["path1"]:
                rsa["path1"] = ad["path1"]
            if ad["path2"]:
                rsa["path2"] = ad["path2"]
            ops.append({"create": {
                "adGroup": s_rn,
                "status": "ENABLED",
                "ad": {"finalUrls": ad["final_urls"], "responsiveSearchAd": rsa},
            }})
        if ops:
            mutate(env, token, "adGroupAds", ops)
            result["ads_copied"] += len(ops)

        # 3. rename the survivor
        if merge.get("rename_needed"):
            mutate(env, token, "adGroups", [{
                "update": {"resourceName": s_rn, "name": merge["new_name"]},
                "updateMask": "name",
            }])
            result["renamed"] += 1

        # 4. pause the source only after its content is safely copied
        if merge.get("pause_source_needed"):
            mutate(env, token, "adGroups", [{
                "update": {"resourceName": src_rn, "status": "PAUSED"},
                "updateMask": "status",
            }])
            result["sources_paused"] += 1

    return result


def verify_state(state: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {"customer_id": CID, "campaign": CAMPAIGN,
                              "groups": [], "problems": []}
    enabled = {n: g for n, g in state["groups"].items() if g["status"] == "ENABLED"}

    for merge in MERGES:
        name = merge["new_name"]
        g = state["groups"].get(name)
        if not g:
            report["problems"].append(f"merged ad group missing: {name}")
            continue
        rn = g["resource_name"]
        kws = state["keywords"].get(rn, [])
        group_ads = state["ads"].get(rn, [])
        report["groups"].append({
            "name": name, "status": g["status"],
            "keywords": len(kws), "ads": len(group_ads),
        })
        if g["status"] != "ENABLED":
            report["problems"].append(f"{name} is not ENABLED")
        if len(group_ads) < 2:
            report["problems"].append(f"{name} has {len(group_ads)} ad(s), expected 2")

        src = state["groups"].get(merge["source"])
        if src and src["status"] == "ENABLED":
            report["problems"].append(f"source still enabled: {merge['source']}")

        # no off-offer copy survived into the merged group
        for ad in group_ads:
            for text in ad["headlines"] + ad["descriptions"]:
                if text in ASSET_REPLACEMENTS:
                    report["problems"].append(
                        f"{name}: off-offer asset still live: {text!r}")

    for name in UNTOUCHED:
        g = state["groups"].get(name)
        if not g:
            report["problems"].append(f"expected ad group missing: {name}")
        else:
            report["groups"].append({
                "name": name, "status": g["status"],
                "keywords": len(state["keywords"].get(g["resource_name"], [])),
                "ads": len(state["ads"].get(g["resource_name"], [])),
            })

    report["enabled_ad_group_count"] = len(enabled)
    report["expected_enabled_ad_group_count"] = len(MERGES) + len(UNTOUCHED)
    if report["enabled_ad_group_count"] != report["expected_enabled_ad_group_count"]:
        report["problems"].append(
            f"expected {report['expected_enabled_ad_group_count']} enabled ad groups, "
            f"found {report['enabled_ad_group_count']}")

    total_kw = sum(len(v) for v in state["keywords"].values())
    report["enabled_keyword_total"] = total_kw
    report["ok"] = not report["problems"]
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="Show planned changes (default)")
    mode.add_argument("--apply", action="store_true", help="Apply the merge")
    mode.add_argument("--verify", action="store_true", help="Verify the merged state")
    args = parser.parse_args()

    env = ads.load_env()
    token = ads.oauth_token(env)
    state = read_state(env, token)

    if args.verify:
        report = verify_state(state)
        print(json.dumps(report, indent=2))
        raise SystemExit(0 if report["ok"] else 1)

    plan = build_plan(state)
    if args.apply:
        print(json.dumps(apply_changes(env, token, plan), indent=2))
        return

    print(json.dumps(public(plan), indent=2))


if __name__ == "__main__":
    main()
