#!/usr/bin/env python3
"""One-off Tesla Fleet API setup for a single Powerwall: register the partner account, mint
an owner refresh token, and pull a first energy_site reading. Stdlib only.

Env: TESLA_CLIENT_ID, TESLA_CLIENT_SECRET, TESLA_DOMAIN, TESLA_REDIRECT_URI, TESLA_REGION (eu|na, default eu).
Tokens are kept in ~/.tesla-fleet/tokens.json (mode 600). The refresh token rotates on every use.
"""
import json
import os
import secrets
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

AUTH = "https://auth.tesla.com/oauth2/v3/authorize"
TOKEN = "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token"
REGION = os.environ.get("TESLA_REGION", "eu")
API = f"https://fleet-api.prd.{REGION}.vn.cloud.tesla.com"
SCOPES = "openid offline_access energy_device_data"
TOKENS = Path.home() / ".tesla-fleet" / "tokens.json"


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"set {name}")
    return value


def post_form(url: str, data: dict, headers: dict | None = None) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded", **(headers or {})})
    return call(req)


def post_json(url: str, data: dict, token: str) -> dict:
    req = urllib.request.Request(url, data=json.dumps(data).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    return call(req)


def get(url: str, token: str) -> dict:
    return call(urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}))


def call(req: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"{req.full_url} -> HTTP {e.code}\n{e.read().decode(errors='replace')}")


def save_tokens(tokens: dict) -> None:
    TOKENS.parent.mkdir(mode=0o700, exist_ok=True)
    TOKENS.write_text(json.dumps(tokens, indent=1))
    TOKENS.chmod(0o600)


def access_token() -> str:
    """Refresh on every call; Tesla rotates the refresh token, so persist the new one immediately."""
    if not TOKENS.exists():
        sys.exit("no tokens yet: run auth-url then exchange")
    old = json.loads(TOKENS.read_text())
    new = post_form(TOKEN, {
        "grant_type": "refresh_token",
        "client_id": env("TESLA_CLIENT_ID"),
        "refresh_token": old["refresh_token"],
    })
    save_tokens(new)
    return new["access_token"]


def register() -> None:
    partner = post_form(TOKEN, {
        "grant_type": "client_credentials",
        "client_id": env("TESLA_CLIENT_ID"),
        "client_secret": env("TESLA_CLIENT_SECRET"),
        "scope": "openid energy_device_data",
        "audience": API,
    })
    print(json.dumps(post_json(f"{API}/api/1/partner_accounts", {"domain": env("TESLA_DOMAIN")}, partner["access_token"]), indent=1))


def auth_url() -> None:
    params = {
        "response_type": "code",
        "client_id": env("TESLA_CLIENT_ID"),
        "redirect_uri": env("TESLA_REDIRECT_URI"),
        "scope": SCOPES,
        "state": secrets.token_urlsafe(16),
    }
    print(f"{AUTH}?{urllib.parse.urlencode(params)}")
    print("\nLog in, approve, then copy the `code` query parameter from the address bar you land on.")


def exchange(code: str) -> None:
    tokens = post_form(TOKEN, {
        "grant_type": "authorization_code",
        "client_id": env("TESLA_CLIENT_ID"),
        "client_secret": env("TESLA_CLIENT_SECRET"),
        "code": code,
        "redirect_uri": env("TESLA_REDIRECT_URI"),
        "audience": API,
    })
    save_tokens(tokens)
    print(f"saved {TOKENS} (expires_in {tokens.get('expires_in')}s, refresh token present: {'refresh_token' in tokens})")


def products() -> None:
    data = get(f"{API}/api/1/products", access_token())
    for p in data.get("response", []):
        if "energy_site_id" in p:
            print(f"energy_site_id={p['energy_site_id']}  name={p.get('site_name')}  battery={p.get('resource_type')}")
    print(json.dumps(data, indent=1)[:2000])


def history() -> None:
    token = access_token()
    site = os.environ.get("TESLA_SITE_ID") or next(
        str(p["energy_site_id"]) for p in get(f"{API}/api/1/products", token)["response"] if "energy_site_id" in p)
    yesterday = date.today() - timedelta(days=1)
    params = urllib.parse.urlencode({
        "kind": "energy",
        "period": "day",
        "start_date": f"{yesterday}T00:00:00Z",
        "end_date": f"{yesterday}T23:59:59Z",
        "time_zone": "Europe/London",
    })
    print(json.dumps(get(f"{API}/api/1/energy_sites/{site}/calendar_history?{params}", token), indent=1))


if __name__ == "__main__":
    cmds = {"register": register, "auth-url": auth_url, "products": products, "history": history}
    if len(sys.argv) >= 3 and sys.argv[1] == "exchange":
        exchange(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] in cmds:
        cmds[sys.argv[1]]()
    else:
        sys.exit("usage: tesla_fleet.py register | auth-url | exchange <code> | products | history")
