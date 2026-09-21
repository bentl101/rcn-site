#!/usr/bin/env python3
"""Apply and verify the DCT portfolio Target CPA bid guardrail.

The live campaign keeps its C$50 target CPA while a portfolio Maximize
Conversions strategy caps keyword bids at C$6. The script is idempotent and
defaults to a read-only plan; mutations require ``--apply``.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

import google_ads_offline as ads

CID = "3639225242"
CAMPAIGN_ID = "24230451785"
CAMPAIGN_RESOURCE = f"customers/{CID}/campaigns/{CAMPAIGN_ID}"
STRATEGY_NAME = "DCT | Portfolio Target CPA 50 | Max CPC 6"
TARGET_CPA_MICROS = 50_000_000
MAX_CPC_MICROS = 6_000_000


def search(env: dict[str, str], token: str, query: str) -> list[dict[str, Any]]:
    return ads.search(env, token, CID, query)


def mutate(
    env: dict[str, str],
    token: str,
    service: str,
    operations: list[dict[str, Any]],
    *,
    validate_only: bool = False,
) -> dict[str, Any]:
    status, payload = ads.request_json(
        env,
        token,
        "POST",
        f"{ads.API_ROOT}/customers/{CID}/{service}:mutate",
        {
            "operations": operations,
            "partialFailure": False,
            "validateOnly": validate_only,
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


def strategy_rows(env: dict[str, str], token: str) -> list[dict[str, Any]]:
    escaped_name = STRATEGY_NAME.replace("'", "\\'")
    return search(
        env,
        token,
        "SELECT bidding_strategy.id, bidding_strategy.name, "
        "bidding_strategy.resource_name, bidding_strategy.status, "
        "bidding_strategy.type, bidding_strategy.campaign_count, "
        "bidding_strategy.non_removed_campaign_count, "
        "bidding_strategy.maximize_conversions.target_cpa_micros, "
        "bidding_strategy.maximize_conversions.cpc_bid_ceiling_micros "
        "FROM bidding_strategy "
        f"WHERE bidding_strategy.name = '{escaped_name}'",
    )


def snapshot(env: dict[str, str], token: str) -> dict[str, Any]:
    campaign_rows = search(
        env,
        token,
        "SELECT campaign.id, campaign.name, campaign.status, "
        "campaign.bidding_strategy, campaign.bidding_strategy_type, "
        "campaign.maximize_conversions.target_cpa_micros "
        "FROM campaign "
        f"WHERE campaign.id = {CAMPAIGN_ID}",
    )
    campaign = campaign_rows[0].get("campaign", {}) if campaign_rows else {}
    rows = strategy_rows(env, token)
    strategy = rows[0].get("biddingStrategy", {}) if rows else {}
    scheme = strategy.get("maximizeConversions", {})
    ok = bool(
        campaign
        and strategy
        and campaign.get("biddingStrategy") == strategy.get("resourceName")
        and campaign.get("biddingStrategyType") == "MAXIMIZE_CONVERSIONS"
        and int(scheme.get("targetCpaMicros", 0)) == TARGET_CPA_MICROS
        and int(scheme.get("cpcBidCeilingMicros", 0)) == MAX_CPC_MICROS
        and strategy.get("status") == "ENABLED"
    )
    return {
        "customer_id": CID,
        "campaign": campaign,
        "portfolio_strategy": strategy,
        "target_cpa_cad": TARGET_CPA_MICROS / 1_000_000,
        "max_cpc_cad": MAX_CPC_MICROS / 1_000_000,
        "ok": ok,
    }


def ensure_strategy(env: dict[str, str], token: str) -> str:
    rows = strategy_rows(env, token)
    if len(rows) > 1:
        raise RuntimeError(f"More than one bidding strategy is named {STRATEGY_NAME!r}")
    if rows:
        strategy = rows[0]["biddingStrategy"]
        scheme = strategy.get("maximizeConversions", {})
        if strategy.get("status") != "ENABLED":
            raise RuntimeError("Existing portfolio strategy is not enabled")
        if (
            int(scheme.get("targetCpaMicros", 0)) != TARGET_CPA_MICROS
            or int(scheme.get("cpcBidCeilingMicros", 0)) != MAX_CPC_MICROS
        ):
            operation = {
                "update": {
                    "resourceName": strategy["resourceName"],
                    "maximizeConversions": {
                        "targetCpaMicros": str(TARGET_CPA_MICROS),
                        "cpcBidCeilingMicros": str(MAX_CPC_MICROS),
                    },
                },
                "updateMask": (
                    "maximizeConversions.targetCpaMicros,"
                    "maximizeConversions.cpcBidCeilingMicros"
                ),
            }
            mutate(env, token, "biddingStrategies", [operation], validate_only=True)
            mutate(env, token, "biddingStrategies", [operation])
        return strategy["resourceName"]

    operation = {
        "create": {
            "name": STRATEGY_NAME,
            "maximizeConversions": {
                "targetCpaMicros": str(TARGET_CPA_MICROS),
                "cpcBidCeilingMicros": str(MAX_CPC_MICROS),
            },
        }
    }
    mutate(env, token, "biddingStrategies", [operation], validate_only=True)
    mutate(env, token, "biddingStrategies", [operation])
    rows = strategy_rows(env, token)
    if len(rows) != 1:
        raise RuntimeError("Portfolio strategy creation could not be verified")
    return rows[0]["biddingStrategy"]["resourceName"]


def assign_campaign(
    env: dict[str, str], token: str, strategy_resource: str
) -> bool:
    before = snapshot(env, token)
    if before["campaign"].get("biddingStrategy") == strategy_resource:
        return False
    operation = {
        "update": {
            "resourceName": CAMPAIGN_RESOURCE,
            "biddingStrategy": strategy_resource,
        },
        "updateMask": "biddingStrategy",
    }
    mutate(env, token, "campaigns", [operation], validate_only=True)
    mutate(env, token, "campaigns", [operation])
    return True


def plan() -> dict[str, Any]:
    return {
        "mode": "plan",
        "customer_id": CID,
        "campaign_id": CAMPAIGN_ID,
        "portfolio_strategy_name": STRATEGY_NAME,
        "bidding": "MAXIMIZE_CONVERSIONS",
        "target_cpa_cad": TARGET_CPA_MICROS / 1_000_000,
        "max_cpc_cad": MAX_CPC_MICROS / 1_000_000,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if not (args.apply or args.verify):
        print(json.dumps(plan(), indent=2))
        return

    env = ads.load_env()
    token = ads.oauth_token(env)
    if args.verify:
        state = snapshot(env, token)
        print(json.dumps(state, indent=2))
        raise SystemExit(0 if state["ok"] else 1)

    strategy_resource = ensure_strategy(env, token)
    campaign_changed = assign_campaign(env, token, strategy_resource)
    state = snapshot(env, token)
    if not state["ok"]:
        raise RuntimeError("Post-apply verification failed")
    print(json.dumps({"campaign_changed": campaign_changed, **state}, indent=2))


if __name__ == "__main__":
    main()
