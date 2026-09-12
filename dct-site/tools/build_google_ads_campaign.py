#!/usr/bin/env python3
"""Idempotently build the paused DCT Canada Search campaign."""
from __future__ import annotations

import argparse
import json
import time
from typing import Any

import google_ads_offline as ads

CID = "3639225242"
CAMPAIGN = "DCT | Search | Canada | Operators | 2026"
BUDGET = "DCT | Search | Canada | 150 CAD per day"
BASE = "https://book.discountcoachtours.ca"

# Account-level negative lists, attached to the campaign rather than held as
# campaign criteria. Managed by tools/consolidate_google_ads_negatives.py.
NEGATIVE_SHARED_SETS = [
    "DCT | Global Country Negatives",
    "DCT | Global Search Exclusions",
    "DCT | Global City Negatives",  # added 11 Sep 2026
    "DCT | Competitor Tour Operators",  # added 12 Sep 2026
]


def pairs(terms: list[str]) -> list[tuple[str, str]]:
    return [(term, match) for term in terms for match in ("EXACT", "PHRASE")]


COMMON = [
    "Guided Tours Made Easier",
    "Coach Tour Specialists",
    "No-Obligation Enquiry",
    "Tell Us Your Travel Plans",
    "Compare Current Itineraries",
    "Personal Tour Recommendations",
    "TICO Registered Agency",
    "Request Tour Options Today",
]


def desc(operator: str) -> list[str]:
    return [
        f"Tell us your plans. We'll compare current {operator} guided tour options.",
        "Get independent help choosing a guided coach tour that fits your plans and travel style.",
        "Ask a coach tour specialist for suitable itineraries. Your enquiry is obligation-free.",
        f"Explore {operator} journeys with planning help from Discount Coach Tours.",
    ]


OPERATOR_SPECS = [
    {
        "short": "Trafalgar",
        "operator": "Trafalgar",
        "slug": "trafalgar-tours.html",
        "brand": [
            "trafalgar tours", "trafalgar vacations", "trafalgar coach tours",
            "trafalgar guided tours", "trafalgar tour packages", "trafalgar travel",
        ],
        "dest": [
            "trafalgar europe tours", "trafalgar italy tours", "trafalgar ireland tours",
            "trafalgar scotland tours", "trafalgar spain tours", "trafalgar greece tours",
        ],
        "brand_heads": [
            "Trafalgar Tours Canada", "Explore Trafalgar Tours",
            "Find Your Trafalgar Tour", "Trafalgar Tour Options",
        ],
        "dest_heads": [
            "Trafalgar Europe Tours", "Trafalgar Italy Tours",
            "Trafalgar Ireland Tours", "Trafalgar Scotland Tours",
            "Find Your Trafalgar Tour",
        ],
    },
    {
        "short": "Insight",
        "operator": "Insight Vacations",
        "slug": "insight-vacations.html",
        "brand": [
            "insight vacations", "insight tours",
            "insight guided tours", "insight coach tours",
            "insight travel", "insight vacation packages",
        ],
        "dest": [
            "insight vacations europe", "insight vacations italy",
            "insight vacations ireland", "insight vacations england",
            "insight vacations scotland", "insight vacations spain",
        ],
        "brand_heads": [
            "Insight Vacations Canada", "Explore Insight Vacations",
            "Find Your Insight Tour", "Insight Guided Tour Options",
            "Premium Guided Tours",
        ],
        "dest_heads": [
            "Insight Europe Tours", "Insight Italy Tours", "Insight Ireland Tours",
            "Insight Scotland Tours", "Find Your Insight Tour", "Premium Guided Tours",
        ],
    },
    {
        "short": "Globus",
        "operator": "Globus",
        "slug": "globus-journeys.html",
        "brand": [
            "globus tours", "globus journeys",
            "globus guided tours", "globus coach tours", "globus travel",
            "globus tour packages", "globus vacations",
        ],
        "dest": [
            "globus europe tours", "globus italy tours", "globus ireland tours",
            "globus scotland tours", "globus greece tours",
            "globus france tours",
        ],
        "brand_heads": [
            "Globus Tours Canada", "Explore Globus Journeys",
            "Find Your Globus Tour", "Globus Guided Tour Options",
        ],
        "dest_heads": [
            "Globus Europe Tours", "Globus Italy Tours", "Globus Ireland Tours",
            "Globus Scotland Tours", "Find Your Globus Tour",
        ],
    },
    {
        "short": "Cosmos",
        "operator": "Cosmos",
        "slug": "cosmos-tours.html",
        "brand": [
            "cosmos tours", "cosmos vacations",
            "cosmos guided tours", "cosmos coach tours", "cosmos travel",
            "cosmos tour packages",
        ],
        "dest": [
            "cosmos europe tours", "cosmos italy tours", "cosmos ireland tours",
            "cosmos scotland tours", "cosmos spain tours", "cosmos france tours",
            "cosmos greece tours",
        ],
        "brand_heads": [
            "Cosmos Tours Canada", "Explore Cosmos Tours", "Find Your Cosmos Tour",
            "Smart-Value Guided Tours",
        ],
        "dest_heads": [
            "Cosmos Europe Tours", "Cosmos Italy Tours", "Cosmos Ireland Tours",
            "Cosmos Scotland Tours", "Find Your Cosmos Tour",
            "Smart-Value Guided Tours",
        ],
    },
]


