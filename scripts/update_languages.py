#!/usr/bin/env python3
"""Update the languages and stats blocks in assets/terminal.svg.

Aggregates byte counts across the user's public (non-fork, non-archived)
repositories via the GitHub REST API, then rewrites the bar chart between the
<!-- LANGS:START --> / <!-- LANGS:END --> markers and the side panel between
the <!-- STATS:START --> / <!-- STATS:END --> markers. Standard library only.
"""
import os
import re
import json
import time
import urllib.parse
import urllib.request
import urllib.error
from xml.sax.saxutils import escape
from datetime import datetime, timezone, timedelta

USER = os.environ.get("GH_USER", "idesyatov")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
SVG = os.path.join(os.path.dirname(__file__), "..", "assets", "terminal.svg")

TOP = 5          # how many languages to show
BAR = 15         # bar length in characters
NAMEPAD = 11     # width of the language-name column
Y0, STEP = 300, 24

SX = 430         # x of the stats panel labels
SVALX = 620      # x of the stats panel values

RETRIES = 3      # attempts per request before giving up
BACKOFF = 5      # seconds, multiplied by attempt number
RETRY_CODES = {403, 429, 500, 502, 503, 504}

# linguist colors for common languages; anything else falls back to DEFAULT
COLORS = {
    "Go": "#00ADD8", "Python": "#3572A5", "Shell": "#89e051", "C": "#555555",
    "C++": "#f34b7d", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "HTML": "#e34c26", "CSS": "#563d7c", "Dockerfile": "#384d54", "HCL": "#844FBA",
    "Makefile": "#427819", "Rust": "#dea584", "Java": "#b07219", "PHP": "#4F5D95",
    "Ruby": "#701516", "Lua": "#000080", "Vim Script": "#199f4b", "PowerShell": "#012456",
    "YAML": "#cb171e", "Jinja": "#a52a22", "Smarty": "#f0c040",
}
DEFAULT = "#9aa5ce"


def api(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "lang-stats"})
    # only ever attach the token to api.github.com, so a redirect or an
    # unexpected URL from the API cannot exfiltrate it to another host
    if TOKEN and urllib.parse.urlparse(url).hostname == "api.github.com":
        req.add_header("Authorization", "Bearer " + TOKEN)
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_CODES or attempt == RETRIES:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == RETRIES:
                raise
        time.sleep(BACKOFF * attempt)


def get_repos():
    repos, page = [], 1
    while True:
        data = api(f"https://api.github.com/users/{USER}/repos"
                   f"?per_page=100&page={page}&type=owner&sort=pushed")
        repos += data
        if len(data) < 100:
            break
        page += 1
    return repos


def aggregate(repos):
    agg = {}
    for repo in repos:
        if repo.get("fork") or repo.get("archived"):
            continue
        for lang, b in api(repo["languages_url"]).items():
            agg[lang] = agg.get(lang, 0) + b
    return agg


def replace_marker(svg, name, value):
    return re.sub(
        rf"(<!-- {name}:START -->).*?(<!-- {name}:END -->)",
        lambda m: m.group(1) + value + m.group(2),
        svg, flags=re.S,
    )


def fmt_bytes(n):
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{round(n / 1024)} KB"
    return f"{n / 1024 ** 2:.1f} MB"


def search_count(kind, query):
    url = f"https://api.github.com/search/{kind}?q={urllib.parse.quote(query)}&per_page=1"
    return api(url).get("total_count", 0)


def build_stats(agg):
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    rows = [
        ("languages", str(len(agg))),
        ("Σ code", fmt_bytes(sum(agg.values()))),
        (f"commits {now.year}", str(search_count("commits", f"author:{USER} committer-date:>={now.year}-01-01"))),
        ("PRs", str(search_count("issues", f"type:pr author:{USER}"))),
        ("commits 7d", str(search_count("commits", f"author:{USER} committer-date:>={week_ago}"))),
    ]
    lines = []
    for i, (label, val) in enumerate(rows):
        y = Y0 + STEP * i
        lines.append(
            f'    <tspan x="{SX}" y="{y}">'
            f'<tspan fill="#565f89">{escape(label)}</tspan>'
            f'<tspan x="{SVALX}" fill="#c0caf5">{escape(val)}</tspan></tspan>'
        )
    return "\n" + "\n".join(lines) + "\n"


def build_block(agg):
    total = sum(agg.values()) or 1
    items = sorted(agg.items(), key=lambda kv: -kv[1])[:TOP]
    top = items[0][1] if items else 1
    lines = []
    for i, (name, b) in enumerate(items):
        pct = round(b * 100 / total)
        fill = max(1, round(b * BAR / top))
        empty = BAR - fill
        color = COLORS.get(name, DEFAULT)
        namep = escape(name[:NAMEPAD].ljust(NAMEPAD))
        y = Y0 + STEP * i
        lines.append(
            f'    <tspan x="40" y="{y}">'
            f'<tspan fill="#c0caf5">{namep}</tspan>'
            f'<tspan fill="{color}">{"█" * fill}</tspan>'
            f'<tspan fill="#414868">{"░" * empty}</tspan>'
            f'<tspan fill="#565f89"> {pct}%</tspan></tspan>'
        )
    return "\n".join(lines)


NET_ERRORS = (urllib.error.URLError, TimeoutError, ValueError, KeyError)


def main():
    with open(SVG, encoding="utf-8") as f:
        svg = original = f.read()

    try:
        repos = get_repos()
        agg = aggregate(repos)
    except NET_ERRORS as e:
        print(f"failed to fetch repositories ({e}); leaving SVG unchanged")
        return

    if agg:
        svg = replace_marker(svg, "LANGS", "\n" + build_block(agg) + "\n")
        print(f"updated {len(agg)} languages")
    else:
        print("no languages found, leaving languages unchanged")

    try:
        svg = replace_marker(svg, "STATS", build_stats(agg))
        print("updated stats panel")
    except NET_ERRORS as e:
        print(f"failed to build stats ({e}); leaving stats unchanged")

    if svg != original:
        with open(SVG, "w", encoding="utf-8") as f:
            f.write(svg)
    else:
        print("nothing changed")


if __name__ == "__main__":
    main()
