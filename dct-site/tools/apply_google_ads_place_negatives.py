#!/usr/bin/env python3
"""Apply the North American place negatives from dct_place_negatives.py.

Three coordinated changes to the DCT campaign's negative lists:

1. ``DCT | Global Country Negatives`` - remove the bare broad ``Canada`` and
   add the phrase replacements, Canadian destination regions, US states and
   national parks.
2. ``DCT | Global City Negatives`` - create, fill with Canadian and US cities,
   attach to the campaign.
3. ``DCT | Global Search Exclusions`` - add ``short`` (broad). There are no
   short coach tours; "short trip toronto" was a real search term.

Ordering matters. Every addition lands and the new list is attached BEFORE
the bare ``Canada`` is removed, so negative coverage never dips mid-run.

Two blockers stop --apply outright: a candidate term that would block one
of the campaign's own positive keywords, and a bare broad term that is an
approved destination or a known name collision. Both checks run in --plan.

Mutations require the explicit ``--apply`` flag.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import time
from typing import Any

import google_ads_offline as ads
import dct_place_negatives as places

CID = "3639225242"
CAMPAIGN = "customers/3639225242/campaigns/24230451785"

COUNTRY_LIST = "DCT | Global Country Negatives"
CITY_LIST = "DCT | Global City Negatives"
SEARCH_LIST = "DCT | Global Search Exclusions"

SEARCH_ADDITIONS = [("short", "BROAD")]

# Same set the negatives tool protects. Anything here can never be blocked.
PROTECTED_DESTINATIONS = {
    "england", "britain", "scotland", "ireland", "italy", "sicily", "greece",
    "spain", "france", "croatia", "portugal", "scandinavian countries",
    "germany", "switzerland", "netherlands", "holland", "austria", "hungary",
    "czech republic", "prague", "budapest", "turkey", "japan", "egypt",
    "africa", "south africa", "peru",
}


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def key(text: str, match_type: str) -> tuple[str, str]:
    return (text.strip().lower(), match_type)


def search(env: dict[str, str], token: str, query: str) -> list[dict[str, Any]]:
    last: Exception | None = None
    for attempt in range(4):
        try:
            return ads.search(env, token, CID, query)
        except (TimeoutError, OSError) as exc:
            last = exc
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"search failed after retries: {last}")


def mutate(env: dict[str, str], token: str, service: str,
           operations: list[dict[str, Any]]) -> dict[str, Any]:
    if not operations:
        return {"results": []}
    status, payload = ads.request_json(
        env, token, "POST",
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
    sets = {
        row["sharedSet"]["name"]: row["sharedSet"]
        for row in search(
            env, token,
            "SELECT shared_set.resource_name, shared_set.name, shared_set.type, "
            "shared_set.status FROM shared_set "
            "WHERE shared_set.type = 'NEGATIVE_KEYWORDS' "
            "AND shared_set.status != 'REMOVED'",
        )
    }
    criteria: dict[str, dict[tuple[str, str], str]] = {}
    for row in search(
        env, token,
        "SELECT shared_criterion.resource_name, shared_criterion.shared_set, "
        "shared_criterion.keyword.text, shared_criterion.keyword.match_type "
        "FROM shared_criterion",
    ):
        c = row["sharedCriterion"]
        kw = c.get("keyword", {})
        criteria.setdefault(c["sharedSet"], {})[
            key(kw.get("text", ""), kw.get("matchType", ""))
        ] = c["resourceName"]
    attached = {
        row["campaignSharedSet"]["sharedSet"]
        for row in search(
            env, token,
            "SELECT campaign_shared_set.shared_set FROM campaign_shared_set "
            f"WHERE campaign.resource_name = '{CAMPAIGN}' "
            "AND campaign_shared_set.status = 'ENABLED'",
        )
    }
    positives = [
        (row["adGroup"]["name"], row["adGroupCriterion"]["keyword"]["text"],
         row["adGroupCriterion"]["keyword"]["matchType"])
        for row in search(
            env, token,
            "SELECT ad_group.name, ad_group.status, ad_group_criterion.keyword.text, "
            "ad_group_criterion.keyword.match_type FROM ad_group_criterion "
            f"WHERE campaign.resource_name = '{CAMPAIGN}' "
            "AND ad_group_criterion.type = KEYWORD "
            "AND ad_group_criterion.status = 'ENABLED' "
            "AND ad_group.status = 'ENABLED'",
        )
    ]
    return {"sets": sets, "criteria": criteria, "attached": attached,
            "positives": positives}


def blocks(neg_text: str, neg_match: str, query_words: list[str]) -> bool:
    nw = words(neg_text)
    if not nw:
        return False
    if neg_match == "BROAD":
        return all(w in query_words for w in nw)
    n = len(nw)
    return any(query_words[i:i + n] == nw for i in range(len(query_words) - n + 1))


def validate(terms: list[tuple[str, str]], positives) -> list[str]:
    problems = []
    seen = set()
    for text, match in terms:
        k = key(text, match)
        if k in seen:
            problems.append(f"duplicate term in spec: {text!r} [{match}]")
        seen.add(k)
        tw = words(text)
        if match == "BROAD" and len(tw) == 1:
            if tw[0] in places.COLLISION_EXCLUDED:
                problems.append(
                    f"bare broad {text!r} is a known collision: "
                    f"{places.COLLISION_EXCLUDED[tw[0]]}")
        for dest in PROTECTED_DESTINATIONS:
            if text.lower() == dest or (match == "BROAD" and all(w in tw for w in words(dest))):
                problems.append(f"{text!r} [{match}] would block approved destination {dest!r}")
        for ag, ptext, pmatch in positives:
            if blocks(text, match, words(ptext)):
                problems.append(
                    f"{text!r} [{match}] blocks positive keyword {ptext!r} in {ag}")
    return problems


def build_plan(state: dict[str, Any]) -> dict[str, Any]:
    plan: dict[str, Any] = {"customer_id": CID, "campaign": CAMPAIGN, "blockers": []}
    sets, criteria, attached = state["sets"], state["criteria"], state["attached"]

    for name in (COUNTRY_LIST, SEARCH_LIST):
        if name not in sets:
            plan["blockers"].append(f"expected shared set missing: {name}")
        elif sets[name].get("status") != "ENABLED":
            plan["blockers"].append(f"shared set not enabled: {name}")
    if plan["blockers"]:
        plan["ok"] = False
        return plan

    country_rn = sets[COUNTRY_LIST]["resourceName"]
    search_rn = sets[SEARCH_LIST]["resourceName"]
    country_have = criteria.get(country_rn, {})
    search_have = criteria.get(search_rn, {})

    # 1. country list
    canada_key = key(places.CANADA_BROAD_REMOVAL, "BROAD")
    country_add = [t for t in places.country_list_additions()
                   if key(*t) not in country_have]
    plan["country"] = {
        "resource": country_rn,
        "current_count": len(country_have),
        "remove_bare_canada": canada_key in country_have,
        "add_count": len(country_add),
        "already_present": len(places.country_list_additions()) - len(country_add),
        "_add": country_add,
        "_canada_rn": country_have.get(canada_key),
    }

    # 2. city list
    city_set = sets.get(CITY_LIST)
    city_rn = city_set["resourceName"] if city_set else None
    city_have = criteria.get(city_rn, {}) if city_rn else {}
    city_add = [t for t in places.city_list_terms() if key(*t) not in city_have]
    plan["city"] = {
        "resource": city_rn,
        "create_needed": city_set is None,
        "status": city_set.get("status") if city_set else None,
        "current_count": len(city_have),
        "add_count": len(city_add),
        "attach_needed": city_rn not in attached,
        "_add": city_add,
    }
    if city_set and city_set.get("status") != "ENABLED":
        plan["blockers"].append(f"{CITY_LIST} exists but is {city_set.get('status')}")

    # 3. search exclusions
    search_add = [t for t in SEARCH_ADDITIONS if key(*t) not in search_have]
    plan["search"] = {
        "resource": search_rn,
        "current_count": len(search_have),
        "add": [f"{t} [{m}]" for t, m in search_add],
        "_add": search_add,
    }

    # validation against live positives and the collision table
    all_new = country_add + city_add + search_add
    plan["blockers"].extend(validate(all_new, state["positives"]))
    plan["positive_keywords_checked"] = len(state["positives"])
    plan["new_terms_total"] = len(all_new)
    plan["ok"] = not plan["blockers"]
    return plan


def public(plan: dict[str, Any]) -> dict[str, Any]:
    out = json.loads(json.dumps(plan))
    for section in ("country", "city", "search"):
        for k in [k for k in out.get(section, {}) if k.startswith("_")]:
            out[section].pop(k)
    return out


def apply_changes(env: dict[str, str], token: str, plan: dict[str, Any]) -> dict[str, Any]:
    if not plan["ok"]:
        raise SystemExit("refusing to apply: " + "; ".join(plan["blockers"]))

    backup = pathlib.Path(
        f"/private/tmp/dct-place-negatives-{dt.datetime.now(dt.UTC):%Y%m%d-%H%M%S}.json")
    backup.write_text(json.dumps(plan, indent=2))
    result: dict[str, Any] = {"backup": str(backup)}

    def add_terms(rn: str, terms: list[tuple[str, str]]) -> int:
        mutate(env, token, "sharedCriteria", [{
            "create": {"sharedSet": rn, "keyword": {"text": t, "matchType": m}}
        } for t, m in terms])
        return len(terms)

    # 2. city list first: create, fill, attach
    city = plan["city"]
    city_rn = city["resource"]
    if city["create_needed"]:
        payload = mutate(env, token, "sharedSets", [{
            "create": {"name": CITY_LIST, "type": "NEGATIVE_KEYWORDS"}
        }])
        city_rn = payload["results"][0]["resourceName"]
        result["city_list_created"] = city_rn
    result["city_terms_added"] = add_terms(city_rn, city["_add"])
    if city["attach_needed"]:
        mutate(env, token, "campaignSharedSets", [{
            "create": {"campaign": CAMPAIGN, "sharedSet": city_rn}
        }])
        result["city_list_attached"] = True

    # 1. country additions
    country = plan["country"]
    result["country_terms_added"] = add_terms(country["resource"], country["_add"])

    # 3. search exclusions
    result["search_terms_added"] = add_terms(plan["search"]["resource"], plan["search"]["_add"])

    # 1b. only now remove the bare Canada - replacements are all live
    if country["remove_bare_canada"] and country["_canada_rn"]:
        mutate(env, token, "sharedCriteria", [{"remove": country["_canada_rn"]}])
        result["bare_canada_removed"] = True

    return result


def verify_state(state: dict[str, Any]) -> dict[str, Any]:
    report: dict[str, Any] = {"customer_id": CID, "campaign": CAMPAIGN, "problems": []}
    sets, criteria, attached = state["sets"], state["criteria"], state["attached"]

    for name in (COUNTRY_LIST, CITY_LIST, SEARCH_LIST):
        s = sets.get(name)
        if not s:
            report["problems"].append(f"missing: {name}")
            continue
        rn = s["resourceName"]
        have = criteria.get(rn, {})
        report[name] = {
            "status": s.get("status"),
            "criteria_count": len(have),
            "attached": rn in attached,
        }
        if s.get("status") != "ENABLED":
            report["problems"].append(f"{name} not ENABLED")
        if rn not in attached:
            report["problems"].append(f"{name} not attached to campaign")

    if COUNTRY_LIST in sets:
        have = criteria.get(sets[COUNTRY_LIST]["resourceName"], {})
        if key(places.CANADA_BROAD_REMOVAL, "BROAD") in have:
            report["problems"].append("bare broad 'Canada' still present in country list")
        missing = [f"{t} [{m}]" for t, m in places.country_list_additions()
                   if key(t, m) not in have]
        if missing:
            report["problems"].append(f"country list missing {len(missing)} terms: {missing[:5]}")
    if CITY_LIST in sets:
        have = criteria.get(sets[CITY_LIST]["resourceName"], {})
        missing = [f"{t} [{m}]" for t, m in places.city_list_terms()
                   if key(t, m) not in have]
        if missing:
            report["problems"].append(f"city list missing {len(missing)} terms: {missing[:5]}")
    if SEARCH_LIST in sets:
        have = criteria.get(sets[SEARCH_LIST]["resourceName"], {})
        for t, m in SEARCH_ADDITIONS:
            if key(t, m) not in have:
                report["problems"].append(f"search list missing {t!r} [{m}]")

    # the live lists must not block any live positive keyword
    conflicts = []
    for name in (COUNTRY_LIST, CITY_LIST, SEARCH_LIST):
        if name not in sets:
            continue
        for (text, match) in criteria.get(sets[name]["resourceName"], {}):
            for ag, ptext, pmatch in state["positives"]:
                if blocks(text, match, words(ptext)):
                    conflicts.append(f"{name}: {text!r} [{match}] blocks {ptext!r} ({ag})")
    report["positive_keyword_conflicts"] = conflicts
    if conflicts:
        report["problems"].append(f"{len(conflicts)} negative(s) block live positive keywords")

    report["attached_negative_list_count"] = len(attached)
    report["ok"] = not report["problems"]
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="Show planned changes (default)")
    mode.add_argument("--apply", action="store_true", help="Apply the changes")
    mode.add_argument("--verify", action="store_true", help="Verify the three-list state")
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
