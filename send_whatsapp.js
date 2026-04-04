/**
 * Send downloaded photos to all WhatsApp recipients defined in contacts.json.
 *
 * Usage:
 *   node send_whatsapp.js <folder>
 *
 * Arguments:
 *   folder  Path to a folder whose images will be sent (jpg, jpeg, png, gif).
 *           Subfolders are searched recursively.
 *
 * Recipients are read from contacts.json in the same directory:
 *   { "me": "34612345678", "kid1": "34698765432" }
 *   Numbers must be in international format without + or spaces.
 *
 * First run: a QR code will be printed in the terminal — scan it with
 * WhatsApp on your phone (Settings → Linked Devices → Link a Device).
 * The session is saved in .wwebjs_auth/ and reused on subsequent runs.
 *
 * Example:
 *   node send_whatsapp.js downloads/04/04
 */

const { Client, LocalAuth, MessageMedia } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const fs = require("fs");
const path = require("path");

// ---------------------------------------------------------------------------
// Logging
// ---------------------------------------------------------------------------

const LOG_FILE = path.join(__dirname, "send_whatsapp.log");

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

if (!folder) {
  console.error("Usage: node send_whatsapp.js <folder>");
  console.error("  folder  e.g. downloads/04/04");
  process.exit(1);
}

if (!fs.existsSync(folder)) {
  console.error(`Folder not found: ${folder}`);
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Recipients from contacts.json
// ---------------------------------------------------------------------------

const contactsFile = path.join(__dirname, "contacts.json");
if (!fs.existsSync(contactsFile)) {
  console.error("contacts.json not found. Create it with your recipients.");
  process.exit(1);
}

const contacts = JSON.parse(fs.readFileSync(contactsFile, "utf8"));
const contactEntries = Object.entries(contacts);

if (contactEntries.length === 0) {
  console.error("No recipients found in contacts.json.");
  process.exit(1);
}

log("INFO", `Recipients: ${contactEntries.map(([name]) => name).join(", ")}`);

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

const images = collectImages(folder);

if (images.length === 0) {
  console.error(`No images found in: ${folder}`);
  process.exit(1);
}

log("INFO", `Found ${images.length} image(s) in ${folder}`);;

// ---------------------------------------------------------------------------
// WhatsApp client
// ---------------------------------------------------------------------------

const client = new Client({
  authStrategy: new LocalAuth(),
  puppeteer: {
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  },
});

client.on("qr", (qr) => {
  log("INFO", "QR code ready — scan with WhatsApp (Settings → Linked Devices → Link a Device)");
  qrcode.generate(qr, { small: true });
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

// Fail fast if WhatsApp doesn't connect within 60 seconds
const initTimeout = setTimeout(() => {
  log("ERROR", "Timed out waiting for WhatsApp to be ready (60s). Try again or delete .wwebjs_auth/ to force a fresh login.");
  client.destroy().finally(() => process.exit(1));
}, 60_000);

client.initialize();
