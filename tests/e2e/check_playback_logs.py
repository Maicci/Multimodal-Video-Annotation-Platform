"""Check server logs from a browser run without printing credential-bearing lines."""

import re
import sys


streams = thumbnails = exposed = 0
media_request = re.compile(r'"GET /api/videos/[^/ ]+/(stream|thumbnails/\d+) HTTP/[\d.]+" 20[06]\b')
jwt = re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+")
for line in sys.stdin:
    if "media_token=" in line or jwt.search(line):
        exposed += 1
    match = media_request.search(line)
    if match:
        if match[1] == "stream":
            streams += 1
        else:
            thumbnails += 1

print(f"Successful stream requests: {streams}, thumbnails: {thumbnails}, "
      f"log lines containing credentials: {exposed}")
sys.exit(0 if streams and thumbnails and not exposed else 1)
