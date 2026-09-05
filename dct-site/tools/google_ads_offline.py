#!/usr/bin/env python3
"""Inspect and configure Discount Coach Tours offline conversions.

Secrets are loaded from the shared untracked ``claude/.env`` file and are
never printed. Mutating operations require the explicit ``--apply`` flag.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request

API_VERSION = "v25"
API_ROOT = f"https://googleads.googleapis.com/{API_VERSION}"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
TARGET_CUSTOMER_ID = "3639225242"
TARGET_CUSTOMER_NAME = "Discount Coach Tours"
FINAL_URL_SUFFIX = (
    "utm_source=google&utm_medium=cpc&utm_campaign={campaignid}"
    "&utm_term={keyword}&utm_content={creative}&utm_id={campaignid}"
    "&matchtype={matchtype}&device={device}&network={network}"
    "&adgroupid={adgroupid}&targetid={targetid}"
    "&loc_physical={loc_physical_ms}&loc_interest={loc_interest_ms}"
)
ACTION_SPECS = {
    "gclid": {
        "name": "DCT - Submit Lead Form (Offline - GCLID)",
        "countingType": "ONE_PER_CLICK",
    },
    "braid": {
        "name": "DCT - Submit Lead Form (Offline - Braid)",
        "countingType": "MANY_PER_CLICK",
    },
}


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (PROJECT_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def oauth_token(env: dict[str, str]) -> str:
    body = urllib.parse.urlencode({
        "client_id": env["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": env["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": env["GOOGLE_ADS_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())["access_token"]


def request_json(env: dict[str, str], token: str, method: str, url: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "developer-token": env["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "login-customer-id": env["GOOGLE_ADS_LOGIN_CUSTOMER_ID"].replace("-", ""),
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 DCT-Offline-Setup/1.0",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"error": {"message": raw[:1000]}}
        return exc.code, payload


def search(env: dict[str, str], token: str, customer_id: str, query: str) -> list[dict]:
    clean_id = customer_id.replace("-", "")
    status, payload = request_json(
        env, token, "POST", f"{API_ROOT}/customers/{clean_id}/googleAds:searchStream",
        {"query": query},
    )
    if status != 200:
        if isinstance(payload, dict):
            message = payload.get("error", {}).get("message", "unknown error")
        else:
            message = json.dumps(payload, separators=(",", ":"))[:1000]
        raise RuntimeError(f"Google Ads search failed ({status}): {message}")
    rows: list[dict] = []
    for batch in payload:
        rows.extend(batch.get("results", []))
    return rows


def inspect_accounts(env: dict[str, str], token: str) -> list[dict]:
    manager_id = env["GOOGLE_ADS_LOGIN_CUSTOMER_ID"].replace("-", "")
    rows = search(env, token, manager_id, """
        SELECT customer_client.id, customer_client.descriptive_name,
               customer_client.status, customer_client.manager,
               customer_client.level, customer_client.test_account,
               customer_client.currency_code, customer_client.time_zone
        FROM customer_client
        WHERE customer_client.level <= 1
        ORDER BY customer_client.descriptive_name
    """)
    accounts = []
    for row in rows:
        item = row.get("customerClient", {})
        accounts.append({
            "id": str(item.get("id", "")), "name": item.get("descriptiveName", ""),
            "status": item.get("status", ""), "manager": item.get("manager", False),
            "level": item.get("level"), "test_account": item.get("testAccount", False),
            "currency": item.get("currencyCode", ""), "time_zone": item.get("timeZone", ""),
        })
    return accounts


def inspect_customer(env: dict[str, str], token: str, customer_id: str) -> dict:
    customer_rows = search(env, token, customer_id, """
        SELECT customer.id, customer.descriptive_name, customer.status,
               customer.currency_code, customer.time_zone,
               customer.auto_tagging_enabled, customer.final_url_suffix,
               customer.conversion_tracking_setting.accepted_customer_data_terms,
               customer.conversion_tracking_setting.enhanced_conversions_for_leads_enabled,
               customer.conversion_tracking_setting.conversion_tracking_status,
               customer.conversion_tracking_setting.google_ads_conversion_customer
        FROM customer
    """)
    campaign_rows = search(env, token, customer_id, """
        SELECT campaign.id, campaign.name, campaign.status,
               campaign.advertising_channel_type
        FROM campaign ORDER BY campaign.id
    """)
    action_rows = search(env, token, customer_id, """
        SELECT conversion_action.id, conversion_action.name,
               conversion_action.status, conversion_action.type,
               conversion_action.category, conversion_action.counting_type,
               conversion_action.primary_for_goal,
               conversion_action.click_through_lookback_window_days,
               conversion_action.value_settings.default_value,
               conversion_action.value_settings.default_currency_code
        FROM conversion_action ORDER BY conversion_action.id
    """)
    try:
        billing_rows = search(env, token, customer_id, """
            SELECT billing_setup.id, billing_setup.status,
                   billing_setup.start_date_time, billing_setup.end_date_time,
                   billing_setup.payments_account
            FROM billing_setup
        """)
    except RuntimeError as exc:
        billing_rows = [{"query_error": str(exc)}]
    try:
        access_rows = search(env, token, customer_id, """
            SELECT customer_user_access.user_id,
                   customer_user_access.email_address,
                   customer_user_access.access_role,
                   customer_user_access.access_creation_date_time,
                   customer_user_access.inviter_user_email_address
            FROM customer_user_access
        """)
    except RuntimeError as exc:
        access_rows = [{"query_error": str(exc)}]
    try:
        invitation_rows = search(env, token, customer_id, """
            SELECT customer_user_access_invitation.invitation_id,
                   customer_user_access_invitation.email_address,
                   customer_user_access_invitation.access_role,
                   customer_user_access_invitation.creation_date_time
            FROM customer_user_access_invitation
        """)
    except RuntimeError as exc:
        invitation_rows = [{"query_error": str(exc)}]
    return {
        "customer_id": customer_id.replace("-", ""),
        "customer": customer_rows[0].get("customer", {}) if customer_rows else {},
        "campaigns": [row.get("campaign", {}) for row in campaign_rows],
        "conversion_actions": [row.get("conversionAction", {}) for row in action_rows],
        "billing_setups": [row.get("billingSetup", row) for row in billing_rows],
        "user_access": [row.get("customerUserAccess", row) for row in access_rows],
        "user_invitations": [row.get("customerUserAccessInvitation", row) for row in invitation_rows],
    }


def customer_update_operation(current: dict) -> dict | None:
    update = {"resourceName": f"customers/{TARGET_CUSTOMER_ID}"}
    mask: list[str] = []
    desired = {
        "descriptiveName": TARGET_CUSTOMER_NAME,
        "autoTaggingEnabled": True,
        "finalUrlSuffix": FINAL_URL_SUFFIX,
    }
    for field, value in desired.items():
        if current.get(field) != value:
            update[field] = value
            mask.append(field)
    if not mask:
        return None
    return {"update": update, "updateMask": ",".join(mask)}


def action_payload(spec: dict) -> dict:
    return {
        "name": spec["name"],
        "type": "UPLOAD_CLICKS",
        "category": "SUBMIT_LEAD_FORM",
        "status": "ENABLED",
        "countingType": spec["countingType"],
        "primaryForGoal": True,
        "clickThroughLookbackWindowDays": "90",
        "valueSettings": {
            "defaultValue": 50,
            "defaultCurrencyCode": "CAD",
            "alwaysUseDefaultValue": True,
        },
    }


def ensure_configuration(env: dict[str, str], token: str, *, apply: bool) -> dict:
    before = inspect_customer(env, token, TARGET_CUSTOMER_ID)
    customer_operation = customer_update_operation(before["customer"])
    result: dict = {
        "mode": "apply" if apply else "validate_only",
        "customer_update": "unchanged" if customer_operation is None else "pending",
        "conversion_actions": {},
    }

    if customer_operation is not None:
        status, payload = request_json(
            env,
            token,
            "POST",
            f"{API_ROOT}/customers/{TARGET_CUSTOMER_ID}:mutate",
            {"operation": customer_operation, "validateOnly": not apply},
        )
        if status != 200:
            raise RuntimeError(
                f"Customer update failed ({status}): "
                f"{payload.get('error', {}).get('message', 'unknown error')}"
            )
        result["customer_update"] = "applied" if apply else "validated"

    by_name = {item.get("name"): item for item in before["conversion_actions"]}
    for key, spec in ACTION_SPECS.items():
        existing = by_name.get(spec["name"])
        if existing:
            if existing.get("type") != "UPLOAD_CLICKS":
                raise RuntimeError(f"Existing action {spec['name']!r} has immutable type {existing.get('type')!r}")
            result["conversion_actions"][key] = {
                "status": "existing",
                "resourceName": existing.get("resourceName"),
                "id": existing.get("id"),
            }
            continue
        status, payload = request_json(
            env,
            token,
            "POST",
            f"{API_ROOT}/customers/{TARGET_CUSTOMER_ID}/conversionActions:mutate",
            {
                "operations": [{"create": action_payload(spec)}],
                "validateOnly": not apply,
                "responseContentType": "MUTABLE_RESOURCE",
            },
        )
        if status != 200 or payload.get("partialFailureError"):
            message = payload.get("error", {}).get("message") or payload.get("partialFailureError", {}).get("message")
            raise RuntimeError(f"Conversion action {key} failed ({status}): {message or 'unknown error'}")
        created = (payload.get("results") or [{}])[0]
        result["conversion_actions"][key] = {
            "status": "created" if apply else "validated",
            "resourceName": created.get("resourceName"),
        }

    if apply:
        result["post_state"] = inspect_customer(env, token, TARGET_CUSTOMER_ID)
    return result


def validate_upload(env: dict[str, str], token: str, action: dict) -> dict:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    stamp = now.strftime("%Y-%m-%d %H:%M:%S+00:00")
    status, payload = request_json(
        env,
        token,
        "POST",
        f"{API_ROOT}/customers/{TARGET_CUSTOMER_ID}:uploadClickConversions",
        {
            "conversions": [{
                "gclid": "DCT_API_VALIDATION_ONLY_NOT_A_REAL_CLICK",
                "conversionAction": action["resourceName"],
                "conversionDateTime": stamp,
                "conversionValue": 50,
                "currencyCode": "CAD",
                "conversionEnvironment": "WEB",
                "orderId": f"DCT-VALIDATE-{now.strftime('%Y%m%d%H%M%S')}",
            }],
            "partialFailure": True,
            "validateOnly": True,
        },
    )
    return {
        "http_status": status,
        "partial_failure": payload.get("partialFailureError"),
        "rpc_error": payload.get("error"),
        "results_returned": len(payload.get("results", [])),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="apply idempotent DCT account configuration")
    parser.add_argument("--validate-config", action="store_true", help="validate configuration mutations without applying")
    parser.add_argument("--validate-upload", action="store_true", help="validate an offline upload without recording it")
    parser.add_argument("--customer-id", help="inspect one Google Ads customer")
    args = parser.parse_args()
    env = load_env()
    token = oauth_token(env)
    status, accessible = request_json(env, token, "GET", f"{API_ROOT}/customers:listAccessibleCustomers")
    if status != 200:
        raise SystemExit(f"API {API_VERSION} access failed: HTTP {status}")
    if args.apply or args.validate_config:
        print(json.dumps(ensure_configuration(env, token, apply=args.apply), indent=2))
        return
    if args.validate_upload:
        state = inspect_customer(env, token, TARGET_CUSTOMER_ID)
        by_name = {item.get("name"): item for item in state["conversion_actions"]}
        action = by_name.get(ACTION_SPECS["gclid"]["name"])
        if not action:
            raise SystemExit("GCLID offline action does not exist; run --apply first")
        print(json.dumps(validate_upload(env, token, action), indent=2))
        return
    if args.customer_id:
        print(json.dumps(inspect_customer(env, token, args.customer_id), indent=2))
        return
    accounts = inspect_accounts(env, token)
    matches = [a for a in accounts if any(term in a["name"].lower() for term in ("discount", "coach", "dct"))]
    print(json.dumps({
        "api_version": API_VERSION,
        "accessible_customer_count": len(accessible.get("resourceNames", [])),
        "manager_child_count": len(accounts),
        "matches": matches,
        "accounts": accounts,
    }, indent=2))


if __name__ == "__main__":
    main()
