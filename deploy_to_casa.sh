#!/usr/bin/env bash
# Copy the code to casa.local (~/flickr) with tar over ssh (casa has no rsync).
# Secrets, the WhatsApp session, downloads/ and today/ stay on casa untouched.
#
#   ./deploy_to_casa.sh            copy files
#   ./deploy_to_casa.sh --build    copy files and rebuild the image (Dockerfile / package.json changed)
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"
TARGET="${TARGET:-fernando@casa.local}"
FILES="Dockerfile docker-compose.yml .dockerignore .env.example .gitignore CLAUDE.md README.md config.py \
contacts.json.example flickr_api_key.txt.example download_flickr_pictures.py package.json run.sh \
send_whatsapp.js setup_scheduler.sh deploy_to_casa.sh"
COPYFILE_DISABLE=1 tar --no-xattrs -cf - $FILES | ssh "$TARGET" 'mkdir -p ~/flickr/downloads ~/flickr/today && tar -xf - -C ~/flickr && rm -f ~/flickr/._*'
echo "Copied to $TARGET:~/flickr"
if [ "${1:-}" = "--build" ]; then
  ssh "$TARGET" 'cd ~/flickr && docker compose build'
fi
