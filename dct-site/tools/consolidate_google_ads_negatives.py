#!/usr/bin/env python3
"""Move DCT campaign-level negatives into two reusable shared lists.

The country/destination list already exists. This script creates (or repairs)
the search-exclusion list, copies the campaign-level negatives into it, links
both lists to the DCT campaign, and only then removes the loose campaign
criteria. Mutations require the explicit ``--apply`` flag.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
from typing import Any

import google_ads_offline as ads

CID = "3639225242"
CAMPAIGN = "customers/3639225242/campaigns/24230451785"
COUNTRY_LIST_NAME = "DCT | Global Country Negatives"
SEARCH_LIST_NAME = "DCT | Global Search Exclusions"
# Added 11 Sep 2026 by apply_google_ads_place_negatives.py. This tool does not
# manage its contents but must recognise it, or it refuses to run.
CITY_LIST_NAME = "DCT | Global City Negatives"
COMPETITOR_LIST_NAME = "DCT | Competitor Tour Operators"  # added 12 Sep 2026
KNOWN_LIST_NAMES = {COUNTRY_LIST_NAME, SEARCH_LIST_NAME, CITY_LIST_NAME, COMPETITOR_LIST_NAME}

PROTECTED_DESTINATIONS = {
    "england",
    "britain",
    "scotland",
    "ireland",
    "italy",
    "sicily",
    "greece",
    "spain",
    "france",
    "croatia",
    "portugal",
    "scandinavian countries",
    "germany",
    "switzerland",
    "netherlands",
    "holland",
    "austria",
    "hungary",
    "czech republic",
    "prague",
    "budapest",
    "turkey",
    "japan",
    "egypt",
    "africa",
    "south africa",
    "peru",
}


def search(env: dict[str, str], token: str, query: str) -> list[dict[str, Any]]:
    return ads.search(env, token, CID, query)


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
        {
            "operations": operations,
            "partialFailure": False,
            "responseContentType": "MUTABLE_RESOURCE",
        },
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
    shared_sets = search(
        env,
        token,
        "SELECT shared_set.resource_name, shared_set.id, shared_set.name, "
        "shared_set.type, shared_set.status FROM shared_set "
        "ORDER BY shared_set.name",
    )
    shared_criteria = search(
        env,
        token,
        "SELECT shared_criterion.resource_name, shared_criterion.shared_set, "
        "shared_criterion.keyword.text, shared_criterion.keyword.match_type "
        "FROM shared_criterion",
    )
    campaign_shared_sets = search(
        env,
        token,
        "SELECT campaign_shared_set.resource_name, "
        "campaign_shared_set.campaign, campaign_shared_set.shared_set "
        f"FROM campaign_shared_set WHERE campaign_shared_set.campaign = '{CAMPAIGN}'",
    )
    campaign_negatives = search(
        env,
        token,
        "SELECT campaign_criterion.resource_name, "
        "campaign_criterion.keyword.text, campaign_criterion.keyword.match_type "
        "FROM campaign_criterion "
        f"WHERE campaign_criterion.campaign = '{CAMPAIGN}' "
        "AND campaign_criterion.negative = TRUE",
    )
    return {
        "shared_sets": [row.get("sharedSet", {}) for row in shared_sets],
        "shared_criteria": [row.get("sharedCriterion", {}) for row in shared_criteria],
        "campaign_shared_sets": [
            row.get("campaignSharedSet", {}) for row in campaign_shared_sets
        ],
        "campaign_negatives": [
            row.get("campaignCriterion", {}) for row in campaign_negatives
        ],
    }


def normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def negative_shared_sets(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in state["shared_sets"]
        if item.get("type") == "NEGATIVE_KEYWORDS"
    ]


def list_by_name(state: dict[str, Any], name: str) -> dict[str, Any] | None:
    matches = [item for item in negative_shared_sets(state) if item.get("name") == name]
    if len(matches) > 1:
        raise RuntimeError(f"More than one negative shared set is named {name!r}")
    return matches[0] if matches else None


def criteria_for_set(state: dict[str, Any], resource: str) -> list[dict[str, Any]]:
    return [
        item
        for item in state["shared_criteria"]
        if item.get("sharedSet") == resource and item.get("keyword")
    ]


def criterion_key(item: dict[str, Any]) -> tuple[str, str]:
    keyword = item.get("keyword", {})
    return (
        normalize(keyword.get("text", "")),
        keyword.get("matchType", ""),
    )


def expected_campaign_negatives(state: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    expected: dict[tuple[str, str], dict[str, Any]] = {}
    for item in state["campaign_negatives"]:
        key = criterion_key(item)
        if key[0] and key[1]:
            expected.setdefault(key, item)
    return expected


def validate_preconditions(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    country = list_by_name(state, COUNTRY_LIST_NAME)
    if not country:
        raise RuntimeError(f"Required shared list is missing: {COUNTRY_LIST_NAME}")
    if country.get("status") != "ENABLED":
        raise RuntimeError(f"Required shared list is not enabled: {COUNTRY_LIST_NAME}")

    unexpected = [
        item
        for item in negative_shared_sets(state)
        if item.get("name") not in KNOWN_LIST_NAMES
    ]
    if unexpected:
        names = ", ".join(item.get("name", "(unnamed)") for item in unexpected)
        raise RuntimeError(f"Unexpected negative shared list(s); refusing to delete anything: {names}")

    negative_resources = {
        item.get("resourceName") for item in negative_shared_sets(state)
    }
    attached_resources = {
        item.get("sharedSet")
        for item in state["campaign_shared_sets"]
        if item.get("sharedSet")
    }
    unexpected_attached = attached_resources - negative_resources
    if unexpected_attached:
        raise RuntimeError(
            "Campaign has an attached shared set that was not returned as a negative list; "
            "refusing to alter attachments"
        )

    overlaps = sorted(
        normalize(item.get("keyword", {}).get("text", ""))
        for item in criteria_for_set(state, country["resourceName"])
        if normalize(item.get("keyword", {}).get("text", "")) in PROTECTED_DESTINATIONS
    )
    if overlaps:
        raise RuntimeError(
            "Approved destinations appear in the country negative list: "
            + ", ".join(overlaps)
        )

    return country, list_by_name(state, SEARCH_LIST_NAME)


def summary(state: dict[str, Any], expected: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    country, search_list = validate_preconditions(state)
    lists = []
    for item in negative_shared_sets(state):
        lists.append({
            "name": item.get("name"),
            "resource_name": item.get("resourceName"),
            "status": item.get("status"),
            "criteria_count": len(criteria_for_set(state, item.get("resourceName", ""))),
            "attached_to_campaign": any(
                link.get("sharedSet") == item.get("resourceName")
                for link in state["campaign_shared_sets"]
            ),
        })

    existing_search_keys = {
        criterion_key(item)
        for item in criteria_for_set(state, search_list.get("resourceName", ""))
    } if search_list else set()
    return {
        "customer_id": CID,
        "campaign": CAMPAIGN,
        "negative_shared_list_count_now": len(negative_shared_sets(state)),
        "negative_shared_lists": lists,
        "campaign_negative_count_now": len(state["campaign_negatives"]),
        "campaign_negative_unique_count_now": len(expected),
        "search_list_will_be_created": search_list is None,
        "search_terms_missing_before_apply": len(set(expected) - existing_search_keys),
        "campaign_negative_criteria_to_remove_after_coverage": len(state["campaign_negatives"]),
        "protected_destination_overlap": [],
        "target_after_apply": {
            "negative_shared_list_count": len(KNOWN_LIST_NAMES),
            "campaign_negative_count": 0,
            "both_lists_attached": True,
        },
        "country_list": {
            "name": country.get("name"),
            "criteria_count": len(criteria_for_set(state, country["resourceName"])),
        },
    }


def remove_term(
    env: dict[str, str], token: str, state: dict[str, Any], text: str
) -> dict[str, Any]:
    """Remove one term from the search-exclusion list.

    Only the search-exclusion list is touched. The country list holds the
    destination policy and is never edited here, so a typo cannot silently
    unblock a non-approved destination.
    """
    country, search_list = validate_preconditions(state)
    if not search_list:
        raise RuntimeError(f"missing shared set: {SEARCH_LIST_NAME}")
    search_resource = search_list["resourceName"]
    country_resource = country["resourceName"] if country else None

    wanted = text.strip().lower()
    matches = [
        item for item in state["shared_criteria"]
        if item.get("sharedSet") == search_resource
        and item.get("keyword", {}).get("text", "").strip().lower() == wanted
    ]
    in_country = [
        item for item in state["shared_criteria"]
        if country_resource and item.get("sharedSet") == country_resource
        and item.get("keyword", {}).get("text", "").strip().lower() == wanted
    ]
    if in_country:
        raise RuntimeError(
            f"{text!r} is in {COUNTRY_LIST_NAME}, not the search list. "
            "Destination policy terms are not removable through this flag."
        )
    if not matches:
        return {"term": text, "removed": 0, "note": "term not present, nothing to do"}

    backup_path = pathlib.Path("/private/tmp") / (
        "dct-negative-removal-" + dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S") + ".json"
    )
    backup_path.write_text(json.dumps(matches, indent=2), encoding="utf-8")

    mutate(
        env, token, "sharedCriteria",
        [{"remove": item["resourceName"]} for item in matches],
    )
    return {
        "term": text,
        "list": SEARCH_LIST_NAME,
        "removed": len(matches),
        "match_types": [m.get("keyword", {}).get("matchType") for m in matches],
        "backup": str(backup_path),
    }


def verify_state(
    state: dict[str, Any],
    expected: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    country, search_list = validate_preconditions(state)
    neg_sets = negative_shared_sets(state)
    names = {item.get("name") for item in neg_sets}
    attached = {
        item.get("sharedSet")
        for item in state["campaign_shared_sets"]
        if item.get("sharedSet")
    }
    target_resources = {
        item.get("resourceName")
        for item in neg_sets
        if item.get("name") in KNOWN_LIST_NAMES
    }
    search_criteria = criteria_for_set(state, search_list["resourceName"]) if search_list else []
    search_keys = {criterion_key(item) for item in search_criteria}
    protected_overlap = sorted(
        normalize(item.get("keyword", {}).get("text", ""))
        for item in criteria_for_set(state, country["resourceName"])
        if normalize(item.get("keyword", {}).get("text", "")) in PROTECTED_DESTINATIONS
    )
    expected_missing = sorted(set(expected or {}) - search_keys)
    report = {
        "customer_id": CID,
        "campaign": CAMPAIGN,
        "negative_shared_list_count": len(neg_sets),
        "negative_shared_lists": [
            {
                "name": item.get("name"),
                "resource_name": item.get("resourceName"),
                "status": item.get("status"),
                "criteria_count": len(criteria_for_set(state, item.get("resourceName", ""))),
                "attached_to_campaign": item.get("resourceName") in attached,
            }
            for item in neg_sets
        ],
        "attached_negative_shared_list_count": len(attached & target_resources),
        "attached_negative_shared_lists": sorted(attached & target_resources),
        "campaign_negative_count": len(state["campaign_negatives"]),
        "search_list_criteria_count": len(search_criteria),
        "migrated_terms_missing_from_search_list": expected_missing,
        "protected_destination_overlap": protected_overlap,
    }
    report["ok"] = (
        names == KNOWN_LIST_NAMES
        and len(neg_sets) == len(KNOWN_LIST_NAMES)
        and all(item.get("status") == "ENABLED" for item in neg_sets)
        and attached == target_resources
        and len(state["campaign_negatives"]) == 0
        and not expected_missing
        and not protected_overlap
    )
    return report


def create_search_list(env: dict[str, str], token: str) -> str:
    payload = mutate(
        env,
        token,
        "sharedSets",
        [{
            "create": {
                "name": SEARCH_LIST_NAME,
                "type": "NEGATIVE_KEYWORDS",
                "status": "ENABLED",
            }
        }],
    )
    return payload["results"][0]["resourceName"]


def apply_changes(env: dict[str, str], token: str, state: dict[str, Any]) -> dict[str, Any]:
    country, search_list = validate_preconditions(state)
    expected = expected_campaign_negatives(state)
    backup_path = pathlib.Path("/private/tmp") / (
        "dct-negative-backup-" + dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S") + ".json"
    )
    backup_path.write_text(
        json.dumps({
            "campaign": CAMPAIGN,
            "campaign_negatives": state["campaign_negatives"],
            "campaign_shared_sets": state["campaign_shared_sets"],
        }, indent=2),
        encoding="utf-8",
    )

    created_list = False
    if search_list:
        if search_list.get("status") != "ENABLED":
            raise RuntimeError(f"Search exclusion list is not enabled: {SEARCH_LIST_NAME}")
        search_resource = search_list["resourceName"]
    else:
        search_resource = create_search_list(env, token)
        created_list = True

    existing_keys = {
        criterion_key(item)
        for item in criteria_for_set(state, search_resource)
    }
    missing = [
        item
        for key, item in expected.items()
        if key not in existing_keys
    ]
    if missing:
        mutate(
            env,
            token,
            "sharedCriteria",
            [{
                "create": {
                    "sharedSet": search_resource,
                    "keyword": {
                        "text": item["keyword"]["text"],
                        "matchType": item["keyword"]["matchType"],
                    },
                }
            } for item in missing],
        )

    state_after_list = read_state(env, token)
    country_after_list, search_after_list = validate_preconditions(state_after_list)
    if not search_after_list:
        raise RuntimeError("Search exclusion list disappeared after creation")
    search_keys_after = {
        criterion_key(item)
        for item in criteria_for_set(state_after_list, search_after_list["resourceName"])
    }
    missing_after = sorted(set(expected) - search_keys_after)
    if missing_after:
        raise RuntimeError(
            f"Refusing to remove campaign negatives; {len(missing_after)} terms were not copied"
        )

    attached = {
        item.get("sharedSet") for item in state_after_list["campaign_shared_sets"]
    }
    attach_operations = [
        {"create": {"campaign": CAMPAIGN, "sharedSet": resource}}
        for resource in (country_after_list["resourceName"], search_after_list["resourceName"])
        if resource not in attached
    ]
    if attach_operations:
        mutate(env, token, "campaignSharedSets", attach_operations)

    if state_after_list["campaign_negatives"]:
        mutate(
            env,
            token,
            "campaignCriteria",
            [{"remove": item["resourceName"]} for item in state_after_list["campaign_negatives"]],
        )

    final_state = read_state(env, token)
    report = verify_state(final_state, expected)
    report["created_search_list"] = created_list
    report["copied_campaign_negative_count"] = len(expected)
    report["backup_path"] = str(backup_path)
    if not report["ok"]:
        raise RuntimeError("Post-mutation verification failed: " + json.dumps(report, separators=(",", ":")))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="Show the planned changes (default)")
    mode.add_argument("--apply", action="store_true", help="Apply the consolidation")
    mode.add_argument("--verify", action="store_true", help="Verify the final two-list state")
    mode.add_argument(
        "--remove-term",
        metavar="TEXT",
        help="Remove one term from the search-exclusion list",
    )
    args = parser.parse_args()

    env = ads.load_env()
    token = ads.oauth_token(env)
    state = read_state(env, token)
    expected = expected_campaign_negatives(state)

    if args.verify:
        report = verify_state(state, expected)
        print(json.dumps(report, indent=2))
        raise SystemExit(0 if report["ok"] else 1)
    if args.remove_term:
        print(json.dumps(remove_term(env, token, state, args.remove_term), indent=2))
        return
    if args.apply:
        print(json.dumps(apply_changes(env, token, state), indent=2))
        return

    print(json.dumps(summary(state, expected), indent=2))


if __name__ == "__main__":
    main()
