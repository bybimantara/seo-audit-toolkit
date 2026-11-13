# SEO Audit Toolkit

A lightweight Python toolkit for crawling websites, auditing technical on-page SEO factors, validating robots/sitemaps, checking broken links, and generating standalone CSV/HTML reports or running an interactive web dashboard.

Built without headless browser overhead, utilizing asynchronous HTTP (`asyncio` + `httpx`), HTML parsing (`BeautifulSoup4`), and Python's standard library SQLite (`sqlite3`) for local audit persistence and regression tracking.

---

## Features

- Breadth-first search (BFS) internal site crawler with URL normalization, crawl loop protection, and private network/anti-SSRF filtering.
- On-page metadata checks for `<title>`, meta descriptions, H1/H2 counts, canonical URLs, and heading hierarchy skips (for example, H1 jumping straight to H3).
- HTTP status verification (`404`/`5xx`) for internal and external links with destination deduplication.
- Multi-hop redirect tracing (`301`/`302`) that flags long chains and redirect loops.
- Site directive checks covering `robots.txt` syntax, `sitemap.xml` (including `<sitemapindex>`), `/llms.txt`, and AI crawler rules (GPTBot, ClaudeBot, PerplexityBot).
- OpenGraph, Twitter Card, and JSON-LD validation alongside image checks for missing `alt` attributes or `width`/`height` dimensions.
- 22-column CSV exports and offline-capable standalone HTML reports with zero external CDN dependencies.
- Local SQLite persistence for storing audit history and diffing score deltas, regressions, resolved issues, and broken link changes across runs.
- Command-line workflow (with CI score gates) and an interactive FastAPI web dashboard.

---

## Requirements

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/bybimantara/seo-audit-toolkit.git
   cd seo-audit-toolkit
   ```

2. Synchronize dependencies using `uv`:
   ```bash
   uv sync
   ```

3. (Optional) Configure environment variables:
   ```bash
   cp .env.example .env
   ```

---

## Usage

### 1. CLI Audit

Audit a target website directly from the terminal:
```bash
uv run seo-audit https://example.com
```

Generate both CSV and HTML reports:
```bash
uv run seo-audit https://example.com --max-pages 50 --csv report.csv --html report.html
```

Available flags:
```text
--max-pages <int>           Maximum internal pages to crawl (default: 50)
--max-external-links <int>  Maximum external links to verify (default: 100)
--concurrency <int>         Concurrent asynchronous requests (default: 10)
--timeout <float>           Request timeout in seconds (default: 10.0)
--no-save                   Skip saving this audit to the local history database
--json                      Print raw report JSON to stdout
--fail-under <int>          Exit with code 1 if health score is below this threshold
```

### 2. Audit History & Diffing

List past audit runs stored in SQLite:
```bash
uv run seo-audit history --limit 20
```

Compare two audits to detect regressions or score improvements:
```bash
uv run seo-audit compare <old_report_id> <new_report_id>
```

Output comparison as JSON for CI/CD pipelines:
```bash
uv run seo-audit compare <old_report_id> <new_report_id> --json
```

### 3. Interactive Web Dashboard

Launch the local web server:
```bash
uv run seo-audit serve --reload
```
Navigate to `http://127.0.0.1:8000` to run audits interactively, download reports, view past history, and compare audit diffs visually.

---

## Testing & Code Quality

Run the test suite:
```bash
uv run pytest
```

Run code formatting and linter checks:
```bash
uv run ruff check .
```

---

## Project Structure

```text
seo-audit-toolkit/
├── src/
│   └── seo_audit/
│       ├── analyzer.py     # HTML, On-Page, OG, JSON-LD, heading, and directive parsing
│       ├── cli.py          # Command-line interface (audit, history, compare, serve)
│       ├── crawler.py      # Async BFS crawler, redirect tracing, and broken link checks
│       ├── db.py           # SQLite persistence layer for audit history
│       ├── diff.py         # Audit comparison and regression tracking engine
│       ├── models.py       # Data models and serialization logic
│       ├── reporters.py    # CSV and standalone HTML report generators
│       └── web.py          # FastAPI web application and dashboard
├── tests/                  # Automated unit and integration test suite
├── .env.example            # Environment configuration template
├── pyproject.toml          # Project configuration, dependencies, and build settings
├── LICENSE                 # License file
└── README.md               # Main project documentation
```

---

## License

Distributed under the MIT License. See [LICENSE](./LICENSE) for details.
