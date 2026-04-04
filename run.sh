#!/usr/bin/env bash
# Download past Flickr photos and send them via WhatsApp.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load nvm so the arm64 node is used
export NVM_DIR="$HOME/.nvm"
[ -s "/usr/local/opt/nvm/nvm.sh" ] && source "/usr/local/opt/nvm/nvm.sh"

OUTPUT="downloads"

echo "=== Downloading photos ==="
python3 download_flickr_pictures.py --output "$OUTPUT"

# Derive today's MM/DD folder (matches what the Python script creates)
FOLDER="$OUTPUT/$(date +%m)/$(date +%d)"

if [ ! -d "$FOLDER" ] || [ -z "$(ls -A "$FOLDER")" ]; then
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