GENERIC_DESTINATIONS = [
    "Europe", "England", "Britain", "Scotland", "Ireland", "Italy", "Sicily",
    "Greece", "Spain", "France", "Croatia", "Portugal", "Scandinavian Countries",
    "Germany", "Switzerland", "Netherlands", "Holland", "Austria", "Hungary",
    "Czech Republic", "Prague", "Budapest", "Turkey", "Japan", "Egypt", "Africa",
    "South Africa", "Peru",
]


def generic_destination_broad_terms() -> list[tuple[str, str]]:
    return [
        (f"{destination} {suffix}", "BROAD")
        for destination in GENERIC_DESTINATIONS
        for suffix in ("coach tours", "bus tours")
    ]


def build_groups() -> list[dict[str, Any]]:
    """One ad group per operator.

    The paired "Brand & Tours" / "Destinations" groups were merged on
    10 September 2026 (see tools/consolidate_google_ads_ad_groups.py). Both
    keyword sets and both RSAs now live in a single group per operator so a
    small daily budget is not split eight ways. Each group keeps two ads,
    distinguished by path2, so the destination-led creative still runs.
    """
    groups: list[dict[str, Any]] = []
    for spec in OPERATOR_SPECS:
        url = f"{BASE}/{spec['slug']}"
        path = spec["short"].lower()
        groups.append({
            "name": f"DCT | {spec['short']}",
            "status": "ENABLED",
            "url": url,
            "keywords": pairs(spec["brand"]) + pairs(spec["dest"]),
            "ads": [
                {
                    "path1": path,
                    "path2": "tour-options",
                    "headlines": spec["brand_heads"] + COMMON,
                    "descriptions": desc(spec["operator"]),
                },
                {
                    "path1": path,
                    "path2": "destinations",
                    "headlines": spec["dest_heads"] + COMMON,
                    "descriptions": desc(spec["operator"]),
                },
            ],
        })
    groups.extend([
        {
            "name": "DCT | Brand",
            "status": "ENABLED",
            "url": f"{BASE}/",
            "keywords": pairs([
                "discount coach tours",
                "discountcoachtours",
            ]),
            "ads": [{
                "path1": "coach-tours",
                "path2": "tour-options",
                "headlines": [
                    "Discount Coach Tours", "Compare Trusted Tour Brands",
                    "Guided Holiday Planning", "Find Your Best-Fit Tour",
                    "Travel Planning Made Easier", *COMMON,
                ],
                "descriptions": [
                    "Compare guided holidays from trusted tour operators with personal planning help.",
                    "Tell us your destination, dates and budget. We'll suggest suitable coach tour options.",
                    "Ask a coach tour specialist for current itineraries. Your enquiry is obligation-free.",
                    "Explore Trafalgar, Globus, Insight and Cosmos tours with a TICO registered agency.",
                ],
            }],
        },
        {
            # Live name is "... | HOLD". Keep it in sync or the builder will
            # create a second, duplicate generic group alongside the real one.
            "name": "DCT | Generic Coach Tours | HOLD",
            "status": "ENABLED",
            "url": f"{BASE}/",
            "keywords": generic_destination_broad_terms(),
            "ads": [{
                "path1": "coach-tours",
                "path2": "compare",
                "headlines": [
                    "Guided Coach Tours Canada", "Compare Coach Tour Options",
                    "Find Your Best-Fit Tour", "Trusted Tour Operators",
                    "Guided Holiday Planning", "Travel Planning Made Easier", *COMMON,
                ],
                "descriptions": [
                    "Compare guided holidays from trusted tour operators with personal planning help.",
                    "Tell us your destination, dates and budget. We'll suggest suitable coach tour options.",
                    "Ask a coach tour specialist for current itineraries. Your enquiry is obligation-free.",
                    "Explore Trafalgar, Globus, Insight and Cosmos tours with a TICO registered agency.",
                ],
            }],
        },
    ])
    return groups


