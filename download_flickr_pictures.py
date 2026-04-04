"""
Command‑line utility to download photos from a Flickr account taken on a
specific date.  This tool reads API credentials from a file and downloads
the five most recent photos from the authenticated user's account that were
taken on the same day and month one year prior to today.  The photos are
saved into a local output directory.

Usage example (public photos only):

    python download_flickr_pictures.py \
        --user-id 12345678@N00 \
        --api-key-file flickr_api_key.txt \
        --output ./downloads

To access private photos, first run the OAuth authorisation flow:

    python download_flickr_pictures.py \
        --user-id 12345678@N00 \
        --authenticate

Then run normally; the saved token is used automatically.

Requirements:
  * `requests` and `requests-oauthlib` must be installed:
        pip install requests requests-oauthlib

Notes:
  * The API key file must contain the API key on line 1 and the API secret
    on line 2.  The secret is required for the OAuth flow.
  * The `user_id` parameter refers to the Flickr NSID of the account to
    search.  You can find your NSID at
    https://www.flickr.com/services/api/misc.nsid.html
  * Without OAuth the script only retrieves public photos.  After running
    --authenticate, private and friends-only photos are also returned.
"""

import argparse
import datetime
import json
import random
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import parse_qs

import requests
import config


def load_api_credentials(file_path: str) -> Tuple[str, Optional[str]]:
    """Read the Flickr API key and optional secret from the given file.

    Line 1: API key (required)
    Line 2: API secret (required for OAuth / private photo access)

    Args:
        file_path: Path to the credentials text file.

    Returns:
        A tuple of (api_key, api_secret).  api_secret is None if the file
        has only one line.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"API key file not found: {file_path}")
    with path.open(encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines()]
    key = lines[0] if lines else ""
    if not key:
        raise ValueError(f"API key file '{file_path}' is empty")
    secret = lines[1] if len(lines) > 1 and lines[1] else None
    return key, secret


def save_oauth_token(token: dict, file_path: str) -> None:
    """Persist an OAuth access token to a JSON file."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(token, f)


def load_oauth_token(file_path: str) -> Optional[dict]:
    """Load a previously saved OAuth access token, or None if not present."""
    path = Path(file_path)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def authenticate(api_key: str, api_secret: str, pending_file: str) -> None:
    """Step 1 of OAuth: get a request token and print the authorisation URL.

    Saves the request token/secret to pending_file, then exits.  Run
    --verify CODE to complete the flow once you have the verifier.

    Args:
        api_key: Flickr API key.
        api_secret: Flickr API secret.
        pending_file: Path where the pending request token is saved.
    """
    from requests_oauthlib import OAuth1

    oauth = OAuth1(api_key, client_secret=api_secret, callback_uri="oob")
    resp = requests.post(
        "https://www.flickr.com/services/oauth/request_token",
        auth=oauth,
        timeout=30,
    )
    resp.raise_for_status()
    creds = parse_qs(resp.text)
    pending = {
        "oauth_token": creds["oauth_token"][0],
        "oauth_token_secret": creds["oauth_token_secret"][0],
    }
    with open(pending_file, "w", encoding="utf-8") as f:
        json.dump(pending, f)

    auth_url = (
        f"https://www.flickr.com/services/oauth/authorize"
        f"?oauth_token={pending['oauth_token']}&perms=read"
    )
    print(f"\nOpen this URL in your browser to authorise:\n\n  {auth_url}\n")
    print(f"Then run:  python3 download_flickr_pictures.py --user-id <NSID> --verify CODE\n")


