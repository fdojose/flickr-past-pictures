# Daily schedule — time to download and send photos (24h, local time)
SCHEDULE_HOUR   = 8
SCHEDULE_MINUTE = 0

# Flickr NSID of the account to search
USER_ID = "8948709@N07"

# WhatsApp recipients are defined in contacts.json (international format, no +)
# send_whatsapp.js reads that file directly.

# Date matching strategy:
#   "exact"       - same month and day (Apr 4 → Apr 4)
#   "nth_weekday" - same nth weekday of the month (1st Saturday → 1st Saturday)
DATE_STRATEGY = "nth_weekday"

# Years ago to search (relative to today's month and day)
YEARS_AGO = [1, 5, 10, 15, 20]

# Maximum number of photos to download per year
MAX_PHOTOS = 5

# How to select photos when more are available than MAX_PHOTOS:
#   "random"  - randomly sample MAX_PHOTOS from all results
#   "first"   - earliest taken time of day
#   "last"    - latest taken time of day
#   "views"   - most viewed photos
SELECTION = "random"
