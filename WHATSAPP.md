# send_whatsapp.js — WhatsApp sender for other scripts

`send_whatsapp.js` is a Node script that sends every image in a folder to a list of WhatsApp
contacts through the unofficial [whatsapp-web.js](https://github.com/pedroslopez/whatsapp-web.js)
library. It drives a headless Chromium logged into WhatsApp Web with a saved session: there is no
official API and no token.

## Locations

| Copy | Path | Use |
|---|---|---|
| Source of truth | `NotebooksPython/flickr_past_pictures/send_whatsapp.js` (git) | edit here, then `./deploy_to_casa.sh` |
| Runtime | `fernando@casa.local:~/flickr/send_whatsapp.js` | runs inside the `flickr-past-pictures` Docker image |

## How to call it

```bash
# on casa.local, from ~/flickr (Chromium, Node and the session live inside the container)
docker compose run --rm flickr node send_whatsapp.js <folder>
docker compose run --rm flickr node send_whatsapp.js --link
```

- `<folder>`: path relative to `~/flickr`. Every `.jpg`, `.jpeg`, `.png` and `.gif` under it
  (recursively) is sent, one message per image, with the file's relative path as caption.
  Two seconds between images to avoid rate limiting.
- `--link`: one-time pairing. Writes the QR code to `whatsapp_qr.png` next to the script, rewrites
  it as WhatsApp refreshes the code (about every 20 s, 10-minute window), exits 0 once the phone
  has scanned it. Scan from the phone: WhatsApp → Settings → Linked Devices → Link a Device.

## Inputs (read from the script's own directory)

| Item | Meaning |
|---|---|
| `contacts.json` | `{"name": "+56912345678", ...}`. Every entry receives every image. Numbers not on WhatsApp are skipped with a warning. |
| `.wwebjs_auth/` | Saved session from `--link`. Delete it to force a new pairing. |
| `PUPPETEER_EXECUTABLE_PATH` (env) | Chromium binary to use. The container sets `/usr/bin/chromium`; unset on a Mac, puppeteer's bundled Chrome is used. |

## Outputs and exit codes

- Appends timestamped lines to `send_whatsapp.log` in the same directory: one `OK:` line per
  delivered image, `Failed:` on a per-image error, `[ERROR]` lines for fatal conditions.
- **Exit 0**: all recipients processed (or `--link` succeeded).
- **Exit 1**: folder missing, no images, `contacts.json` missing or empty, session expired
  (log says "QR scan required"), authentication failure, disconnect, or no connection within
  120 s (600 s in `--link` mode).
- A per-image failure does not stop the run and does not change the exit code.

## Constraints a caller must respect

- **One process at a time.** Two runs sharing `.wwebjs_auth/` collide on the Chromium profile lock.
- **Sending only.** It does not read incoming messages or reply.
- **Session tied to the phone that scanned.** If WhatsApp unlinks the device, every run exits 1
  until `--link` is repeated. Schedule it with a fallback (as `run.sh` does: download and notify
  first, WhatsApp last, one retry) and watch the log for "QR scan required".
- **Unofficial library.** A WhatsApp Web change can break it. Bump `whatsapp-web.js` in
  `package.json` and rebuild with `./deploy_to_casa.sh --build`. Symptom to watch for in the log:
  `Failed: ... Data passed to getter must include an id property` on every image while the client
  reports ready. That was the 2026-09-17 WhatsApp Web change; the `Dockerfile` applies the upstream
  fix (wwebjs PR 201923) on top of 1.34.7 until a fixed release exists. Drop that step once
  `package.json` moves to a version that includes it.
- **Shared image.** The camera bridge on casa.local (`/opt/casa/whatsapp/server.js`, container
  `whatsapp-bridge`, controller compose project) runs on this same `flickr-past-pictures:latest`
  image with its own session. After `--build`, recreate it too:
  `cd ~/controller && docker compose up -d whatsapp-bridge`.

## Minimal example for a new caller

```bash
mkdir -p ~/flickr/outbox/report && cp chart.png ~/flickr/outbox/report/
cd ~/flickr && docker compose run --rm flickr node send_whatsapp.js outbox/report
```

If the other script lives in its own compose project, the cleaner option is to give it its own
copy of `send_whatsapp.js`, `package.json`, `contacts.json` and a separate `.wwebjs_auth/` linked
with its own `--link`, so the two jobs never share a session. The `Dockerfile` in this repo is the
reference image (Node 22, Debian Chromium, `PUPPETEER_SKIP_DOWNLOAD=1`, `NODE_PATH=/opt/wa/node_modules`).
