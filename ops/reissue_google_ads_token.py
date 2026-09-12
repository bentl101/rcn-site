#!/usr/bin/env python3
"""Mint a fresh Google Ads refresh token and push it to every place that uses it.

Run this when every Google Ads call starts returning ``invalid_grant``. That
error on the refresh token means the grant behind it is gone - a password
change, a security checkup, or "remove third-party access" on the Google
account revokes all of them at once. Nothing on our side can un-revoke it;
a human has to click through the consent screen again.

The token lives in FOUR places. Miss one and that path silently fails while
the others work - which is exactly how the health cron reported "All good"
on the morning the n8n uploads died (it was testing its own copy).

    1. claude/.env                              - local tools, conversion_worker
    2. VPS /home/ben/infra/n8n/.env             - n8n Upload Click Conversion + Lookup Geo
       (needs docker compose up -d --force-recreate; restart does NOT re-read env_file)
    3. VPS ~/.secrets                           - rcn_report.py health/daily crons
    4. Apps Script Script Properties            - Review/Good Leads/Spam tab checkboxes
       (bound to leads workbook; not scriptable from here - done by hand)

Usage:
    python3 ops/reissue_google_ads_token.py            # mint + write everywhere
    python3 ops/reissue_google_ads_token.py --dry-run  # mint, show where it would go, write nothing

Stdlib only. Uses the Desktop OAuth client already in claude/.env. Opens a
browser for the consent click, catches the redirect on a loopback port.
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import pathlib
import re
import secrets
import shutil
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[2]  # claude/
LOCAL_ENV = ROOT / ".env"
VPS = "ben@46.224.150.87"
VPS_N8N_ENV = "/home/ben/infra/n8n/.env"
VPS_SECRETS = "~/.secrets"
VPS_COMPOSE_DIR = "/home/ben/infra/n8n"

SCOPE = "https://www.googleapis.com/auth/adwords"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
PORT = 8765


def read_env(path: pathlib.Path) -> dict[str, str]:
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip().removeprefix("export ").strip()] = v.strip().strip("\"'")
    return env


def short(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12]


class Catcher(http.server.BaseHTTPRequestHandler):
    code: str | None = None
    state: str = ""

    def do_GET(self):  # noqa: N802
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if qs.get("state", [""])[0] != Catcher.state:
            self.send_response(400); self.end_headers()
            self.wfile.write(b"state mismatch - close this tab and rerun"); return
        Catcher.code = qs.get("code", [None])[0]
        self.send_response(200); self.end_headers()
        self.wfile.write(b"Token captured. You can close this tab.")

    def log_message(self, *_):
        pass


def mint(client_id: str, client_secret: str) -> str:
    Catcher.state = secrets.token_urlsafe(16)
    redirect = f"http://localhost:{PORT}"
    params = {
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent",
        "state": Catcher.state,
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    server = http.server.HTTPServer(("localhost", PORT), Catcher)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print("\nOpening the consent screen. Sign in with the Google account that")
    print("has access to the Copperchunk MCC (381-427-8874) and click Allow.\n")
    print(f"If no browser opens, paste this:\n{url}\n")
    webbrowser.open(url)
    while Catcher.code is None:
        thread.join(0.2)
    server.shutdown()

    body = urllib.parse.urlencode({
        "code": Catcher.code, "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": redirect, "grant_type": "authorization_code",
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=body), timeout=30) as r:
        payload = json.load(r)
    token = payload.get("refresh_token")
    if not token:
        sys.exit(f"no refresh_token in response (got {sorted(payload)}); "
                 "the client may not be a Desktop app, or consent was not re-prompted")
    return token


def verify(client_id: str, client_secret: str, refresh: str) -> None:
    body = urllib.parse.urlencode({
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh, "grant_type": "refresh_token",
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=body), timeout=30) as r:
        assert "access_token" in json.load(r)


def replace_in_file_text(text: str, token: str) -> str:
    pattern = re.compile(r'^(\s*(?:export\s+)?GOOGLE_ADS_REFRESH_TOKEN\s*=\s*)(["\']?)[^\n]*$', re.M)
    if not pattern.search(text):
        sys.exit("GOOGLE_ADS_REFRESH_TOKEN line not found")
    return pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}{token}{m.group(2)}", text)


def write_local(token: str, dry: bool) -> None:
    text = LOCAL_ENV.read_text()
    if not dry:
        backup = LOCAL_ENV.with_suffix(f".env.bak.{datetime.now(timezone.utc):%Y%m%d%H%M%S}")
        shutil.copy2(LOCAL_ENV, backup)
        LOCAL_ENV.write_text(replace_in_file_text(text, token))
    print(f"  [{'dry' if dry else 'ok'}] 1. {LOCAL_ENV}")


def write_vps(token: str, dry: bool) -> None:
    # One python invocation on the VPS updates both files, backs each up, recreates n8n.
    remote = f'''
import re, pathlib, shutil, subprocess, sys
from datetime import datetime, timezone
token = sys.stdin.read().strip()
pat = re.compile(r'^(\\s*(?:export\\s+)?GOOGLE_ADS_REFRESH_TOKEN\\s*=\\s*)(["\\']?)[^\\n]*$', re.M)
for p in [pathlib.Path("{VPS_N8N_ENV}"), pathlib.Path("{VPS_SECRETS}").expanduser()]:
    t = p.read_text()
    if not pat.search(t): print("  skip (no key):", p); continue
    shutil.copy2(p, p.with_name(p.name + ".bak." + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")))
    p.write_text(pat.sub(lambda m: m.group(1) + m.group(2) + token + m.group(2), t))
    print("  [ok] wrote", p)
r = subprocess.run(["docker", "compose", "up", "-d", "--force-recreate", "n8n"],
                   cwd="{VPS_COMPOSE_DIR}", capture_output=True, text=True)
print("  [ok] n8n recreated" if r.returncode == 0 else "  [FAIL] compose: " + r.stderr[-300:])
'''
    if dry:
        print(f"  [dry] 2. {VPS}:{VPS_N8N_ENV} + force-recreate n8n")
        print(f"  [dry] 3. {VPS}:{VPS_SECRETS}")
        return
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", VPS, "python3", "-c", remote],
                       input=token, capture_output=True, text=True, timeout=180)
    print(r.stdout.rstrip() or r.stderr.rstrip())
    if r.returncode != 0:
        sys.exit("VPS update failed - fix by hand before relying on n8n uploads")


def smoke_n8n() -> None:
    js = ('const q=new URLSearchParams({client_id:process.env.GOOGLE_ADS_CLIENT_ID,'
          'client_secret:process.env.GOOGLE_ADS_CLIENT_SECRET,'
          'refresh_token:process.env.GOOGLE_ADS_REFRESH_TOKEN,grant_type:"refresh_token"});'
          'fetch("https://oauth2.googleapis.com/token",{method:"POST",body:q})'
          '.then(r=>console.log(r.ok?"  [ok] n8n container can mint an access token":"  [FAIL] n8n token "+r.status))')
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", VPS,
                        f"printf %s '{js}' > /tmp/tok.js && docker cp /tmp/tok.js n8n:/tmp/tok.js "
                        "&& docker exec n8n node /tmp/tok.js"],
                       capture_output=True, text=True, timeout=90)
    print(r.stdout.rstrip() or r.stderr.rstrip())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--print-token", action="store_true", help="print the raw refresh token for a manual Apps Script update")
    args = ap.parse_args()

    env = read_env(LOCAL_ENV)
    cid, csec = env["GOOGLE_ADS_CLIENT_ID"], env["GOOGLE_ADS_CLIENT_SECRET"]
    print(f"old refresh token: {short(env['GOOGLE_ADS_REFRESH_TOKEN'])}")

    token = mint(cid, csec)
    verify(cid, csec, token)
    print(f"new refresh token: {short(token)}  (verified: mints an access token)\n")

    print("writing to the four homes:")
    write_local(token, args.dry_run)
    write_vps(token, args.dry_run)
    if not args.dry_run:
        smoke_n8n()
    print("  [MANUAL] 4. Apps Script -> Project Settings -> Script Properties ->")
    print("     GOOGLE_ADS_REFRESH_TOKEN still needs updating for the RCN workbook.")
    if args.print_token:
        print("     Raw token requested explicitly; never commit it.\n")
        print(f"  {token}\n")
    else:
        print("     Raw token hidden. Re-run with --print-token only when updating that property.\n")
    print("then backfill any lead that missed its upload while the token was dead:")
    print("  ./conversion_worker.py --upload-order RCN-...")


if __name__ == "__main__":
    main()
