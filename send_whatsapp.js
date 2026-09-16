/**
 * Send downloaded photos to all WhatsApp recipients defined in contacts.json.
 *
 * Usage:
 *   node send_whatsapp.js <folder>     send every image under <folder> (recursive)
 *   node send_whatsapp.js --link       link this machine once: writes the QR code to
 *                                      whatsapp_qr.png (and prints it) until it is scanned
 *
 * Recipients are read from contacts.json in the same directory:
 *   { "me": "34612345678", "kid1": "34698765432" }
 *   Numbers must be in international format without + or spaces.
 *
 * First run: link with --link and scan the QR with WhatsApp on your phone
 * (Settings → Linked Devices → Link a Device). The session is saved in
 * .wwebjs_auth/ and reused on subsequent runs.
 *
 * Environment:
 *   PUPPETEER_EXECUTABLE_PATH   use this Chromium instead of puppeteer's bundled one
 *                               (set in the casa.local image to /usr/bin/chromium)
 *
 * Example:
 *   node send_whatsapp.js downloads/04/04
 */

const { Client, LocalAuth, MessageMedia } = require("whatsapp-web.js");
const qrcodeTerminal = require("qrcode-terminal");
const QRCode = require("qrcode");
const fs = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// Logging
// ---------------------------------------------------------------------------

const LOG_FILE = path.join(__dirname, "send_whatsapp.log");
const QR_FILE = path.join(__dirname, "whatsapp_qr.png");

function log(level, msg) {
  const line = `${new Date().toISOString()} [${level}] ${msg}`;
  console.log(line);
  fs.appendFileSync(LOG_FILE, line + "\n");
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Delay between individual image sends (ms) to avoid WhatsApp rate limiting
const SEND_DELAY_MS = 2000;

// ---------------------------------------------------------------------------
// Arguments
// ---------------------------------------------------------------------------

const [, , folder] = process.argv;
const LINK_MODE = folder === "--link";

if (!folder) {
  console.error("Usage: node send_whatsapp.js <folder> | --link");
  console.error("  folder  e.g. downloads/04/04");
  process.exit(1);
}

if (!LINK_MODE && !fs.existsSync(folder)) {
  console.error(`Folder not found: ${folder}`);
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Recipients from contacts.json
// ---------------------------------------------------------------------------

let contactEntries = [];
if (!LINK_MODE) {
  const contactsFile = path.join(__dirname, "contacts.json");
  if (!fs.existsSync(contactsFile)) {
    console.error("contacts.json not found. Create it with your recipients.");
    process.exit(1);
  }

  const contacts = JSON.parse(fs.readFileSync(contactsFile, "utf8"));
  contactEntries = Object.entries(contacts);

  if (contactEntries.length === 0) {
    console.error("No recipients found in contacts.json.");
    process.exit(1);
  }

  log("INFO", `Recipients: ${contactEntries.map(([name]) => name).join(", ")}`);
}

// ---------------------------------------------------------------------------
// Collect image files recursively
// ---------------------------------------------------------------------------

const IMAGE_EXTENSIONS = new Set([".jpg", ".jpeg", ".png", ".gif"]);

function collectImages(dir) {
  const results = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...collectImages(fullPath));
    } else if (IMAGE_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) {
      results.push(fullPath);
    }
  }
  return results;
}

let images = [];
if (!LINK_MODE) {
  images = collectImages(folder);

  if (images.length === 0) {
    console.error(`No images found in: ${folder}`);
    process.exit(1);
  }

  log("INFO", `Found ${images.length} image(s) in ${folder}`);
}

// ---------------------------------------------------------------------------
// WhatsApp client
// ---------------------------------------------------------------------------

const puppeteerOptions = {
  headless: true,
  args: [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
  ],
};
if (process.env.PUPPETEER_EXECUTABLE_PATH) {
  puppeteerOptions.executablePath = process.env.PUPPETEER_EXECUTABLE_PATH;
}

const client = new Client({
  authStrategy: new LocalAuth(),
  puppeteer: puppeteerOptions,
});

let qrCount = 0;

client.on("qr", (qr) => {
  if (LINK_MODE) {
    qrCount += 1;
    QRCode.toFile(QR_FILE, qr, { scale: 8, margin: 2 })
      .then(() => log("INFO", `QR #${qrCount} written to ${QR_FILE} — scan it with WhatsApp (Settings → Linked Devices → Link a Device).`))
      .catch((err) => log("WARN", `Could not write ${QR_FILE}: ${err.message}`));
    qrcodeTerminal.generate(qr, { small: true });
    return;
  }
  log("ERROR", "WhatsApp session expired — QR scan required. Run `node send_whatsapp.js --link` to re-authenticate, then the scheduler will work again.");
  // Exit directly: destroy() while the client is still injecting only produces a puppeteer stack trace.
  setTimeout(() => process.exit(1), 500);
});

client.on("authenticated", () => {
  log("INFO", "Authenticated — session saved for future runs.");
});

client.on("auth_failure", (msg) => {
  log("ERROR", `Authentication failed: ${msg}`);
  process.exit(1);
});

client.on("ready", async () => {
  clearTimeout(initTimeout);
  log("INFO", "WhatsApp client ready.");

  if (LINK_MODE) {
    // Give the browser profile a moment to flush the session to disk before closing.
    await sleep(10_000);
    if (fs.existsSync(QR_FILE)) fs.unlinkSync(QR_FILE);
    log("INFO", "Linked. Session saved in .wwebjs_auth/ — the scheduled runs can now send.");
    await client.destroy();
    process.exit(0);
  }

  for (const [name, rawPhone] of contactEntries) {
    const normalized = rawPhone.replace(/[+\s]/g, "");
    log("INFO", `Resolving number for ${name} (${rawPhone})...`);
    const numberId = await client.getNumberId(normalized);
    if (!numberId) {
      log("WARN", `${name} (${rawPhone}) is not on WhatsApp — skipping.`);
      continue;
    }
    const chatId = numberId._serialized;
    log("INFO", `Resolved chatId: ${chatId}`);
    log("INFO", `Sending ${images.length} image(s) to ${name}...`);

    for (const imagePath of images) {
      const caption = path.relative(folder, imagePath);
      try {
        log("INFO", `  Sending: ${caption}`);
        const media = MessageMedia.fromFilePath(imagePath);
        log("INFO", `  Media loaded — mimeType: ${media.mimetype}, size: ${Buffer.from(media.data, "base64").length} bytes`);
        await client.sendMessage(chatId, media, { caption });
        log("INFO", `  OK: ${caption}`);
      } catch (err) {
        log("ERROR", `  Failed: ${caption} — ${err.message}\n${err.stack}`);
      }
      await sleep(SEND_DELAY_MS);
    }
  }

  log("INFO", "All done. Closing session...");
  await client.destroy();
  process.exit(0);
});

client.on("disconnected", (reason) => {
  log("WARN", `Disconnected: ${reason}`);
  process.exit(1);
});

// Fail if WhatsApp doesn't connect in time (linking gets longer: QR codes refresh while you scan)
const INIT_TIMEOUT_MS = LINK_MODE ? 600_000 : 120_000;
const initTimeout = setTimeout(() => {
  log("ERROR", `Timed out waiting for WhatsApp to be ready (${INIT_TIMEOUT_MS / 1000}s). Try again or delete .wwebjs_auth/ to force a fresh login.`);
  client.destroy().finally(() => process.exit(1));
}, INIT_TIMEOUT_MS);

client.initialize();
