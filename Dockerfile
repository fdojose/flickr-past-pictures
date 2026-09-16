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
# The project folder is bind-mounted here (code, secrets, session, photos).
WORKDIR /app
CMD ["bash", "run.sh"]