GROUPS = build_groups()

SITELINKS = [
    ("Trafalgar Tours", f"{BASE}/trafalgar-tours.html",
     "Explore Trafalgar journeys", "Request suitable tour options"),
    ("Globus Journeys", f"{BASE}/globus-journeys.html",
     "Explore Globus journeys", "Request suitable tour options"),
    ("Insight Vacations", f"{BASE}/insight-vacations.html",
     "Explore premium guided tours", "Request suitable tour options"),
    ("Cosmos Tours", f"{BASE}/cosmos-tours.html",
     "Explore value-focused tours", "Request suitable tour options"),
]

CALLOUTS = [
    "TICO Registered", "No-Obligation Enquiry", "Coach Tour Specialists",
    "Personal Recommendations", "Trusted Tour Operators", "Canada-Based Team",
]


def validate_plan() -> None:
    names = [group["name"] for group in GROUPS]
    assert len(names) == len(set(names)), "Duplicate ad group names"
    for group in GROUPS:
        assert group["ads"], group["name"]
        paths = [ad["path2"] for ad in group["ads"]]
        assert len(paths) == len(set(paths)), f"{group['name']}: duplicate path2"
        for ad in group["ads"]:
            headlines = ad["headlines"]
            descriptions = ad["descriptions"]
            assert 3 <= len(headlines) <= 15, group["name"]
            assert len(headlines) == len(set(headlines)), group["name"]
            assert 2 <= len(descriptions) <= 4, group["name"]
            assert all(len(text) <= 30 for text in headlines), [
                (text, len(text)) for text in headlines if len(text) > 30
            ]
            assert all(len(text) <= 90 for text in descriptions), [
                (text, len(text)) for text in descriptions if len(text) > 90
            ]
            assert len(ad["path1"]) <= 15 and len(ad["path2"]) <= 15
        keys = {(text.lower(), match) for text, match in group["keywords"]}
        assert len(keys) == len(group["keywords"]), group["name"]
    for text, _, description1, description2 in SITELINKS:
        assert len(text) <= 25
        assert len(description1) <= 35 and len(description2) <= 35
    assert all(len(text) <= 25 for text in CALLOUTS)


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
        raise RuntimeError(
            f"{service} mutate failed ({status}): {message} "
            f"{json.dumps(payload, separators=(',', ':'))}"
        )
    return payload


