#!/usr/bin/env bash
# Configure launchd and pmset to run the daily photo script at the time
# defined by SCHEDULE_HOUR and SCHEDULE_MINUTE in config.py.
#
# Run once (or again whenever you change the schedule in config.py):
#   ./setup_scheduler.sh
#
# Requires sudo for pmset (wake scheduling).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# Read schedule from config.py
# ---------------------------------------------------------------------------

HOUR=$(python3 -c "import config; print(config.SCHEDULE_HOUR)")
MINUTE=$(python3 -c "import config; print(config.SCHEDULE_MINUTE)")
TIME_LABEL=$(printf "%02d:%02d" "$HOUR" "$MINUTE")

echo "Configuring daily schedule at ${TIME_LABEL} (local time)..."

# ---------------------------------------------------------------------------
# Write launchd plist
# ---------------------------------------------------------------------------

PLIST="$HOME/Library/LaunchAgents/com.maccasa.flickr-past-pictures.plist"

cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.maccasa.flickr-past-pictures</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${SCRIPT_DIR}/run.sh</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>${HOUR}</integer>
        <key>Minute</key>
        <integer>${MINUTE}</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>${SCRIPT_DIR}/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>${SCRIPT_DIR}/launchd.log</string>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

echo "  Plist written to $PLIST"

# ---------------------------------------------------------------------------
# Reload launchd agent
# ---------------------------------------------------------------------------

if launchctl list | grep -q "com.maccasa.flickr-past-pictures"; then
    launchctl unload "$PLIST"
    echo "  Unloaded existing launchd agent."
fi

launchctl load "$PLIST"
echo "  launchd agent loaded — will run daily at ${TIME_LABEL}."

# ---------------------------------------------------------------------------
# Set pmset wake schedule (requires sudo)
# ---------------------------------------------------------------------------

WAKE_TIME=$(printf "%02d:%02d:00" "$HOUR" "$MINUTE")

echo ""
echo "Setting Mac wake schedule at ${TIME_LABEL} (requires sudo)..."
sudo pmset repeat wake MTWRFSU "$WAKE_TIME"
echo "  pmset wake schedule set."

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "Done. Every day at ${TIME_LABEL}:"
echo "  1. Mac wakes from sleep (pmset)"
echo "  2. Photos download from Flickr (launchd → run.sh)"
echo "  3. Photos sent via WhatsApp"
echo ""
echo "To change the time, edit SCHEDULE_HOUR/SCHEDULE_MINUTE in config.py"
echo "and run ./setup_scheduler.sh again."
