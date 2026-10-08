#!/usr/bin/env python3
"""Read a myenergi Zappi through the unofficial cloud API: live status, and a day of hourly or
per-minute history. Stdlib only.

Env: MYENERGI_HUB_SERIAL (the gateway device's serial), MYENERGI_API_KEY (generated once in
myaccount.myenergi.com, Products, gateway card, Advanced). Digest auth, username = serial.
The director host answers directly and names the real backend in its x_myenergi-asn header.
History values are joules per bucket (hour or minute), timestamps are UTC, and zero-valued
fields are omitted from a row rather than sent as 0.
"""
import json
import os
import sys
import urllib.request
from datetime import date, timedelta

DIRECTOR = "https://director.myenergi.net"
JOULES_PER_KWH = 3_600_000
FIELDS = {"imp": "grid import", "exp": "grid export", "gep": "generation", "gen": "generation negative",
          "h1d": "zappi diverted (solar)", "h1b": "zappi boosted (grid)"}


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"set {name}")
    return value


def opener() -> urllib.request.OpenerDirector:
    auth = urllib.request.HTTPDigestAuthHandler()
    for host in (DIRECTOR, os.environ.get("MYENERGI_HOST", "")):
        if host:
            auth.add_password("MyEnergi Telemetry", host, env("MYENERGI_HUB_SERIAL"), env("MYENERGI_API_KEY"))
    return urllib.request.build_opener(auth)


def get(path: str) -> dict:
    base = os.environ.get("MYENERGI_HOST") or DIRECTOR
    try:
        with opener().open(f"{base}{path}", timeout=60) as resp:
            asn = resp.headers.get("x_myenergi-asn")
            if asn and asn != "undefined" and not os.environ.get("MYENERGI_HOST"):
                os.environ["MYENERGI_HOST"] = f"https://{asn}"
            return json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"{path} -> HTTP {e.code}\n{e.read().decode(errors='replace')}")


def day_arg() -> str:
    """Yesterday unless a YYYY-MM-DD was given; the API wants unpadded month and day."""
    d = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today() - timedelta(days=1)
    return f"{d.year}-{d.month}-{d.day}"


def totals(rows: list[dict]) -> None:
    for field, label in FIELDS.items():
        print(f"{field:4s} {label:24s} {sum(r.get(field, 0) for r in rows) / JOULES_PER_KWH:8.3f} kWh")


def status() -> None:
    print(json.dumps(get("/cgi-jstatus-*"), indent=1))


def history(kind: str) -> None:
    serial = env("MYENERGI_HUB_SERIAL")
    data = get(f"/cgi-{kind}-Z{serial}-{day_arg()}")
    rows = data[f"U{serial}"]
    print(f"{len(rows)} rows; fields seen: {sorted({k for r in rows for k in r})}")
    print(json.dumps(rows[:3], indent=1))
    totals(rows)


if __name__ == "__main__":
    cmds = {"status": status, "hours": lambda: history("jdayhour"), "minutes": lambda: history("jday")}
    if len(sys.argv) >= 2 and sys.argv[1] in cmds:
        cmds[sys.argv[1]]()
    else:
        sys.exit("usage: zappi.py status | hours [YYYY-MM-DD] | minutes [YYYY-MM-DD]")