def search(env: dict[str, str], token: str, query: str) -> list[dict[str, Any]]:
    """Read query with retries.

    The asset and ad queries are heavy enough that the API intermittently
    times out. Without a retry a --verify run dies mid-snapshot and prints
    nothing to stdout, which reads like an empty account.
    """
    last: Exception | None = None
    for attempt in range(4):
        try:
            return ads.search(env, token, CID, query)
        except (TimeoutError, OSError) as exc:
            last = exc
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"search failed after retries: {last}")


def ensure_budget(env: dict[str, str], token: str) -> str:
    rows = search(
        env,
        token,
        "SELECT campaign_budget.id, campaign_budget.name, "
        "campaign_budget.resource_name, campaign_budget.amount_micros "
        f"FROM campaign_budget WHERE campaign_budget.name = '{BUDGET}'",
    )
    if rows:
        item = rows[0]["campaignBudget"]
        if int(item.get("amountMicros", 0)) != 150_000_000:
            raise RuntimeError("Existing DCT budget does not equal CAD 150/day")
        return item["resourceName"]
    payload = mutate(
        env,
        token,
        "campaignBudgets",
        [{"create": {
            "name": BUDGET,
            "amountMicros": "150000000",
            "deliveryMethod": "STANDARD",
            "explicitlyShared": False,
        }}],
    )
    return payload["results"][0]["resourceName"]


def ensure_campaign(env: dict[str, str], token: str, budget: str) -> str:
    rows = search(
        env,
        token,
        "SELECT campaign.id, campaign.name, campaign.resource_name, campaign.status "
        f"FROM campaign WHERE campaign.name = '{CAMPAIGN}'",
    )
    if rows:
        item = rows[0]["campaign"]
        if item.get("status") != "PAUSED":
            raise RuntimeError(
                f"Refusing to alter same-named campaign in {item.get('status')} state"
            )
        return item["resourceName"]
    payload = mutate(
        env,
        token,
        "campaigns",
        [{"create": {
            "name": CAMPAIGN,
            "status": "PAUSED",
            "campaignBudget": budget,
            "advertisingChannelType": "SEARCH",
            "containsEuPoliticalAdvertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
            "networkSettings": {
                "targetGoogleSearch": True,
                "targetSearchNetwork": False,
                "targetContentNetwork": False,
                "targetPartnerSearchNetwork": False,
            },
            "geoTargetTypeSetting": {
                "positiveGeoTargetType": "PRESENCE",
                "negativeGeoTargetType": "PRESENCE",
            },
            "targetSpend": {"cpcBidCeilingMicros": "5000000"},
        }}],
    )
    return payload["results"][0]["resourceName"]


def ensure_campaign_criteria(
    env: dict[str, str], token: str, campaign: str
) -> int:
    rows = search(
        env,
        token,
        "SELECT campaign_criterion.negative, campaign_criterion.keyword.text, "
        "campaign_criterion.keyword.match_type, "
        "campaign_criterion.location.geo_target_constant, "
        "campaign_criterion.language.language_constant "
        f"FROM campaign_criterion WHERE campaign_criterion.campaign = '{campaign}'",
    )
    locations = {
        row.get("campaignCriterion", {}).get("location", {}).get("geoTargetConstant")
        for row in rows
    }
    languages = {
        row.get("campaignCriterion", {}).get("language", {}).get("languageConstant")
        for row in rows
    }
    operations: list[dict[str, Any]] = []
    if "geoTargetConstants/2124" not in locations:
        operations.append({"create": {
            "campaign": campaign,
            "location": {"geoTargetConstant": "geoTargetConstants/2124"},
        }})
    if "languageConstants/1000" not in languages:
        operations.append({"create": {
            "campaign": campaign,
            "language": {"languageConstant": "languageConstants/1000"},
        }})
    # Negative keywords are account-level shared lists. Keeping them out of
    # this campaign builder prevents a later rebuild from recreating loose
    # campaign criteria after consolidation.
    mutate(env, token, "campaignCriteria", operations)
    return len(operations)