def verify(api_key: str, api_secret: str, verifier: str, pending_file: str, auth_file: str) -> None:
    """Step 2 of OAuth: exchange the verifier code for an access token.

    Reads the pending request token saved by --authenticate, exchanges it
    for a permanent access token, and saves it to auth_file.

    Args:
        api_key: Flickr API key.
        api_secret: Flickr API secret.
        verifier: The code shown by Flickr after authorisation.
        pending_file: Path to the pending request token written by --authenticate.
        auth_file: Path where the access token JSON will be saved.
    """
    from requests_oauthlib import OAuth1

    pending_path = Path(pending_file)
    if not pending_path.is_file():
        raise FileNotFoundError(
            f"No pending auth found at {pending_file}. Run --authenticate first."
        )
    with pending_path.open(encoding="utf-8") as f:
        pending = json.load(f)

    oauth = OAuth1(
        api_key,
        client_secret=api_secret,
        resource_owner_key=pending["oauth_token"],
        resource_owner_secret=pending["oauth_token_secret"],
        verifier=verifier.strip(),
    )
    resp = requests.post(
        "https://www.flickr.com/services/oauth/access_token",
        auth=oauth,
        timeout=30,
    )
    resp.raise_for_status()
    creds = parse_qs(resp.text)
    token = {
        "oauth_token": creds["oauth_token"][0],
        "oauth_token_secret": creds["oauth_token_secret"][0],
    }
    save_oauth_token(token, auth_file)
    pending_path.unlink(missing_ok=True)
    print(f"Authorised successfully. Token saved to {auth_file}")


def get_nth_weekday_of_month(date: datetime.date) -> tuple:
    """Return (n, weekday) describing date's position within its month.

    For example, April 4 2026 (a Saturday) → (1, 5) meaning "1st Saturday".

    Returns:
        A tuple of (n, weekday) where n is 1-based and weekday follows
        datetime convention (0=Monday, 6=Sunday).
    """
    n = (date.day - 1) // 7 + 1
    return n, date.weekday()


def nth_weekday_in_month(year: int, month: int, weekday: int, n: int) -> Optional[datetime.date]:
    """Return the date of the nth occurrence of weekday in the given month/year.

    Args:
        year: Target year.
        month: Target month (1–12).
        weekday: Day of week (0=Monday, 6=Sunday).
        n: 1-based occurrence index.

    Returns:
        The matching date, or None if the nth occurrence does not exist in
        that month (e.g. there is no 5th Saturday in a short month).
    """
    first = datetime.date(year, month, 1)
    days_ahead = (weekday - first.weekday()) % 7
    first_occurrence = first + datetime.timedelta(days=days_ahead)
    target = first_occurrence + datetime.timedelta(weeks=n - 1)
    if target.month != month:
        return None
    return target


def build_date_range(target_date: datetime.date) -> Dict[str, str]:
    """Construct Flickr API date range parameters for a single day.

    Flickr expects dates in the format YYYY‑MM‑DD HH:MM:SS.  This helper
    constructs the start and end timestamps covering the entire day.

    Args:
        target_date: A datetime.date object representing the day to
            search.

    Returns:
        A dict with 'min_taken_date' and 'max_taken_date'.
    """
    start = datetime.datetime.combine(target_date, datetime.time.min)
    end = datetime.datetime.combine(target_date, datetime.time.max)
    return {
        "min_taken_date": start.strftime("%Y-%m-%d %H:%M:%S"),
        "max_taken_date": end.strftime("%Y-%m-%d %H:%M:%S"),
    }


def fetch_photos(
    api_key: str,
    user_id: str,
    target_date: datetime.date,
    per_page: int = 5,
    auth=None,
) -> List[Dict]:
    """Search for photos taken on a specific date using Flickr's API.

    This function queries the `flickr.photos.search` endpoint for the
    specified user and date range.  Only the first page of results is
    retrieved; up to `per_page` photos are returned.  The API returns
    metadata but not the actual image files.

    Args:
        api_key: Your Flickr API key.
        user_id: The Flickr NSID of the account to search.
        target_date: The date whose day and month will be searched (year
            component is used as passed; this script passes last year's
            date).
        per_page: Maximum number of photos to return (default 5).
        auth: Optional requests_oauthlib.OAuth1 instance.  When provided,
            the request is signed and private photos are included.

    Returns:
        A list of dicts representing the photo metadata.

    Raises:
        requests.HTTPError: If the HTTP response indicates failure.
    """
    base_url = "https://api.flickr.com/services/rest/"
    date_params = build_date_range(target_date)
    params = {
        "method": "flickr.photos.search",
        "api_key": api_key,
        "user_id": user_id,
        "per_page": per_page,
        "page": 1,
        "extras": "date_taken,views,url_o,url_l,url_b,url_c,url_z,url_n,url_m",
        "format": "json",
        "nojsoncallback": 1,
        **date_params,
    }
    response = requests.get(base_url, params=params, timeout=30, auth=auth)
    response.raise_for_status()
    data = response.json()
    if "photos" not in data:
        raise RuntimeError(f"Unexpected API response: {data}")
    return data["photos"].get("photo", [])


