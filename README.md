# Flickr Past Pictures

Downloads photos from your Flickr account taken on the same weekday reference (e.g. 1st Saturday of April) across multiple past years, and sends them to WhatsApp contacts daily.

> **macOS only.** Scheduler relies on `launchd` and `pmset`.

## How it works

Every day at a configured time:
1. Finds the equivalent weekday anchor in past years (1, 5, 10, 15, 20 years ago)
2. Downloads up to N photos per year from your Flickr account (public and private)
3. Skips photos already downloaded (deduplication by photo ID)
4. Sends them via WhatsApp to everyone in `contacts.json`

## Requirements

- Python 3
- Node.js (arm64 build recommended on Apple Silicon)
- A Flickr account with API credentials
- WhatsApp account

```bash
pip install requests requests-oauthlib
npm install
```

## First-time setup

### 1. Flickr API credentials

Get your API key and secret from [flickr.com/services/apps](https://www.flickr.com/services/apps):

```bash
cp flickr_api_key.txt.example flickr_api_key.txt
```

Edit `flickr_api_key.txt`:
```
YOUR_API_KEY
YOUR_API_SECRET
```

### 2. Flickr OAuth (required for private photos)

Find your Flickr NSID at [flickr.com/services/api/misc.nsid.html](https://www.flickr.com/services/api/misc.nsid.html), then run the two-step auth flow:

```bash
# Step 1 — opens an authorization URL
python3 download_flickr_pictures.py --authenticate

# Step 2 — paste the code shown by Flickr
python3 download_flickr_pictures.py --verify CODE
```

The access token is saved to `flickr_oauth.json` and reused automatically.

### 3. WhatsApp contacts

```bash
cp contacts.json.example contacts.json
```

Edit `contacts.json` with international phone numbers:
```json
{
  "me":   "+56912345678",
  "kid1": "+56987654321"
}
```

### 4. WhatsApp session (once only)

Link the session by scanning a QR code:

```bash
node send_whatsapp.js downloads/MM/DD
```

Scan the QR with WhatsApp on your phone → **Settings → Linked Devices → Link a Device**.  
The session is saved to `.wwebjs_auth/` and reused on subsequent runs.

### 5. Scheduler

Set your preferred time in `config.py`, then run:

```bash
./setup_scheduler.sh
```

This registers a `launchd` agent and a `pmset` wake schedule so your Mac wakes automatically at the right time every day.

## Configuration

All options in `config.py`:

```python
SCHEDULE_HOUR   = 8       # Daily run time (local time, 24h)
SCHEDULE_MINUTE = 0

USER_ID = "12345678@N00"  # Your Flickr NSID

DATE_STRATEGY = "nth_weekday"  # "nth_weekday" or "exact"
YEARS_AGO     = [1, 5, 10, 15, 20]
MAX_PHOTOS    = 5
SELECTION     = "random"  # "random", "first", "last", or "views"
```

| Option | Description |
|---|---|
| `DATE_STRATEGY` | `nth_weekday` matches the same weekday occurrence (e.g. 1st Saturday → 1st Saturday across years). `exact` matches the calendar day. |
| `YEARS_AGO` | Which past years to search |
| `MAX_PHOTOS` | Max photos to download per year |
| `SELECTION` | How to pick when more are available: `random`, `first` (earliest that day), `last` (latest that day), `views` (most viewed) |

After changing `SCHEDULE_HOUR` or `SCHEDULE_MINUTE`, re-run `./setup_scheduler.sh` to apply.

## Running manually

```bash
# Full pipeline (download + send)
./run.sh

# Download only
python3 download_flickr_pictures.py --output ./downloads

# Send only
node send_whatsapp.js downloads/MM/DD
```

## Files

```
config.py                   — all configuration
download_flickr_pictures.py — Flickr downloader
send_whatsapp.js            — WhatsApp sender
run.sh                      — full pipeline
setup_scheduler.sh          — register launchd agent + pmset wake

flickr_api_key.txt          — API key + secret        (git ignored)
flickr_oauth.json           — OAuth access token      (git ignored)
contacts.json               — WhatsApp recipients     (git ignored)
.wwebjs_auth/               — WhatsApp session        (git ignored)
downloads/                  — downloaded photos       (git ignored)
send_whatsapp.log           — WhatsApp send log       (git ignored)
launchd.log                 — scheduler output log    (git ignored)
```

## Scheduler management

```bash
# Apply schedule changes from config.py
./setup_scheduler.sh

# Trigger immediately without waiting for scheduled time
launchctl start com.maccasa.flickr-past-pictures

# Disable
launchctl unload ~/Library/LaunchAgents/com.maccasa.flickr-past-pictures.plist

# Re-enable
launchctl load ~/Library/LaunchAgents/com.maccasa.flickr-past-pictures.plist

# Monitor logs
tail -f launchd.log
tail -f send_whatsapp.log
```

## Troubleshooting

### `ModuleNotFoundError: No module named 'requests'` at scheduled time

`launchd` runs with a minimal environment where `python3` on `$PATH` may not be the same binary you installed packages into. `run.sh` uses the full path `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3` to avoid this. If you upgrade Python or use a different installation, update that path in `run.sh` accordingly.

### `pmset` wake not re-scheduled after reboot

The `pmset` wake entry is one-shot — it fires once and is not automatically re-added. Re-run `./setup_scheduler.sh` after a reboot or if the Mac was shut down (not just slept) to restore the daily wake.

## Notes

- WhatsApp has no official personal API. This project uses [whatsapp-web.js](https://github.com/pedroslopez/whatsapp-web.js), an unofficial library. Use at your own discretion.
- The Mac must be in sleep (not shut down) for `pmset` to wake it.
- Photos are downloaded at original resolution when available.