def ensure_ad_groups(
    env: dict[str, str], token: str, campaign: str
) -> dict[str, str]:
    rows = search(
        env,
        token,
        "SELECT ad_group.id, ad_group.name, ad_group.resource_name, ad_group.status "
        f"FROM ad_group WHERE campaign.resource_name = '{campaign}'",
    )
    existing = {
        row["adGroup"]["name"]: row["adGroup"]["resourceName"]
        for row in rows
        if row.get("adGroup", {}).get("name")
    }
    missing = [group for group in GROUPS if group["name"] not in existing]
    payload = mutate(
        env,
        token,
        "adGroups",
        [{"create": {
            "name": group["name"],
            "campaign": campaign,
            "status": group["status"],
            "type": "SEARCH_STANDARD",
            "cpcBidMicros": "3000000",
        }} for group in missing],
    )
    for group, result in zip(missing, payload.get("results", [])):
        existing[group["name"]] = result["resourceName"]
    return existing


def ensure_keywords(
    env: dict[str, str], token: str, ad_groups: dict[str, str]
) -> int:
    rows = search(
        env,
        token,
        "SELECT ad_group.resource_name, ad_group_criterion.keyword.text, "
        "ad_group_criterion.keyword.match_type FROM keyword_view "
        f"WHERE campaign.name = '{CAMPAIGN}'",
    )
    existing = {
        (
            row.get("adGroup", {}).get("resourceName"),
            row.get("adGroupCriterion", {}).get("keyword", {}).get("text", "").lower(),
            row.get("adGroupCriterion", {}).get("keyword", {}).get("matchType"),
        )
        for row in rows
    }
    operations = []
    for group in GROUPS:
        resource = ad_groups[group["name"]]
        for text, match_type in group["keywords"]:
            if (resource, text.lower(), match_type) not in existing:
                operations.append({"create": {
                    "adGroup": resource,
                    "status": "ENABLED",
                    "keyword": {"text": text, "matchType": match_type},
                }})
    mutate(env, token, "adGroupCriteria", operations)
    return len(operations)


def ensure_ads(
    env: dict[str, str], token: str, ad_groups: dict[str, str]
) -> int:
    """Create any missing RSA, keyed by (ad group, path2).

    Existing ads are never rewritten. Live ad copy has been edited by hand
    since launch, so overwriting from this file would silently revert it.
    """
    rows = search(
        env,
        token,
        "SELECT ad_group.resource_name, ad_group_ad.ad.id, ad_group_ad.ad.type, "
        "ad_group_ad.ad.responsive_search_ad.path2 "
        "FROM ad_group_ad "
        f"WHERE campaign.name = '{CAMPAIGN}' "
        "AND ad_group_ad.ad.type = RESPONSIVE_SEARCH_AD "
        "AND ad_group_ad.status != 'REMOVED'",
    )
    existing = {
        (
            row.get("adGroup", {}).get("resourceName"),
            row.get("adGroupAd", {}).get("ad", {})
            .get("responsiveSearchAd", {}).get("path2"),
        )
        for row in rows
    }
    operations = []
    for group in GROUPS:
        resource = ad_groups[group["name"]]
        for ad in group["ads"]:
            if (resource, ad["path2"]) in existing:
                continue
            operations.append({"create": {
                "adGroup": resource,
                "status": "ENABLED",
                "ad": {
                    "finalUrls": [group["url"]],
                    "responsiveSearchAd": {
                        "headlines": [{"text": text} for text in ad["headlines"]],
                        "descriptions": [
                            {"text": text} for text in ad["descriptions"]
                        ],
                        "path1": ad["path1"],
                        "path2": ad["path2"],
                    },
                },
            }})
    mutate(env, token, "adGroupAds", operations)
    return len(operations)


