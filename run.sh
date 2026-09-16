#!/usr/bin/env bash
# Download past Flickr photos, refresh today/, notify Home Assistant, send them via WhatsApp.
# Runs on macOS (launchd) or inside the casa.local container (cron → docker compose run).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ "$(uname)" == "Darwin" ]]; then
  # launchd has a minimal PATH: use the framework Python and the arm64 node from nvm
  export NVM_DIR="$HOME/.nvm"
  [ -s "/usr/local/opt/nvm/nvm.sh" ] && source "/usr/local/opt/nvm/nvm.sh"
  PYTHON="${PYTHON:-/Library/Frameworks/Python.framework/Versions/3.11/bin/python3}"
fi
PYTHON="${PYTHON:-python3}"

OUTPUT="downloads"
TODAY_DIR="today"     # flat copy of today's photos (YYYY_ prefix); Home Assistant shows this folder

echo "=== $(date '+%Y-%m-%d %H:%M:%S') Downloading photos ==="
"$PYTHON" download_flickr_pictures.py --output "$OUTPUT"

# Today's MM/DD folder (matches what the Python script creates)
FOLDER="$OUTPUT/$(date +%m)/$(date +%d)"

# Refresh today/ so the Home Assistant gallery always points at a fixed path
rm -rf "$TODAY_DIR"
mkdir -p "$TODAY_DIR"
COUNT=0
if [ -d "$FOLDER" ]; then
  while IFS= read -r -d '' f; do
    year="$(basename "$(dirname "$f")")"
    cp "$f" "$TODAY_DIR/${year}_$(basename "$f")"
    COUNT=$((COUNT + 1))
  done < <(find "$FOLDER" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.gif' \) -print0 | sort -z)
fi
FIRST="$(ls "$TODAY_DIR" 2>/dev/null | head -n 1)"
echo "$TODAY_DIR/: $COUNT photo(s)"

# Tell Home Assistant (webhook automation → phone notification). Optional, never fatal.
if [ -n "${HA_WEBHOOK_URL:-}" ]; then
  PAYLOAD="$("$PYTHON" -c 'import json,sys,datetime; print(json.dumps({"count": int(sys.argv[1]), "first": sys.argv[2], "date": datetime.date.today().isoformat()}))' "$COUNT" "$FIRST")"
  if curl -s -m 10 -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d "$PAYLOAD" "$HA_WEBHOOK_URL" | grep -q '^200$'; then
    echo "Home Assistant notified."
  else
    echo "Home Assistant webhook failed (ignored)." >&2
  fi
fi

if [ "$COUNT" -eq 0 ]; then
  echo "No photos downloaded — skipping WhatsApp send."
  exit 0
fi

echo ""
echo "=== Sending via WhatsApp ==="
# Retry once if the first attempt times out or fails
if ! node send_whatsapp.js "$FOLDER"; then
  echo "First attempt failed, retrying once..."
  sleep 5
  node send_whatsapp.js "$FOLDER"
fi