def choose_best_url(photo: Dict) -> Optional[str]:
    """Select the best available image URL from Flickr photo metadata.

    The Flickr API may return various size URLs (url_o, url_l, etc.).
    This helper picks the highest‑resolution URL that is present.  If
    none are available, returns None.

    Args:
        photo: A dict with Flickr photo metadata including URL fields.

    Returns:
        The chosen URL string or None.
    """
    # Order of preference: original, large, medium, etc.
    # url_h and url_k require unique secrets not available via the search extras
    # parameter, so they are intentionally excluded.
    for key in [
        "url_o",
        "url_l",
        "url_b",
        "url_c",
        "url_z",
        "url_n",
        "url_m",
    ]:
        url = photo.get(key)
        if url:
            return url
    return None


def download_photo(url: str, dest_path: Path, auth=None) -> None:
    """Download a single photo from the given URL to disk.

    Args:
        url: The URL of the image to download.
        dest_path: Path to the file where the image should be saved.
        auth: Optional OAuth1 instance for signed requests.

    Raises:
        requests.HTTPError: If the download request fails.
    """
    with requests.get(url, stream=True, timeout=60, auth=auth) as r:
        r.raise_for_status()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with dest_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def select_photos(photos: List[Dict], count: int, criteria: str) -> List[Dict]:
    """Select up to count photos from a list according to the given criteria.

    Args:
        photos: Full list of photo metadata dicts from the API.
        count: Maximum number of photos to return.
        criteria: One of "random", "first", "last", or "views".

    Returns:
        A subset of photos (or the full list if len <= count).
    """
    if len(photos) <= count:
        return photos

    if criteria == "random":
        return random.sample(photos, count)
    elif criteria == "first":
        return sorted(photos, key=lambda p: p.get("datetaken", ""))[:count]
    elif criteria == "last":
        return sorted(photos, key=lambda p: p.get("datetaken", ""), reverse=True)[:count]
    elif criteria == "views":
        return sorted(photos, key=lambda p: int(p.get("views", 0)), reverse=True)[:count]
    else:
        raise ValueError(f"Unknown selection criteria: {criteria!r}. Choose from: random, first, last, views")


