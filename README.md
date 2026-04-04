# Flickr Past Pictures

Downloads photos from your Flickr account taken on the same weekday reference (e.g. 1st Saturday of April) across multiple past years, and sends them to WhatsApp contacts.

## How it works

Every day at a configured time:
1. Finds the equivalent weekday anchor in past years (1, 5, 10, 15, 20 years ago)
2. Downloads up to N photos per year from your Flickr account (including private photos)
3. Sends them via WhatsApp to the contacts in `contacts.json`

## Requirements

- Python 3 with `requests` and `requests-oauthlib`
- Node.js (arm64 recommended on Apple Silicon)
- A Flickr account with API credentials
- WhatsApp linked device session

```bash
pip install requests requests-oauthlib
npm install
```

## Setup

### 1. Flickr API credentials

Copy the example file and fill in your credentials from [flickr.com/services/apps](https://www.flickr.com/services/apps):

```bash
cp flickr_api_key.txt.example flickr_api_key.txt
```

`flickr_api_key.txt`:
```
YOUR_API_KEY
YOUR_API_SECRET
```

### 2. Flickr OAuth (for private photos)

Find your Flickr NSID at [flickr.com/services/api/misc.nsid.html](https://www.flickr.com/services/api/misc.nsid.html) and run the two-step auth flow:

```bash
# Step 1 — prints an authorization URL
python3 download_flickr_pictures.py --user-id YOUR_NSID --authenticate

# Step 2 — paste the code shown by Flickr
python3 download_flickr_pictures.py --user-id YOUR_NSID --verify CODE
```

The access token is saved to `flickr_oauth.json` and reused automatically.

### 3. WhatsApp contacts

```bash
cp contacts.json.example contacts.json
```

Edit `contacts.json` with international phone numbers (no spaces):
```json
{
  "me":   "+56912345678",
  "kid1": "+56987654321"
}
```

### 4. WhatsApp session (first run only)

Scan the QR code once to link the session:

```bash
node send_whatsapp.js downloads/MM/DD
```

The session is saved to `.wwebjs_auth/` and reused on subsequent runs.

### 5. Scheduler

Configure the daily schedule in `config.py`, then run the setup script once:

```bash
./setup_scheduler.sh
```

This registers a `launchd` agent and sets a `pmset` wake schedule so your Mac wakes automatically at the configured time.

## Configuration

All options are in `config.py`:

```python
SCHEDULE_HOUR   = 8       # Daily run time (local time, 24h)
SCHEDULE_MINUTE = 0

USER_ID = "12345678@N00"  # Your Flickr NSID

DATE_STRATEGY = "nth_weekday"  # "nth_weekday" or "exact"
YEARS_AGO     = [1, 5, 10, 15, 20]
MAX_PHOTOS    = 5
SELECTION     = "random"  # "random", "first", "last", or "views"
```

**DATE_STRATEGY:**
- `nth_weekday` — matches the same occurrence of the weekday in the month (e.g. 1st Saturday → 1st Saturday). Better for lifestyle patterns.
- `exact` — matches the exact calendar day (Apr 4 → Apr 4).

**SELECTION:**
- `random` — randomly picks N from all results
- `first` — earliest taken that day
- `last` — latest taken that day
- `views` — most viewed photos

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

## File structure

```
config.py                   — all configuration
download_flickr_pictures.py — Flickr downloader
send_whatsapp.js            — WhatsApp sender
run.sh                      — full pipeline
setup_scheduler.sh          — configure launchd + pmset

flickr_api_key.txt          — API key + secret (not in git)
flickr_oauth.json           — OAuth access token (not in git)
contacts.json               — WhatsApp recipients (not in git)
.wwebjs_auth/               — WhatsApp session (not in git)
downloads/                  — downloaded photos (not in git)
```

## Scheduler management

```bash
# Apply schedule changes from config.py
./setup_scheduler.sh

# Trigger manually without waiting for scheduled time
launchctl start com.maccasa.flickr-past-pictures

# Disable
launchctl unload ~/Library/LaunchAgents/com.maccasa.flickr-past-pictures.plist

# View logs
tail -f launchd.log
tail -f send_whatsapp.log
```
