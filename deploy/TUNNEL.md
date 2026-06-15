# Public access via Cloudflare Tunnel → `mica.exadaktylos.xyz`

Exposes the locally-running MiCA Copilot to the public internet at **https://mica.exadaktylos.xyz**,
free, with automatic HTTPS and **no open inbound ports** on this machine.

## Architecture (why the API stays private)

```
Browser ──https──> mica.exadaktylos.xyz ──(Cloudflare edge)──> cloudflared (this PC)
                                                                   │
                                                                   ▼
                                                        Next.js app  :3000
                                                                   │  /api/* rewrite (server-side)
                                                                   ▼
                                                        FastAPI API  127.0.0.1:8000   ← localhost-only, NOT tunneled
```

- The tunnel publishes **only the Next.js app (:3000)**.
- The browser only ever talks to `mica.exadaktylos.xyz`. The UI calls `/api/*` on that same host;
  Next.js (`next.config.mjs` `rewrites`) forwards those to `127.0.0.1:8000` **server-side**.
- The FastAPI backend binds to `127.0.0.1` and is **never** in the tunnel ingress, so it is not
  reachable from the internet — only through the app. (No CORS needed: it's all same-origin.)

## What must already be running on this PC

```bash
# backend (localhost-only)
cd ~/mica-copilot && ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
# frontend  (NEXT_PUBLIC_API_URL=/api is set in frontend/.env.local)
cd ~/mica-copilot/frontend && npm run dev      # or: npm run build && npm start  (recommended for a public demo)
```

`npm start` (a production build) is recommended over `npm run dev` for anything public — it's faster
and hides the dev overlay.

## One-time setup

### 1. Cloudflare account + add the domain  *(you, in a browser)*
1. Create a free account at https://dash.cloudflare.com.
2. **Add a site** → `exadaktylos.xyz` → choose the **Free** plan.
3. Cloudflare shows **2 nameservers** (e.g. `xxx.ns.cloudflare.com`). Copy them.

### 2. Point Namecheap at Cloudflare  *(you, at Namecheap)*
Namecheap → **Domain List** → `exadaktylos.xyz` → **Manage** → **Nameservers** → **Custom DNS** →
paste Cloudflare's 2 nameservers → save. Propagation is usually minutes, up to a few hours.
Wait until the zone shows **Active** in the Cloudflare dashboard.

> This moves DNS hosting for the whole domain to Cloudflare. Any existing records (email, other
> subdomains) must be recreated in Cloudflare's DNS tab — Cloudflare's scan imports most automatically;
> verify MX/other records carried over before relying on them.

### 3. Authenticate cloudflared  *(on this PC)*
```bash
export PATH="$HOME/.local/bin:$PATH"      # cloudflared lives here (see "PATH" below)
cloudflared tunnel login                  # opens a browser; pick the exadaktylos.xyz zone
```
This writes `~/.cloudflared/cert.pem`.

### 4. Create the tunnel + DNS route  *(one command — provided)*
```bash
bash ~/mica-copilot/deploy/cloudflared-setup.sh
```
Creates the `mica` tunnel, writes `~/.cloudflared/config.yml` (ingress → :3000 only), and adds the
`mica.exadaktylos.xyz` DNS record.

### 5. Run it
```bash
cloudflared tunnel run mica       # foreground test → open https://mica.exadaktylos.xyz
```

## Run as a service (keep it up)

`cloudflared` can install itself as a systemd service (needs sudo):
```bash
sudo cloudflared --config ~/.cloudflared/config.yml service install
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared
```
Alternatively, a user-level unit at `~/.config/systemd/user/cloudflared.service`:
```ini
[Unit]
Description=cloudflared tunnel (mica)
After=network-online.target
[Service]
ExecStart=%h/.local/bin/cloudflared tunnel run mica
Restart=always
RestartSec=5
[Install]
WantedBy=default.target
```
then `systemctl --user enable --now cloudflared` (and `loginctl enable-linger $USER` so it survives logout).

## PATH

`cloudflared` is at `~/.local/bin/cloudflared`, which isn't on your zsh PATH. Either call it by full
path, or add once:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

## Resilience — deployed as systemd user services

All three processes run as **systemd user services** (`deploy/systemd/*.service`, installed to
`~/.config/systemd/user/`) with `Restart=always`, enabled at boot, with user **lingering** on
(`loginctl enable-linger work`) so they survive logout and reboot. The Postgres/pgvector container is
set to `--restart unless-stopped` and `docker.service` is enabled at boot.

| Unit | What | Restart |
|---|---|---|
| `mica-api.service` | `uvicorn app.main:app` on `127.0.0.1:8000` | always |
| `mica-web.service` | `npm run dev` (Next.js) on `:3000` | always |
| `mica-tunnel.service` | `cloudflared tunnel run` (token from `~/.cloudflared/tunnel.env`, 0600) | always |

Install / manage:
```bash
cp deploy/systemd/*.service ~/.config/systemd/user/
# create the token env file (not in the repo):
printf 'TUNNEL_TOKEN=%s\n' '<your-tunnel-token>' > ~/.cloudflared/tunnel.env && chmod 600 ~/.cloudflared/tunnel.env
loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable --now mica-api mica-web mica-tunnel

systemctl --user status mica-web            # health
journalctl --user -u mica-tunnel -f         # live logs
systemctl --user restart mica-api           # manual restart
```
Crash → systemd respawns in ≤5s. Reboot → linger + `enabled` bring all three up (uvicorn retries
until the DB container is ready). Verified by `SIGKILL`-ing each process and confirming respawn.

## Teardown
```bash
cloudflared tunnel route dns --overwrite-dns mica  # (or delete the DNS record in the dashboard)
cloudflared tunnel delete mica
```
