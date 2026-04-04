# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the script

```bash
python download_flickr_pictures.py \
    --user-id 12345678@N00 \
    --api-key-file flickr_api_key.txt \
    --output ./downloads
```

Dependencies: `pip install requests`

## What this does

Single-script CLI tool that downloads up to 5 Flickr photos taken on the same calendar day and month one year ago from a given user account. It uses the public `flickr.photos.search` REST API endpoint (no OAuth — only public photos).

## Key design details

- **API key**: Read from `flickr_api_key.txt` (first line only). The file is gitignored by convention; never commit it.
- **Date logic**: Computes `today - 1 year`, with a Feb 29 fallback to Feb 28.
- **URL selection**: `choose_best_url()` prefers highest-resolution size (`url_o` → `url_k` → `url_h` → `url_l` → `url_c` → `url_b` → `url_m`). The `extras` param in the API call must list any size suffixes needed.
- **Filename format**: `{photo_id}_{sanitized_title}.jpg` saved into `--output` dir (default: `downloads/`).
- **Error handling**: Non-fatal per-photo errors (missing URL, download failure) print to stderr and continue; fatal errors (API key missing, search failure) exit with code 1.
