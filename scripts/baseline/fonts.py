#!/usr/bin/env python3
"""Retain Google font inputs, fetching only fonts.googleapis.com/fonts.gstatic.com."""
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request
from urllib.parse import urlparse
root = Path(sys.argv[1])
root.mkdir()
records = {}
responses = {}
def get(url):
    assert urlparse(url).hostname in ('fonts.googleapis.com', 'fonts.gstatic.com')
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, timeout=30) as response:
        assert urlparse(response.url).hostname in ('fonts.googleapis.com', 'fonts.gstatic.com')
        return response.read()
for family in ('JetBrains+Mono:wght@400;500', 'Saira+Condensed:wght@400;600;700', 'Saira:wght@400;500'):
    url = 'https://fonts.googleapis.com/css2?family=' + family + '&display=swap'
    css = get(url).decode()
    records[url] = hashlib.sha256(css.encode()).hexdigest()
    (root / (hashlib.sha256(url.encode()).hexdigest() + '.css')).write_text(css)
    for font in set(re.findall(r'url\((https://[^)]+)\)', css)):
        data = get(font)
        name = hashlib.sha256(data).hexdigest() + '.woff2'
        (root / name).write_bytes(data)
        records[font] = hashlib.sha256(data).hexdigest()
        css = css.replace(font, '/build/font-inputs/' + name)
    responses[url] = css
(root / 'responses.json').write_text(json.dumps(responses))
(root / 'sources.json').write_text(json.dumps(records, indent=2))
