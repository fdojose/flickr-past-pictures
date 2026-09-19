# Runtime for flickr_past_pictures on casa.local (Debian, Docker only, no sudo).
# Node 22 + Debian's Chromium for whatsapp-web.js, Debian's Python 3 for the Flickr downloader.
FROM node:22-bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium fonts-liberation ca-certificates curl tzdata \
        python3 python3-requests python3-requests-oauthlib \
    && rm -rf /var/lib/apt/lists/*
# whatsapp-web.js pulls puppeteer; we use the system Chromium instead of its download.
ENV PUPPETEER_SKIP_DOWNLOAD=1 \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    NODE_PATH=/opt/wa/node_modules
WORKDIR /opt/wa
COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund && npm cache clean --force
# WhatsApp Web build 2.3000.1047xxx (2026-09-17) breaks every media send in whatsapp-web.js 1.34.7:
# "Data passed to getter must include an id property". Upstream fix, not released yet:
# https://github.com/wwebjs/whatsapp-web.js/pull/201923 (delete the media model's __x_id before it
# overwrites the outgoing Msg id). Applied here until a fixed version is published; the build fails
# loudly if the file no longer matches so the patch is not silently skipped.
RUN node -e '\
  const fs = require("fs"); const f = "/opt/wa/node_modules/whatsapp-web.js/src/util/Injected/Utils.js"; \
  let s = fs.readFileSync(f, "utf8"); \
  const anchor = "        // Bot\x27s won\x27t reply if canonicalUrl is set (linking)\n"; \
  if (s.includes("delete message.__x_id")) { console.log("wwebjs patch already present"); process.exit(0); } \
  if (s.split(anchor).length !== 2) { console.error("wwebjs patch anchor not found: review PR 201923 against this version"); process.exit(1); } \
  s = s.replace(anchor, "        delete message.__x_id; // PR 201923: MediaData.__x_id must not overwrite the Msg id\n\n" + anchor); \
  fs.writeFileSync(f, s); console.log("wwebjs patch applied");'
# The project folder is bind-mounted here (code, secrets, session, photos).
WORKDIR /app
CMD ["bash", "run.sh"]