def ensure_assets(
    env: dict[str, str], token: str, campaign: str
) -> tuple[int, int]:
    linked_rows = search(
        env,
        token,
        "SELECT campaign_asset.field_type, asset.id, asset.name "
        "FROM campaign_asset "
        f"WHERE campaign_asset.campaign = '{campaign}'",
    )
    linked = {
        (
            row.get("asset", {}).get("name"),
            row.get("campaignAsset", {}).get("fieldType"),
        )
        for row in linked_rows
    }
    specs: list[tuple[str, str, dict[str, Any]]] = []
    for text, url, description1, description2 in SITELINKS:
        name = f"DCT | Sitelink | {text}"
        specs.append((name, "SITELINK", {
            "name": name,
            "sitelinkAsset": {
                "linkText": text,
                "description1": description1,
                "description2": description2,
            },
            "finalUrls": [url],
        }))
    for text in CALLOUTS:
        name = f"DCT | Callout | {text}"
        specs.append((name, "CALLOUT", {
            "name": name,
            "calloutAsset": {"calloutText": text},
        }))
    asset_rows = search(
        env,
        token,
        "SELECT asset.id, asset.name, asset.resource_name FROM asset "
        "WHERE asset.name LIKE 'DCT | %'",
    )
    by_name = {
        row["asset"]["name"]: row["asset"]["resourceName"]
        for row in asset_rows
        if row.get("asset", {}).get("name")
    }
    missing = [spec for spec in specs if spec[0] not in by_name]
    payload = mutate(
        env,
        token,
        "assets",
        [{"create": spec[2]} for spec in missing],
    )
    for spec, result in zip(missing, payload.get("results", [])):
        by_name[spec[0]] = result["resourceName"]
    links = [
        {"create": {
            "campaign": campaign,
            "asset": by_name[name],
            "fieldType": field_type,
        }}
        for name, field_type, _ in specs
        if (name, field_type) not in linked
    ]
    mutate(env, token, "campaignAssets", links)
    return len(missing), len(links)


def ensure_shared_sets(env: dict[str, str], token: str, campaign: str) -> int:
    """Attach the account-level negative lists to the campaign.

    Negative keywords moved out of this builder on 10 September 2026 when they
    were consolidated into shared sets. Without this step a rebuilt campaign
    would serve with NO negative coverage at all, which is worse than the
    campaign-level negatives it replaced.
    """
    sets = {
        row["sharedSet"]["name"]: row["sharedSet"]["resourceName"]
        for row in search(
            env,
            token,
            "SELECT shared_set.name, shared_set.resource_name, shared_set.status "
            "FROM shared_set WHERE shared_set.type = 'NEGATIVE_KEYWORDS' "
            "AND shared_set.status = 'ENABLED'",
        )
    }
    missing_lists = [name for name in NEGATIVE_SHARED_SETS if name not in sets]
    if missing_lists:
        raise RuntimeError(
            "missing negative shared set(s): " + ", ".join(missing_lists)
            + " - run tools/consolidate_google_ads_negatives.py first"
        )
    attached = {
        row["campaignSharedSet"]["sharedSet"]
        for row in search(
            env,
            token,
            "SELECT campaign_shared_set.shared_set FROM campaign_shared_set "
            f"WHERE campaign.resource_name = '{campaign}'",
        )
    }
    operations = [
        {"create": {"campaign": campaign, "sharedSet": sets[name]}}
        for name in NEGATIVE_SHARED_SETS
        if sets[name] not in attached
    ]
    mutate(env, token, "campaignSharedSets", operations)
    return len(operations)


