"""Render the profile's stats and top-languages cards as SVG.

Replaces the public github-readme-stats server, which went offline.
Uses only public data from the GitHub GraphQL API, so the workflow's
built-in GITHUB_TOKEN is enough. Standard library only.

Usage: GITHUB_TOKEN=... python stats_cards.py <user> <out_dir>
"""
import html
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com/graphql"
HIDDEN_LANGS = {"Jupyter Notebook", "HTML", "CSS", "Dockerfile"}
LANG_COUNT = 6

BG, LINE, TEXT, MUTED = "#0d1117", "#30363d", "#e6edf3", "#8b949e"
PINK, PURPLE = "#F75C7E", "#7C3AED"
FONT = "Segoe UI, Helvetica, Arial, sans-serif"


def gql(query, variables=None):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.load(resp)
    if body.get("errors"):
        raise SystemExit(f"GraphQL error: {body['errors']}")
    return body["data"]


def fetch(user):
    data = gql("""
      query($login: String!) {
        user(login: $login) {
          name
          pullRequests { totalCount }
          issues { totalCount }
          contributionsCollection { contributionYears }
          repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
            nodes {
              stargazerCount
              languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
                edges { size node { name color } }
              }
            }
          }
        }
      }""", {"login": user})["user"]

    # All-time commits: one contributionsCollection per year, batched with aliases.
    years = data["contributionsCollection"]["contributionYears"]
    parts = [
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") '
        "{ totalCommitContributions restrictedContributionsCount }"
        for y in years
    ]
    per_year = gql(f'query($login: String!) {{ user(login: $login) {{ {" ".join(parts)} }} }}',
                   {"login": user})["user"]
    commits = sum(v["totalCommitContributions"] + v["restrictedContributionsCount"]
                  for v in per_year.values())

    langs = {}
    for repo in data["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name in HIDDEN_LANGS:
                continue
            entry = langs.setdefault(name, {"size": 0, "color": edge["node"]["color"] or MUTED})
            entry["size"] += edge["size"]

    return {
        "name": data["name"] or user,
        "stars": sum(r["stargazerCount"] for r in data["repositories"]["nodes"]),
        "commits": commits,
        "prs": data["pullRequests"]["totalCount"],
        "issues": data["issues"]["totalCount"],
        "langs": sorted(langs.items(), key=lambda kv: -kv[1]["size"])[:LANG_COUNT],
    }


def fmt(n):
    return f"{n / 1000:.1f}k" if n >= 10_000 else f"{n:,}"


def defs():
    return (f'<defs><linearGradient id="accent" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0%" stop-color="{PINK}"/><stop offset="100%" stop-color="{PURPLE}"/>'
            f'</linearGradient></defs>')


# 16x16 outline icons (original, simple strokes).
ICONS = {
    "star": '<path d="M8 1.5l2 4.2 4.6.6-3.3 3.2.8 4.5L8 11.8 3.9 14l.8-4.5L1.4 6.3l4.6-.6z"/>',
    "commit": '<circle cx="8" cy="8" r="3"/><path d="M1 8h4M11 8h4"/>',
    "pr": '<circle cx="4" cy="3.5" r="1.8"/><circle cx="4" cy="12.5" r="1.8"/>'
          '<circle cx="12" cy="12.5" r="1.8"/><path d="M4 5.3v5.4M12 10.7V6a2 2 0 0 0-2-2H7"/>'
          '<path d="M8.5 2.5L7 4l1.5 1.5"/>',
    "issue": '<circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="1" fill="currentColor"/>',
}


def stats_svg(s, updated):
    w, h = 450, 180
    rows = [("star", "Total Stars Earned", s["stars"]),
            ("commit", "Total Commits", s["commits"]),
            ("pr", "Total PRs", s["prs"]),
            ("issue", "Total Issues", s["issues"])]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
           f'font-family="{FONT}" role="img" aria-label="{html.escape(s["name"])} GitHub stats">',
           defs(),
           f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="12" fill="{BG}" stroke="{LINE}"/>',
           f'<text x="24" y="38" font-size="18" font-weight="700" fill="url(#accent)">'
           f'{html.escape(s["name"])}\'s GitHub Stats</text>']
    for i, (icon, label, value) in enumerate(rows):
        y = 70 + i * 26
        out.append(f'<g transform="translate(24,{y - 12})" fill="none" stroke="{PINK}" '
                   f'stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" color="{PINK}">'
                   f'{ICONS[icon]}</g>')
        out.append(f'<text x="50" y="{y}" font-size="14" font-weight="600" fill="{TEXT}">{label}:</text>')
        out.append(f'<text x="250" y="{y}" font-size="14" font-weight="700" fill="{TEXT}">{fmt(value)}</text>')
    # Voice-waveform ring, the profile's motif, instead of a rank grade.
    cx, cy = 372, 92
    out.append(f'<circle cx="{cx}" cy="{cy}" r="42" fill="none" stroke="{LINE}" stroke-width="6"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="42" fill="none" stroke="url(#accent)" stroke-width="6" '
               f'stroke-linecap="round" stroke-dasharray="190 264" transform="rotate(-90 {cx} {cy})"/>')
    for j, bh in enumerate([14, 26, 36, 22, 30, 16]):
        out.append(f'<rect x="{cx - 26 + j * 9}" y="{cy - bh / 2}" width="5" height="{bh}" rx="2.5" '
                   f'fill="url(#accent)"/>')
    out.append(f'<text x="{w - 16}" y="{h - 12}" font-size="10" fill="{MUTED}" text-anchor="end">'
               f'updated {updated}</text>')
    out.append('</svg>')
    return "\n".join(out)


def langs_svg(s):
    w, h = 320, 180
    total = sum(v["size"] for _, v in s["langs"]) or 1
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
           f'font-family="{FONT}" role="img" aria-label="Most used languages">',
           defs(),
           f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="12" fill="{BG}" stroke="{LINE}"/>',
           '<text x="24" y="38" font-size="18" font-weight="700" fill="url(#accent)">Most Used Languages</text>',
           '<clipPath id="bar"><rect x="24" y="56" width="272" height="8" rx="4"/></clipPath>',
           '<g clip-path="url(#bar)">']
    x = 24.0
    for _, v in s["langs"]:
        seg = 272 * v["size"] / total
        out.append(f'<rect x="{x:.2f}" y="56" width="{seg + 0.5:.2f}" height="8" fill="{v["color"]}"/>')
        x += seg
    out.append('</g>')
    for i, (name, v) in enumerate(s["langs"]):
        col, row = i % 2, i // 2
        lx, ly = 24 + col * 140, 94 + row * 26
        pct = 100 * v["size"] / total
        out.append(f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{v["color"]}"/>')
        out.append(f'<text x="{lx + 16}" y="{ly}" font-size="12" fill="{TEXT}">'
                   f'{html.escape(name)} <tspan fill="{MUTED}">{pct:.1f}%</tspan></text>')
    out.append('</svg>')
    return "\n".join(out)


def main():
    user, out_dir = sys.argv[1], sys.argv[2]
    stats = fetch(user)
    os.makedirs(out_dir, exist_ok=True)
    updated = datetime.now(timezone.utc).strftime("%b %d, %Y")
    with open(os.path.join(out_dir, "stats.svg"), "w") as f:
        f.write(stats_svg(stats, updated))
    with open(os.path.join(out_dir, "langs.svg"), "w") as f:
        f.write(langs_svg(stats))
    print(json.dumps({k: v for k, v in stats.items() if k != "langs"}),
          [n for n, _ in stats["langs"]])


if __name__ == "__main__":
    main()
