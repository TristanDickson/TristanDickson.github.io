#!/usr/bin/env python3
"""One-off Enphase API v4 setup for a single home system: exchange the owner's authorization
code, refresh on demand, list systems and pull a day of production telemetry. Stdlib only.

Env: ENPHASE_API_KEY, ENPHASE_CLIENT_ID, ENPHASE_CLIENT_SECRET.
Tokens are kept in ~/.tesla-fleet/enphase-tokens.json (mode 600). Access tokens last a day,
refresh tokens a month, so a poller that lapses for a month needs a fresh browser login.
"""
import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

AUTH = "https://api.enphaseenergy.com/oauth/authorize"
TOKEN = "https://api.enphaseenergy.com/oauth/token"
API = "https://api.enphaseenergy.com/api/v4"
REDIRECT = "https://api.enphaseenergy.com/oauth/redirect_uri"  # Enphase's own page that displays the code
TOKENS = Path.home() / ".tesla-fleet" / "enphase-tokens.json"


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"set {name}")
    return value


def call(req: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"{req.full_url.split('?')[0]} -> HTTP {e.code}\n{e.read().decode(errors='replace')}")


def token_call(params: dict) -> dict:
    """Enphase takes the grant parameters as query string on an empty POST, with client id and
    secret as HTTP basic auth."""
    basic = base64.b64encode(f"{env('ENPHASE_CLIENT_ID')}:{env('ENPHASE_CLIENT_SECRET')}".encode()).decode()
    req = urllib.request.Request(f"{TOKEN}?{urllib.parse.urlencode(params)}", data=b"", method="POST",
                                 headers={"Authorization": f"Basic {basic}"})
    return call(req)


def save_tokens(tokens: dict) -> None:
    TOKENS.parent.mkdir(mode=0o700, exist_ok=True)
    tokens["saved_at"] = int(time.time())
    TOKENS.write_text(json.dumps(tokens, indent=1))
    TOKENS.chmod(0o600)


def access_token() -> str:
    """Reuse the access token while it has an hour left, otherwise refresh and persist."""
    if not TOKENS.exists():
        sys.exit("no tokens yet: run auth-url then exchange")
    tokens = json.loads(TOKENS.read_text())
    if time.time() < tokens["saved_at"] + tokens.get("expires_in", 0) - 3600:
        return tokens["access_token"]
    new = token_call({"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"]})
    save_tokens(new)
    return new["access_token"]


def get(path: str, params: dict | None = None) -> dict:
    query = urllib.parse.urlencode({"key": env("ENPHASE_API_KEY"), **(params or {})})
    req = urllib.request.Request(f"{API}{path}?{query}", headers={"Authorization": f"Bearer {access_token()}"})
    return call(req)


def auth_url() -> None:
    params = {"response_type": "code", "client_id": env("ENPHASE_CLIENT_ID"), "redirect_uri": REDIRECT}
    print(f"{AUTH}?{urllib.parse.urlencode(params)}")
    print("\nLog in with the homeowner Enlighten account, approve, and copy the code the page shows.")


def exchange(code: str) -> None:
    tokens = token_call({"grant_type": "authorization_code", "redirect_uri": REDIRECT, "code": code})
    save_tokens(tokens)
    print(f"saved {TOKENS} (expires_in {tokens.get('expires_in')}s, refresh token present: {'refresh_token' in tokens})")


def systems() -> None:
    data = get("/systems")
    for s in data.get("systems", []):
        print(f"system_id={s['system_id']}  name={s.get('name')}  status={s.get('status')}  "
              f"connection={s.get('connection_type')}  last_report={s.get('last_report_at')}")
    print(json.dumps(data, indent=1)[:2000])


def system_id() -> int:
    if os.environ.get("ENPHASE_SYSTEM_ID"):
        return int(os.environ["ENPHASE_SYSTEM_ID"])
    return get("/systems")["systems"][0]["system_id"]


def production() -> None:
    """Yesterday's microinverter production in the 15-minute buckets Enphase reports."""
    yesterday = date.today() - timedelta(days=1)
    start_at = int(datetime.combine(yesterday, datetime.min.time()).timestamp())
    print(json.dumps(get(f"/systems/{system_id()}/telemetry/production_micro",
                         {"start_at": start_at, "granularity": "day"}), indent=1))


def lifetime() -> None:
    """Daily production totals for the last week, the cheap one-call-per-week shape."""
    end = date.today() - timedelta(days=1)
    print(json.dumps(get(f"/systems/{system_id()}/energy_lifetime",
                         {"start_date": str(end - timedelta(days=6)), "end_date": str(end)}), indent=1))


if __name__ == "__main__":
    cmds = {"auth-url": auth_url, "systems": systems, "production": production, "lifetime": lifetime}
    if len(sys.argv) >= 3 and sys.argv[1] == "exchange":
        exchange(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] in cmds:
        cmds[sys.argv[1]]()
    else:
        sys.exit("usage: enphase.py auth-url | exchange <code> | systems | production | lifetime")
