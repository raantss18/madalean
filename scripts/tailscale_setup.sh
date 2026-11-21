#!/usr/bin/env bash
# Publish Madalean's remote listener on the tailnet (HTTPS, tailnet only — never Funnel).
#
# ALTERNATIVE, not the default (ARCHITECTURE §18): Madalean embeds its own Tailscale node (madalean-net, started by
# the server, https://madalean.<tailnet>.ts.net). Use this script only if you prefer the host's system tailscaled.
#
#   scripts/tailscale_setup.sh            add the entry if missing (idempotent), print the URL
#   scripts/tailscale_setup.sh --status   show whether the entry exists and the server answers
#   scripts/tailscale_setup.sh --print    show the exact commands that would run, change nothing
#   scripts/tailscale_setup.sh --remove   remove ONLY Madalean's entry (https port 10500)
#
# Exactly one entry is managed:  tailscale serve --bg --https=10500 http://127.0.0.1:11501
# Every other `tailscale serve` entry of the machine (e.g. other projects on 443, 80, 10005–10447) is left
# untouched: this script never runs `tailscale serve reset`, never touches another port, never enables Funnel.
# Refuses to act if https port 10500 is already used by something else. No sudo needed when the user is the
# tailscale operator (`sudo tailscale set --operator=$USER` once, by the user, otherwise).
set -euo pipefail

TS_PORT="${MADALEAN_TS_PORT:-10500}"
BACKEND="${MADALEAN_REMOTE_BACKEND:-http://127.0.0.1:11501}"
TS="${TAILSCALE:-tailscale}"
MODE="apply"
case "${1:-}" in
  "") ;;
  --status) MODE=status ;;
  --print|--dry-run) MODE=print ;;
  --remove) MODE=remove ;;
  -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
  *) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
esac

die() { echo "error: $*" >&2; exit 1; }
command -v "$TS" >/dev/null || die "tailscale is not installed (https://tailscale.com/download/linux)"
command -v python3 >/dev/null || die "python3 is needed to read tailscale's JSON"

STATUS_JSON="$("$TS" status --json 2>/dev/null)" || die "tailscale is not running (start it: sudo systemctl enable --now tailscaled; tailscale up)"
read -r STATE DNS CERT <<<"$(python3 -c '
import json, sys
d = json.loads(sys.argv[1])
dns = (d.get("Self") or {}).get("DNSName", "").rstrip(".")
certs = d.get("CertDomains") or []
print(d.get("BackendState", "?"), dns or "-", "yes" if dns in certs else "no")
' "$STATUS_JSON")"
[ "$STATE" = "Running" ] || die "tailscale is not connected (state: $STATE). Run: tailscale up"
[ "$DNS" != "-" ] || die "this machine has no MagicDNS name. Enable MagicDNS in the admin console (DNS page)."

