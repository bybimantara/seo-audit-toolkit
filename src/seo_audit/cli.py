"""Command Line Interface (CLI) for SEO Audit Toolkit."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict

from seo_audit.crawler import crawl_site
from seo_audit.reporters import generate_csv_report, generate_html_report


def run_audit_command(args: argparse.Namespace) -> int:
    """Execute audit via terminal and print/save reports."""
    print(f"🚀 Starting SEO audit for {args.target_url} (max pages: {args.max_pages})...")

    try:
        report = asyncio.run(
            crawl_site(
                start_url=args.target_url,
                max_pages=args.max_pages,
                max_external_links=args.max_external_links,
                concurrency=args.concurrency,
                timeout=args.timeout,
                allow_private_network=args.allow_private,
            )
        )
    except ValueError as err:
        print(f"❌ Error: {err}", file=sys.stderr)
        return 2
    except Exception as err:  # noqa: BLE001
        print(f"❌ Execution failed: {err}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(asdict(report), indent=2))
        return 0

    print("\n" + "=" * 55)
    print(f"🎯 SEO AUDIT COMPLETE — Health Score: {report.health_score}/100")
    print(f"⏱️  Duration: {report.duration_seconds}s | Pages Crawled: {len(report.pages)}")
    print(f"🔗 Broken Links: {len(report.broken_links)}")
    print(
        f"🤖 robots.txt: {'✅ Found' if report.site_meta.robots_found else '⚠️ Missing'}"
    )
    print(
        f"🗺️  sitemap.xml: {'✅ Valid' if report.site_meta.sitemap_valid_xml else '⚠️ Missing/Invalid'} ({report.site_meta.sitemap_url_count} URLs)"
    )
    print("=" * 55)

    if args.csv:
        csv_content = generate_csv_report(report)
        with open(args.csv, "w", encoding="utf-8") as f:
            f.write(csv_content)
        print(f"📄 CSV report saved to: {args.csv}")

    if args.html:
        html_content = generate_html_report(report)
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"🌐 HTML report saved to: {args.html}")

    return 0


def run_serve_command(args: argparse.Namespace) -> int:
    """Run FastAPI development/production web server."""
    try:
        import uvicorn
    except ImportError:
        print("❌ uvicorn is required to run the web server.", file=sys.stderr)
        return 1

    host = args.host or os.getenv("HOST", "127.0.0.1")
    port = args.port or int(os.getenv("PORT", "8000"))

    print(f"🌐 Starting SEO Audit Web App at http://{host}:{port}")
    uvicorn.run("seo_audit.web:app", host=host, port=port, reload=args.reload)
    return 0


def add_audit_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--max-pages",
        type=int,
        default=int(os.getenv("DEFAULT_MAX_PAGES", "50")),
        help="Maximum internal pages to crawl (default: 50)",
    )
    parser.add_argument(
        "--max-external-links",
        type=int,
        default=100,
        help="Maximum external links to verify (default: 100)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("DEFAULT_CONCURRENCY", "10")),
        help="Concurrent async requests (default: 10)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("REQUEST_TIMEOUT", "10.0")),
        help="HTTP request timeout in seconds (default: 10.0)",
    )
    parser.add_argument(
        "--allow-private",
        action="store_true",
        help="Allow crawling private or localhost networks",
    )
    parser.add_argument("--csv", help="Save report to CSV file path")
    parser.add_argument("--html", help="Save report to HTML file path")
    parser.add_argument(
        "--json", action="store_true", help="Output audit report as JSON to stdout"
    )


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)

    # 1. If 'serve' subcommand is passed
    if args_list and args_list[0] == "serve":
        serve_parser = argparse.ArgumentParser(
            prog="seo-audit serve", description="Run the Web Dashboard server"
        )
        serve_parser.add_argument(
            "--host", default=None, help="Host to bind (default: 127.0.0.1)"
        )
        serve_parser.add_argument(
            "--port", type=int, default=None, help="Port to bind (default: 8000)"
        )
        serve_parser.add_argument(
            "--reload", action="store_true", help="Enable auto-reload for development"
        )
        parsed_serve = serve_parser.parse_args(args_list[1:])
        return run_serve_command(parsed_serve)

    # 2. Normal audit mode (either 'seo-audit <url> [options]' or 'seo-audit audit <url> [options]')
    if args_list and args_list[0] == "audit":
        args_list = args_list[1:]

    parser = argparse.ArgumentParser(
        prog="seo-audit",
        description="Automated SEO audit toolkit for on-page tags, broken links, robots.txt, and sitemaps.",
    )
    parser.add_argument("target_url", nargs="?", help="Target website URL")
    add_audit_flags(parser)

    parsed_args = parser.parse_args(args_list)
    if not parsed_args.target_url:
        parser.print_help()
        return 2

    return run_audit_command(parsed_args)


if __name__ == "__main__":
    sys.exit(main())
