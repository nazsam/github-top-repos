# GitHub Top Repositories

Daily rankings of the most popular repositories on GitHub, published as static Markdown pages on GitHub Pages.

**Live site:** https://nazsam.github.io/github-top-repos/

## What it tracks

| List | Ranked by | Size |
|---|---|---:|
| [Most starred](docs/most-starred.md) | Stars | 100 |
| [Most forked](docs/most-forked.md) | Forks | 100 |
| [JavaScript](docs/languages/javascript.md) | Stars | 100 |
| [Python](docs/languages/python.md) | Stars | 100 |
| [Go](docs/languages/go.md) | Stars | 100 |
| [Rust](docs/languages/rust.md) | Stars | 100 |
| [C++](docs/languages/cpp.md) | Stars | 100 |
| [Java](docs/languages/java.md) | Stars | 100 |

Every table has the columns **Rank, Project, Stars, Forks, Language**, with a short description under each project name. A machine-readable copy of all lists is saved to `docs/data.json`.

## How it works

```
GitHub Actions (daily cron, 06:00 UTC)
        |
        v
scripts/update.sh ----> scripts/fetch_rankings.py ----> GitHub Search API
        |                          |
        |                          v
        |                  docs/*.md  +  docs/data.json
        v
git commit + push  ---->  GitHub Pages rebuilds the site
```

- `scripts/fetch_rankings.py` queries the GitHub Search API, sorts the results and writes the Markdown tables. It uses only the Python standard library, so there is nothing to install.
- `scripts/update.sh` runs the Python script and, when `PUSH=1` is set, commits and pushes any changes.
- `.github/workflows/update-rankings.yml` runs `update.sh` every day and can also be started by hand from the **Actions** tab.

The script respects GitHub's rate limits: it pauses between requests and waits for the reset window if a limit is hit.

## Run it locally

```bash
git clone https://github.com/nazsam/github-top-repos.git
cd github-top-repos
export GITHUB_TOKEN=ghp_your_token   # optional, but gives a higher rate limit
bash scripts/update.sh                  # pages are written to docs/
```

Options for the Python script:

```bash
python3 scripts/fetch_rankings.py --out docs --limit 100
```

### Scheduling without GitHub Actions

To run it from your own Linux or WSL machine instead, add a cron entry:

```cron
0 6 * * * cd /path/to/github-top-repos && PUSH=1 bash scripts/update.sh >> update.log 2>&1
```

## Adding a language

Edit the `LANGUAGES` list at the top of `scripts/fetch_rankings.py`:

```python
("TypeScript", "typescript", "typescript"),   # display name, search qualifier, page slug
```

## GitHub Pages setup

1. Go to **Settings > Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select branch `main` and folder `/docs`, then save.

## License

[MIT](LICENSE) (c) 2026 Sam Naz