def sanitize_filename(name: str) -> str:
    """Simplify strings to safe filenames by replacing whitespace and stripping.

    Args:
        name: Raw title or identifier from Flickr.

    Returns:
        A sanitized filename component containing only safe characters.
    """
    # Replace whitespace with underscores and remove problematic chars
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name).strip("_")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Download up to 10 photos per year (1, 5, 10, 15, 20 years ago) "
            "from a Flickr account taken on today's month and day."
        )
    )
    parser.add_argument(
        "--user-id",
        default=config.USER_ID,
        help=(
            "The Flickr NSID of the account to search (e.g. 12345678@N00). "
            "Defaults to USER_ID in config.py."
        ),
    )
    parser.add_argument(
        "--api-key-file",
        default="flickr_api_key.txt",
        help=(
            "Path to a file containing your Flickr API key on line 1 and "
            "API secret on line 2 (secret required for OAuth)."
        ),
    )
    parser.add_argument(
        "--auth-file",
        default="flickr_oauth.json",
        help="Path to store/load the OAuth access token (default: flickr_oauth.json).",
    )
    parser.add_argument(
        "--authenticate",
        action="store_true",
        help=(
            "Step 1 of OAuth: print the Flickr authorisation URL. "
            "Then run --verify CODE with the code shown by Flickr."
        ),
    )
    parser.add_argument(
        "--verify",
        metavar="CODE",
        help="Step 2 of OAuth: exchange the verifier code for an access token.",
    )
    parser.add_argument(
        "--output",
        default="downloads",
        help="Directory to save downloaded photos (will be created if missing).",
    )
    args = parser.parse_args()

    # Load API credentials
    try:
        api_key, api_secret = load_api_credentials(args.api_key_file)
    except Exception as e:
        print(f"Error reading API credentials: {e}", file=sys.stderr)
        sys.exit(1)

    pending_file = args.auth_file + ".pending"

    # OAuth step 1: get request token and print auth URL
    if args.authenticate:
        if not api_secret:
            print(
                "Error: API secret is required for authentication. "
                "Add it as line 2 of your API key file.",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            authenticate(api_key, api_secret, pending_file)
        except Exception as e:
            print(f"Authentication failed: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # OAuth step 2: exchange verifier for access token
    if args.verify:
        if not api_secret:
            print(
                "Error: API secret is required. Add it as line 2 of your API key file.",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            verify(api_key, api_secret, args.verify, pending_file, args.auth_file)
        except Exception as e:
            print(f"Verification failed: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # Build OAuth1 auth object if a saved token exists
    auth = None
    token = load_oauth_token(args.auth_file)
    if token:
        try:
            from requests_oauthlib import OAuth1
            auth = OAuth1(
                api_key,
                client_secret=api_secret,
                resource_owner_key=token["oauth_token"],
                resource_owner_secret=token["oauth_token_secret"],
            )
            print("Using saved OAuth token (private photos accessible).", file=sys.stderr)
        except ImportError:
            print(
                "Warning: requests-oauthlib not installed; ignoring saved token. "
                "Run: pip install requests-oauthlib",
                file=sys.stderr,
            )

    today = datetime.date.today()
    # Folder named MM/DD based on today's date
    date_folder = Path(args.output) / today.strftime("%m") / today.strftime("%d")

    # Pre-compute nth-weekday anchor from today (used when strategy is nth_weekday)
    nth, weekday = get_nth_weekday_of_month(today)
    weekday_name = today.strftime("%A")
    ordinal = {1: "1st", 2: "2nd", 3: "3rd"}.get(nth, f"{nth}th")

    for years_ago in config.YEARS_AGO:
        target_year = today.year - years_ago

        if config.DATE_STRATEGY == "nth_weekday":
            target_date = nth_weekday_in_month(target_year, today.month, weekday, nth)
            if target_date is None:
                print(
                    f"\n--- {years_ago} year(s) ago: no {ordinal} {weekday_name} in "
                    f"{datetime.date(target_year, today.month, 1).strftime('%B %Y')} — skipping ---",
                    file=sys.stderr,
                )
                continue
        else:
            try:
                target_date = today.replace(year=target_year)
            except ValueError:
                # Feb 29 in a non-leap year
                target_date = today.replace(year=target_year, day=28)

        label = (
            f"{ordinal} {weekday_name} of {target_date.strftime('%B %Y')}"
            if config.DATE_STRATEGY == "nth_weekday"
            else target_date.strftime("%Y-%m-%d")
        )
        print(
            f"\n--- {years_ago} year(s) ago: searching {label} ({target_date}) ---",
            file=sys.stderr,
        )
        try:
            photos = fetch_photos(api_key, args.user_id, target_date, per_page=500, auth=auth)
        except requests.HTTPError as e:
            print(f"Flickr API request failed: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"Error fetching photos: {e}", file=sys.stderr)
            continue

        if not photos:
            print("No photos found.", file=sys.stderr)
            continue

        if len(photos) > config.MAX_PHOTOS:
            total = len(photos)
            photos = select_photos(photos, config.MAX_PHOTOS, config.SELECTION)
            print(
                f"Selected {len(photos)} of {total} photos (criteria: {config.SELECTION}).",
                file=sys.stderr,
            )

        # Save into downloads/MM/DD/YYYY/
        out_dir = date_folder / str(target_date.year)
        for i, photo in enumerate(photos, 1):
            url = choose_best_url(photo)
            if not url:
                print(
                    f"Skipping photo {photo.get('id')} – no downloadable URL available.",
                    file=sys.stderr,
                )
                continue
            photo_id = photo.get("id", "")
            # Skip if already downloaded (any extension)
            if photo_id and list(out_dir.glob(f"{photo_id}*")):
                print(f"Skipping {photo_id} — already downloaded.", file=sys.stderr)
                continue
            title = photo.get("title", f"photo_{i}")
            ext = Path(url.split("?")[0]).suffix or ".jpg"
            filename = sanitize_filename(f"{photo_id}_{title}") + ext
            dest_path = out_dir / filename
            try:
                print(f"Downloading {url} -> {dest_path}", file=sys.stderr)
                download_photo(url, dest_path, auth=auth)
            except requests.HTTPError as e:
                print(f"Failed to download photo {photo_id}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
