#!/usr/bin/env bash
# Finalize the Cloudflare Tunnel for micacopilot.exadaktylos.xyz.
#
# Run this AFTER `cloudflared tunnel login` (which authorises the exadaktylos.xyz zone and
# drops ~/.cloudflared/cert.pem). It is idempotent: re-running reuses the existing tunnel.
#
#   bash deploy/cloudflared-setup.sh
#
# It creates a named tunnel "mica", writes ~/.cloudflared/config.yml (ingress: the hostname
# → the local Next.js app on :3000, and NOTHING else — the FastAPI :8000 stays private,
# reachable only via the app's same-origin /api proxy), and creates the DNS route.
set -euo pipefail

TUNNEL_NAME="mica"
HOSTNAME="micacopilot.exadaktylos.xyz"
APP_URL="http://localhost:3000"
CFDIR="$HOME/.cloudflared"
CLOUDFLARED="$(command -v cloudflared || echo "$HOME/.local/bin/cloudflared")"

[ -f "$CFDIR/cert.pem" ] || { echo "✗ $CFDIR/cert.pem not found. Run: $CLOUDFLARED tunnel login"; exit 1; }

# Create the tunnel if it doesn't already exist, then resolve its UUID + credentials file.
if ! "$CLOUDFLARED" tunnel list -o json 2>/dev/null | grep -q "\"name\":\"$TUNNEL_NAME\""; then
  echo "→ creating tunnel '$TUNNEL_NAME'…"
  "$CLOUDFLARED" tunnel create "$TUNNEL_NAME"
else
  echo "→ tunnel '$TUNNEL_NAME' already exists; reusing."
fi

UUID="$("$CLOUDFLARED" tunnel list -o json | python3 -c "import sys,json;print(next(t['id'] for t in json.load(sys.stdin) if t['name']=='$TUNNEL_NAME'))")"
CREDS="$CFDIR/$UUID.json"
echo "→ tunnel UUID: $UUID"

cat > "$CFDIR/config.yml" <<YAML
tunnel: $UUID
credentials-file: $CREDS

ingress:
  # Public UI. The FastAPI backend (:8000) is intentionally NOT listed here — it is reached
  # only through the app's server-side /api proxy, so it is never exposed to the internet.
  - hostname: $HOSTNAME
    service: $APP_URL
  - service: http_status:404
YAML
echo "→ wrote $CFDIR/config.yml"

echo "→ creating DNS route $HOSTNAME → tunnel…"
"$CLOUDFLARED" tunnel route dns "$TUNNEL_NAME" "$HOSTNAME" || \
  echo "  (route may already exist, or the zone isn't Active on Cloudflare yet — that's fine)"

echo
echo "✓ Tunnel configured. Test it in the foreground with:"
echo "    $CLOUDFLARED tunnel run $TUNNEL_NAME"
echo "  then open https://$HOSTNAME"
echo
echo "  To keep it running as a background service, see deploy/TUNNEL.md (§ Run as a service)."
