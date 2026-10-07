# tristandickson.github.io

Hosts the Tesla Fleet API public key for a personal Powerwall app, and the one-off setup script that registers the app and mints the owner refresh token.

## Layout

- `.well-known/appspecific/com.tesla.3p.public-key.pem`: the public half of the EC P-256 key Tesla requires at this path on the app's domain.
- `tesla_fleet.py`: registers the partner account, builds the login URL, exchanges the code, lists products and pulls a day of energy history. Stdlib only.

## Usage

```bash
export TESLA_CLIENT_ID=... TESLA_CLIENT_SECRET=...
export TESLA_DOMAIN=tristandickson.github.io TESLA_REDIRECT_URI=https://tristandickson.github.io/tesla-callback
python3 tesla_fleet.py register          # once
python3 tesla_fleet.py auth-url          # open, log in, approve, copy the code from the address bar
python3 tesla_fleet.py exchange <code>
python3 tesla_fleet.py products          # prints the energy_site_id
python3 tesla_fleet.py history           # yesterday's solar, battery, grid and home energy
```

Tokens are written to `~/.tesla-fleet/tokens.json` and the private key lives at `~/.tesla-fleet/tesla-private.pem`. Neither is in this repo.