def snapshot(env: dict[str, str], token: str) -> dict[str, Any]:
    campaign_rows = search(
        env,
        token,
        "SELECT campaign.id, campaign.name, campaign.status, "
        "campaign.advertising_channel_type, campaign.bidding_strategy_type, "
        "campaign.network_settings.target_google_search, "
        "campaign.network_settings.target_search_network, "
        "campaign.network_settings.target_content_network, "
        "campaign.network_settings.target_partner_search_network, "
        "campaign.geo_target_type_setting.positive_geo_target_type, "
        "campaign.geo_target_type_setting.negative_geo_target_type, "
        "campaign.target_spend.cpc_bid_ceiling_micros, "
        "campaign.primary_status, "
        "campaign_budget.amount_micros "
        f"FROM campaign WHERE campaign.name = '{CAMPAIGN}'",
    )
    group_rows = search(
        env,
        token,
        "SELECT ad_group.id, ad_group.name, ad_group.status FROM ad_group "
        f"WHERE campaign.name = '{CAMPAIGN}' ORDER BY ad_group.name",
    )
    keyword_rows = search(
        env,
        token,
        "SELECT ad_group.name, ad_group_criterion.status, "
        "ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type "
        f"FROM keyword_view WHERE campaign.name = '{CAMPAIGN}'",
    )
    ad_rows = search(
        env,
        token,
        "SELECT ad_group.name, ad_group_ad.status, ad_group_ad.ad.id, "
        "ad_group_ad.ad.type, ad_group_ad.ad.final_urls, "
        "ad_group_ad.ad_strength, ad_group_ad.primary_status, "
        "ad_group_ad.policy_summary.approval_status, "
        "ad_group_ad.policy_summary.review_status FROM ad_group_ad "
        f"WHERE campaign.name = '{CAMPAIGN}'",
    )
    criterion_rows = search(
        env,
        token,
        "SELECT campaign_criterion.negative, campaign_criterion.type, "
        "campaign_criterion.keyword.text, campaign_criterion.keyword.match_type, "
        "campaign_criterion.location.geo_target_constant, "
        "campaign_criterion.language.language_constant FROM campaign_criterion "
        f"WHERE campaign.name = '{CAMPAIGN}'",
    )
    asset_rows = search(
        env,
        token,
        "SELECT campaign.name, campaign_asset.field_type, asset.id, asset.name "
        "FROM campaign_asset "
        f"WHERE campaign.name = '{CAMPAIGN}'",
    )
    shared_set_rows = search(
        env,
        token,
        "SELECT shared_set.name, shared_set.status, campaign_shared_set.status "
        f"FROM campaign_shared_set WHERE campaign.name = '{CAMPAIGN}'",
    )
    campaign = campaign_rows[0].get("campaign", {}) if campaign_rows else {}
    budget = campaign_rows[0].get("campaignBudget", {}) if campaign_rows else {}
    criteria = [row.get("campaignCriterion", {}) for row in criterion_rows]
    serving_group_names = {
        row["adGroup"]["name"]
        for row in group_rows
        if row.get("adGroup", {}).get("status") == "ENABLED"
    }
    return {
        "campaign": campaign,
        "budget_cad_per_day": int(budget.get("amountMicros", "0")) / 1_000_000,
        # Totals count every row the API returns, including PAUSED groups and
        # REMOVED criteria. The "serving_" figures are what can actually run,
        # and are the numbers to quote. The two diverged after the 10 September
        # 2026 merge left four source ad groups paused but intact.
        "ad_group_count": len(group_rows),
        "serving_ad_group_count": sum(
            1 for row in group_rows if row.get("adGroup", {}).get("status") == "ENABLED"
        ),
        "ad_groups": [row.get("adGroup", {}) for row in group_rows],
        "keyword_count": len(keyword_rows),
        "serving_keyword_count": sum(
            1 for row in keyword_rows
            if row.get("adGroupCriterion", {}).get("status") == "ENABLED"
            and row.get("adGroup", {}).get("name") in serving_group_names
        ),
        "responsive_search_ad_count": len(ad_rows),
        "serving_responsive_search_ad_count": sum(
            1 for row in ad_rows
            if row.get("adGroupAd", {}).get("status") == "ENABLED"
            and row.get("adGroup", {}).get("name") in serving_group_names
        ),
        "responsive_search_ads": [
            {
                "ad_group": row.get("adGroup", {}).get("name"),
                "status": row.get("adGroupAd", {}).get("status"),
                "ad_strength": row.get("adGroupAd", {}).get("adStrength"),
                "primary_status": row.get("adGroupAd", {}).get("primaryStatus"),
                "policy": row.get("adGroupAd", {}).get("policySummary"),
            }
            for row in ad_rows
        ],
        "campaign_criterion_count": len(criterion_rows),
        # Expected to be 0 since the 10 September 2026 consolidation. Negative
        # coverage now comes from the attached shared sets below, so read the
        # two together - a 0 here with 0 attached lists means NO negatives.
        "campaign_negative_keyword_count": sum(
            1 for item in criteria if item.get("negative") and item.get("keyword")
        ),
        "attached_negative_shared_lists": [
            row.get("sharedSet", {}).get("name") for row in shared_set_rows
        ],
        "attached_negative_shared_list_count": len(shared_set_rows),
        "negative_coverage_ok": (
            {row.get("sharedSet", {}).get("name") for row in shared_set_rows}
            == set(NEGATIVE_SHARED_SETS)
        ),
        "location_targets": [
            item.get("location", {}).get("geoTargetConstant")
            for item in criteria
            if item.get("location")
        ],
        "language_targets": [
            item.get("language", {}).get("languageConstant")
            for item in criteria
            if item.get("language")
        ],
        "linked_asset_count": len(asset_rows),
        "linked_assets": [
            {
                "name": row.get("asset", {}).get("name"),
                "fieldType": row.get("campaignAsset", {}).get("fieldType"),
            }
            for row in asset_rows
        ],
    }