explain_https() {
  cat >&2 <<TXT
HTTPS certificates are not enabled for this tailnet, so https://$DNS:$TS_PORT cannot get a valid certificate.
Prerequisites (once, in https://login.tailscale.com/admin/dns):
  1. MagicDNS: enabled.
  2. HTTPS Certificates: click "Enable HTTPS".
Then re-run this script. (The certificate is issued by Let's Encrypt for $DNS; devices must use that full name.)
TXT
}

SERVE_JSON="$("$TS" serve status --json 2>/dev/null || echo '{}')"
# Classify port $TS_PORT: free | ours | other:<description> ; also report Funnel on it.
read -r SLOT FUNNEL <<<"$(python3 -c '
import json, sys
d = json.loads(sys.argv[1] or "{}")
port, dns, backend = sys.argv[2], sys.argv[3], sys.argv[4]
tcp = (d.get("TCP") or {}).get(port)
web = None
for hp, v in (d.get("Web") or {}).items():
    if hp.rsplit(":", 1)[-1] == port:
        web = v
funnel = any(k.rsplit(":", 1)[-1] == port and v for k, v in (d.get("AllowFunnel") or {}).items())
if tcp is None and web is None:
    slot = "free"
else:
    handlers = (web or {}).get("Handlers") or {}
    ok = bool(tcp and tcp.get("HTTPS")) and list(handlers) == ["/"] and handlers["/"].get("Proxy") == backend
    if ok:
        slot = "ours"
    else:
        desc = ",".join(p + "->" + str(h.get("Proxy") or h.get("Path") or ("text" if h.get("Text") else "?")) for p, h in handlers.items())
        if tcp and not tcp.get("HTTPS"):
            desc = "tcp->" + str(tcp.get("TCPForward") or "?")
        slot = "other:" + (desc or "unknown").replace(" ", "_")
print(slot, "funnel" if funnel else "nofunnel")
' "$SERVE_JSON" "$TS_PORT" "$DNS" "$BACKEND")"

[ -n "${SLOT:-}" ] || die "could not read 'tailscale serve status --json'"

URL="https://$DNS:$TS_PORT"
ADD_CMD=("$TS" serve --bg "--https=$TS_PORT" "$BACKEND")
DEL_CMD=("$TS" serve "--https=$TS_PORT" off)

hint() {
  echo "Madalean URL (tailnet only): $URL"
  echo "Pair link pattern (the host UI shows it with the current code and a QR code):"
  echo "  madalean://pair?host=$DNS:$TS_PORT&code=<6-digit code>"
}

backend_check() {
  if command -v curl >/dev/null; then
    if curl -fsS -m 3 "$BACKEND/api/hello" >/dev/null 2>&1; then echo "backend $BACKEND: answering"
    else echo "backend $BACKEND: not answering (is 'madalean serve' running?)"; fi
  fi
}

[ "$FUNNEL" = "funnel" ] && die "Funnel is ON for port $TS_PORT: Madalean must never be public. Turn it off: $TS funnel --https=$TS_PORT off"

case "$MODE" in
  status)
    echo "tailscale: $STATE, name $DNS, HTTPS certificates: $CERT"
    case "$SLOT" in
      ours) echo "serve entry: present ($URL -> $BACKEND)" ;;
      free) echo "serve entry: absent (run: $0)" ;;
      other:*) echo "serve entry: port $TS_PORT is used by something else (${SLOT#other:}) — not Madalean's" ;;
    esac
    backend_check
    [ "$CERT" = "yes" ] || explain_https
    hint
    ;;
  print)
    echo "# tailscale: $STATE, name $DNS, HTTPS certificates: $CERT, port $TS_PORT: $SLOT"
    case "$SLOT" in
      free) echo "# would run:"; printf '%q ' "${ADD_CMD[@]}"; echo ;;
      ours) echo "# already present, nothing to do (idempotent)" ;;
      other:*) echo "# would REFUSE: port $TS_PORT already serves ${SLOT#other:}" ;;
    esac
    echo "# removal (--remove) would run:"; printf '%q ' "${DEL_CMD[@]}"; echo
    [ "$CERT" = "yes" ] || explain_https
    hint
    ;;
  apply)
    [ "$CERT" = "yes" ] || { explain_https; exit 1; }
    case "$SLOT" in
      ours) echo "Already configured (nothing changed)." ;;
      free) "${ADD_CMD[@]}" >/dev/null; echo "Added: $URL -> $BACKEND" ;;
      other:*) die "https port $TS_PORT is already used by another service (${SLOT#other:}); refusing to change it" ;;
    esac
    backend_check
    hint
    ;;
  remove)
    case "$SLOT" in
      ours) "${DEL_CMD[@]}" >/dev/null; echo "Removed Madalean's entry ($URL). Other serve entries untouched." ;;
      free) echo "No Madalean entry on port $TS_PORT (nothing changed)." ;;
      other:*) die "port $TS_PORT serves something that is not Madalean's (${SLOT#other:}); not removing it" ;;
    esac
    ;;
esac
