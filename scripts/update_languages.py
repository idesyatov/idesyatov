#!/usr/bin/env python3
"""Update the languages block in assets/terminal.svg with real top languages.

Aggregates byte counts across the user's public (non-fork, non-archived)
repositories via the GitHub REST API, then rewrites the bar chart between the
<!-- LANGS:START --> / <!-- LANGS:END --> markers. Standard library only.
"""
import os
import re
import json
import urllib.request

USER = os.environ.get("GH_USER", "idesyatov")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
SVG = os.path.join(os.path.dirname(__file__), "..", "assets", "terminal.svg")

TOP = 5          # how many languages to show
BAR = 15         # bar length in characters
NAMEPAD = 11     # width of the language-name column
Y0, STEP = 322, 24

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
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


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


def aggregate():
    agg = {}
    for repo in get_repos():
        if repo.get("fork") or repo.get("archived"):
            continue
        for lang, b in api(repo["languages_url"]).items():
            agg[lang] = agg.get(lang, 0) + b
    return agg


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
        namep = name[:NAMEPAD].ljust(NAMEPAD)
        y = Y0 + STEP * i
        lines.append(
            f'    <tspan x="40" y="{y}">'
            f'<tspan fill="#c0caf5">{namep}</tspan>'
            f'<tspan fill="{color}">{"█" * fill}</tspan>'
            f'<tspan fill="#414868">{"░" * empty}</tspan>'
            f'<tspan fill="#565f89"> {pct}%</tspan></tspan>'
        )
    return "\n".join(lines)


def main():
    agg = aggregate()
    if not agg:
        print("no languages found, leaving SVG unchanged")
        return
    block = build_block(agg)
    with open(SVG, encoding="utf-8") as f:
        svg = f.read()
    new = re.sub(
        r"(<!-- LANGS:START -->).*?(<!-- LANGS:END -->)",
        lambda m: m.group(1) + "\n" + block + "\n" + m.group(2),
        svg, flags=re.S,
    )
    with open(SVG, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"updated {block.count('<tspan x=')} languages")


if __name__ == "__main__":
    main()