def plan() -> dict[str, Any]:
    return {
        "customer_id": CID,
        "campaign": CAMPAIGN,
        "campaign_status": "PAUSED",
        "budget_cad_per_day": 150,
        "bidding": "MAXIMIZE_CLICKS",
        "max_cpc_cad": 5,
        "targeting": "Canada presence, English",
        "search_partners": False,
        "display_network": False,
        "ad_group_count": len(GROUPS),
        "ad_groups": [
            {
                "name": group["name"],
                "status": group["status"],
                "keyword_count": len(group["keywords"]),
                "ad_count": len(group["ads"]),
                "landing_page": group["url"],
            }
            for group in GROUPS
        ],
        "negative_shared_lists": NEGATIVE_SHARED_SETS,
        "campaign_negative_keyword_count": 0,
        "sitelink_count": len(SITELINKS),
        "callout_count": len(CALLOUTS),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    validate_plan()
    if not (args.apply or args.verify):
        print(json.dumps(plan(), indent=2))
        return
    env = ads.load_env()
    token = ads.oauth_token(env)
    if args.verify:
        print(json.dumps(snapshot(env, token), indent=2))
        return
    budget = ensure_budget(env, token)
    campaign = ensure_campaign(env, token, budget)
    changes = {
        "campaign_criteria_created": ensure_campaign_criteria(env, token, campaign),
        "negative_shared_sets_attached": ensure_shared_sets(env, token, campaign),
    }
    ad_groups = ensure_ad_groups(env, token, campaign)
    changes["ad_groups_total"] = len(ad_groups)
    changes["keywords_created"] = ensure_keywords(env, token, ad_groups)
    changes["responsive_search_ads_created"] = ensure_ads(env, token, ad_groups)
    assets_created, links_created = ensure_assets(env, token, campaign)
    changes["assets_created"] = assets_created
    changes["asset_links_created"] = links_created
    print(json.dumps({"changes": changes, "snapshot": snapshot(env, token)}, indent=2))


if __name__ == "__main__":
    main()
