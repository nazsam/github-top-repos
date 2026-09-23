#!/usr/bin/env python3
"""Fetch the most popular GitHub repositories and write ranked Markdown pages.

Uses only the Python standard library. Set GITHUB_TOKEN to raise the API
rate limit (recommended; GitHub Actions provides one automatically).

Usage:
    python scripts/fetch_rankings.py [--out docs] [--limit 100]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

API_URL = "https://api.github.com/search/repositories"
USER_AGENT = "github-top-repos-ranker"

# Display name -> GitHub search qualifier value, and output slug.
LANGUAGES = [
    ("JavaScript", "javascript", "javascript"),
    ("Python", "python", "python"),
    ("Go", "go", "go"),
    ("Rust", "rust", "rust"),
    ("C++", "cpp", "cpp"),
    ("Java", "java", "java"),
]


@dataclass
class Ranking:
    slug: str
    title: str
    description: str
    query: str
    sort: str  # "stars" or "forks"


def build_rankings() -> list[Ranking]:
    rankings = [
        Ranking("most-starred", "Most Starred Repositories",
                "The top repositories on GitHub ranked by star count.",
                "stars:>10000", "stars"),
        Ranking("most-forked", "Most Forked Repositories",
                "The top repositories on GitHub ranked by fork count.",
                "forks:>5000", "forks"),
    ]
    for name, qualifier, slug in LANGUAGES:
        rankings.append(Ranking(
            f"languages/{slug}", f"Top {name} Repositories",
            f"The most-starred repositories whose primary language is {name}.",
            f"language:{qualifier} stars:>1000", "stars"))
    return rankings


def api_get(params: dict, token: str | None, retries: int = 5) -> dict:
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            # Rate limited: wait until the reset time (or back off) and retry.
            rate_limited = err.code == 429 or (
                err.code == 403 and (err.headers.get("X-RateLimit-Remaining") == "0"
                                     or err.headers.get("Retry-After")))
            if rate_limited:
                reset = err.headers.get("X-RateLimit-Reset")
                retry_after = err.headers.get("Retry-After")
                if retry_after:
                    wait = int(retry_after)
                elif reset:
                    wait = max(int(reset) - int(time.time()), 1) + 1
                else:
                    wait = 2 ** attempt * 5
                wait = min(wait, 120)
                print(f"  rate limited, waiting {wait}s (attempt {attempt}/{retries})",
                      file=sys.stderr)
                time.sleep(wait)
                continue
            if 500 <= err.code < 600:
                time.sleep(2 ** attempt)
                continue
            body = err.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"GitHub API error {err.code}: {body}") from err
        except urllib.error.URLError:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"GitHub API request failed after {retries} attempts: {url}")


def fetch_ranking(r: Ranking, limit: int, token: str | None) -> list[dict]:
    repos: list[dict] = []
    page = 1
    while len(repos) < limit:
        per_page = min(100, limit - len(repos))
        data = api_get({"q": r.query, "sort": r.sort, "order": "desc",
                        "per_page": per_page, "page": page}, token)
        items = data.get("items", [])
        repos.extend(items)
        if len(items) < per_page:
            break
        page += 1
    # The search index can return counts slightly out of order; sort ourselves.
    key = "forks_count" if r.sort == "forks" else "stargazers_count"
    repos.sort(key=lambda repo: repo[key], reverse=True)
    return repos[:limit]


def fmt_num(n: int) -> str:
    return f"{n:,}"


def md_escape(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def render_page(r: Ranking, repos: list[dict], updated: str, depth: int) -> str:
    home = "../" * depth + "index.md" if depth else "index.md"
    lines = [
        "---",
        f"title: {r.title}",
        "---",
        "",
        f"# {r.title}",
        "",
        r.description,
        "",
        f"*Last updated: {updated}* | [Back to all rankings]({home.replace('.md', '.html')})",
        "",
        "| Rank | Project | Stars | Forks | Language |",
        "|---:|---|---:|---:|---|",
    ]
    for i, repo in enumerate(repos, 1):
        name = md_escape(repo["full_name"])
        link = repo["html_url"]
        desc = " ".join((repo.get("description") or "").split())
        if len(desc) > 120:
            desc = desc[:117].rstrip() + "..."
        desc = md_escape(desc).replace("<", "&lt;").replace(">", "&gt;")
        project = f"[{name}]({link})" + (f"<br><sub>{desc}</sub>" if desc else "")
        lines.append(
            f"| {i} | {project} | {fmt_num(repo['stargazers_count'])} | "
            f"{fmt_num(repo['forks_count'])} | {md_escape(repo.get('language') or 'n/a')} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_index(rankings: list[Ranking], results: dict, updated: str) -> str:
    lines = [
        "---",
        "title: GitHub Top Repositories",
        "---",
        "",
        "# GitHub Top Repositories",
        "",
        "Daily rankings of the most popular repositories on GitHub, "
        "generated automatically from the GitHub API.",
        "",
        f"*Last updated: {updated}*",
        "",
        "## Overall",
        "",
    ]
    for r in rankings[:2]:
        top = results[r.slug][0] if results[r.slug] else None
        leader = f" (currently led by [{top['full_name']}]({top['html_url']}))" if top else ""
        lines.append(f"- [{r.title}]({r.slug}.html){leader}")
    lines += ["", "## By language", ""]
    lines += ["| Language | #1 Repository | Stars |", "|---|---|---:|"]
    for r in rankings[2:]:
        lang = r.title.replace("Top ", "").replace(" Repositories", "")
        top = results[r.slug][0] if results[r.slug] else None
        if top:
            lines.append(f"| [{lang}]({r.slug}.html) | [{top['full_name']}]({top['html_url']}) | "
                         f"{fmt_num(top['stargazers_count'])} |")
        else:
            lines.append(f"| [{lang}]({r.slug}.html) | n/a | n/a |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs", help="output directory (default: docs)")
    parser.add_argument("--limit", type=int, default=100, help="repos per list (max 1000)")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("Warning: GITHUB_TOKEN not set; using the low unauthenticated rate limit.",
              file=sys.stderr)

    out = Path(args.out)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rankings = build_rankings()
    results: dict[str, list[dict]] = {}

    for r in rankings:
        print(f"Fetching {r.title}...")
        repos = fetch_ranking(r, args.limit, token)
        results[r.slug] = repos
        depth = r.slug.count("/")
        path = out / f"{r.slug}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_page(r, repos, updated, depth), encoding="utf-8")
        print(f"  wrote {path} ({len(repos)} repos)")
        # Stay well under the search API limit (10/min anonymous, 30/min with a token).
        time.sleep(2 if token else 7)

    (out / "index.md").write_text(render_index(rankings, results, updated), encoding="utf-8")

    # Raw data for anyone who wants to build on it.
    slim = {slug: [{k: repo[k] for k in ("full_name", "html_url", "stargazers_count",
                                          "forks_count", "language")} for repo in repos]
            for slug, repos in results.items()}
    (out / "data.json").write_text(json.dumps({"updated": updated, "rankings": slim},
                                              indent=2), encoding="utf-8")
    print(f"Done. Pages written to {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
