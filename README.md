# tristandickson.github.io

Hosts the Tesla Fleet API public key for a personal Powerwall app, and the one-off setup scripts that register the apps and mint the owner refresh tokens for Tesla and Enphase, plus a reader for the myenergi Zappi.

## Layout

- `.well-known/appspecific/com.tesla.3p.public-key.pem`: the public half of the EC P-256 key Tesla requires at this path on the app's domain.
- `tesla_fleet.py`: registers the partner account, builds the login URL, exchanges the code, lists products and pulls a day of energy history. Stdlib only.
- `enphase.py`: builds the Enphase API v4 login URL, exchanges the code, lists systems and pulls a day of 5-minute production. Stdlib only.
- `zappi.py`: live status and a day of hourly or per-minute history from the myenergi cloud API, with the energy fields totalled in kWh. Stdlib only.

## Usage

```bash
export TESLA_CLIENT_ID=... TESLA_CLIENT_SECRET=...
export TESLA_DOMAIN=tristandickson.github.io TESLA_REDIRECT_URI=https://tristandickson.github.io/tesla-callback
python3 tesla_fleet.py register          # once
python3 tesla_fleet.py auth-url          # open, log in, approve, copy the code from the address bar
python3 tesla_fleet.py exchange <code>
python3 tesla_fleet.py products          # prints the energy_site_id
python3 tesla_fleet.py history [YYYY-MM-DD]   # a local day of 5-minute Wh buckets: solar, battery, grid, home; TESLA_KIND=power for 5-minute W samples
```

```bash
export ENPHASE_API_KEY=... ENPHASE_CLIENT_ID=... ENPHASE_CLIENT_SECRET=...
python3 enphase.py auth-url              # open, log in as the homeowner, approve, copy the code the page shows
python3 enphase.py exchange <code>
python3 enphase.py systems               # prints the system_id
python3 enphase.py production            # yesterday's production in 5-minute buckets
python3 enphase.py lifetime              # daily totals for the last week
```

```bash
export MYENERGI_HUB_SERIAL=... MYENERGI_API_KEY=...   # gateway device serial; key from myaccount, Products, Advanced
python3 zappi.py status                  # every device on the hub right now
python3 zappi.py hours [YYYY-MM-DD]      # 24 hourly rows, yesterday by default
python3 zappi.py minutes [YYYY-MM-DD]    # 1441 per-minute rows
```

Tokens are written to `~/.tesla-fleet/tokens.json` and `~/.tesla-fleet/enphase-tokens.json`, and the private key lives at `~/.tesla-fleet/tesla-private.pem`. None of them are in this repo. A local `env` file holding the exports is gitignored.
