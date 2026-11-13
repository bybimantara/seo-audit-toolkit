"""Command Line Interface (CLI) for SEO Audit Toolkit."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict

from seo_audit.crawler import crawl_site
from seo_audit.db import get_report, list_reports, save_report
from seo_audit.diff import compare_reports
from seo_audit.reporters import generate_csv_report, generate_html_report


def run_audit_command(args: argparse.Namespace) -> int:
    """Execute audit via terminal and print/save reports."""
    print(
        f"Starting SEO audit for {args.target_url} (max pages: {args.max_pages})...",
        file=sys.stderr,
    )

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
        print(f"Error: {err}", file=sys.stderr)
        return 2
    except Exception as err:  # noqa: BLE001
        print(f"Execution failed: {err}", file=sys.stderr)
        return 1

    # Persist report in local SQLite database unless --no-save is requested
    if not getattr(args, "no_save", False):
        try:
            save_report(report)
        except Exception as err:  # noqa: BLE001
            print(f"Warning: Failed to save to history database: {err}", file=sys.stderr)

    if args.json:
        print(json.dumps(asdict(report), indent=2))
        if getattr(args, "fail_under", None) is not None and report.health_score < args.fail_under:
            return 1
        return 0

    print("\n" + "=" * 58)
    print(f"SEO AUDIT COMPLETE - Health Score: {report.health_score}/100")
    print(f"Report ID: {report.report_id}")
    print(f"Duration: {report.duration_seconds}s | Pages Crawled: {len(report.pages)}")
    print(f"Broken Links: {len(report.broken_links)}")
    print(
        f"robots.txt: {'Found' if report.site_meta.robots_found else 'Missing'}"
    )
    print(
        f"sitemap.xml: {'Valid' if report.site_meta.sitemap_valid_xml else 'Missing/Invalid'} ({report.site_meta.sitemap_url_count} URLs)"
    )
    print(
        f"AI llms.txt: {'Found (/llms.txt)' if report.site_meta.llms_txt_found else 'Missing (/llms.txt)'}"
    )
    print("=" * 58)

    if args.csv:
        csv_content = generate_csv_report(report)
        with open(args.csv, "w", encoding="utf-8") as f:
            f.write(csv_content)
        print(f"CSV report saved to: {args.csv}")

    if args.html:
        html_content = generate_html_report(report)
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"HTML report saved to: {args.html}")

    if getattr(args, "fail_under", None) is not None and report.health_score < args.fail_under:
        print(
            f"Quality gate failed: health score {report.health_score} < {args.fail_under}",
            file=sys.stderr,
        )
        return 1
    return 0


def run_history_command(args: argparse.Namespace) -> int:
    """List recent audit reports stored in the local SQLite database."""
    reports = list_reports(limit=args.limit, domain=args.domain)
    if not reports:
        print("No audit history found.")
        return 0

    print("\n" + "=" * 78)
    print(f"{'REPORT ID':<10} {'HEALTH':<8} {'PAGES':<7} {'BROKEN':<8} {'AUDITED AT':<22} {'TARGET URL'}")
    print("-" * 78)
    for r in reports:
        date_str = r["audited_at"][:19].replace("T", " ")
        print(
            f"{r['report_id']:<10} {r['health_score']:<3}/100  {r['pages_count']:<7} {r['broken_count']:<8} {date_str:<22} {r['target_url']}"
        )
    print("=" * 78 + "\n")
    return 0


def run_compare_command(args: argparse.Namespace) -> int:
    """Compare two audit reports from SQLite database."""
    report_old = get_report(args.report_id_1)
    if not report_old:
        print(f"Error: Report '{args.report_id_1}' not found in database.", file=sys.stderr)
        return 1

    report_new = get_report(args.report_id_2)
    if not report_new:
        print(f"Error: Report '{args.report_id_2}' not found in database.", file=sys.stderr)
        return 1

    diff = compare_reports(report_old, report_new)

    if args.json:
        print(json.dumps(diff.to_dict(), indent=2))
        return 0

    sign = "+" if diff.score_delta > 0 else ""
    status_label = (
        "IMPROVEMENT"
        if diff.score_delta > 0
        else "REGRESSION"
        if diff.score_delta < 0
        else "UNCHANGED"
    )

    print("\n" + "=" * 62)
    print(f"SEO AUDIT COMPARISON (DIFF) - {diff.target_url}")
    print(f"Base Report   : {diff.old_report_id} ({diff.old_score}/100) on {diff.old_audited_at[:19]}")
    print(f"Current Report: {diff.new_report_id} ({diff.new_score}/100) on {diff.new_audited_at[:19]}")
    print("-" * 62)
    print(f"Health Score Delta: {sign}{diff.score_delta} points [{status_label}]")
    print(f"Pages Delta       : {diff.pages_delta:+d} ({diff.pages_count_old} -> {diff.pages_count_new})")
    print(f"Broken Links Delta: {diff.broken_delta:+d} ({diff.broken_count_old} -> {diff.broken_count_new})")
    print("-" * 62)

    if diff.new_issues:
        print(f"New Regressions Introduced ({len(diff.new_issues)}):")
        for item in diff.new_issues:
            print(f"  [X] {item['url']}: {item['issue']}")
    else:
        print("New Regressions: None")

    if diff.resolved_issues:
        print(f"\nResolved Issues Fixed ({len(diff.resolved_issues)}):")
        for item in diff.resolved_issues:
            print(f"  [V] {item['url']}: {item['issue']}")
    else:
        print("Resolved Issues: None")

    if diff.new_broken_links:
        print(f"\nNew Broken Links ({len(diff.new_broken_links)}):")
        for bl in diff.new_broken_links:
            print(f"  [!] {bl['target_url']} (status: {bl['status_code']}, source: {bl['source_url']})")

    if diff.fixed_broken_links:
        print(f"\nFixed Broken Links ({len(diff.fixed_broken_links)}):")
        for bl in diff.fixed_broken_links:
            print(f"  [V] {bl['target_url']}")

    if diff.meta_changes:
        print("\nDirective Changes:")
        for mc in diff.meta_changes:
            print(f"  [*] {mc}")

    print("=" * 62 + "\n")
    if getattr(args, "fail_on_regression", False) and (
        diff.score_delta < 0 or diff.new_issues or diff.new_broken_links
    ):
        print(
            "Regression gate failed: score dropped or new issues/broken links detected.",
            file=sys.stderr,
        )
        return 1
    return 0


def run_serve_command(args: argparse.Namespace) -> int:
    """Run FastAPI development/production web server."""
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required to run the web server.", file=sys.stderr)
        return 1

    host = args.host or os.getenv("HOST", "127.0.0.1")
    port = args.port or int(os.getenv("PORT", "8000"))

    print(f"Starting SEO Audit Web App at http://{host}:{port}")
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
        "--no-save",
        action="store_true",
        help="Do not save this audit to the local history database",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output audit report as JSON to stdout"
    )
    parser.add_argument(
        "--fail-under",
        type=int,
        default=None,
        help="Exit with code 1 if health score is below this threshold",
    )


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)

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

    if args_list and args_list[0] == "history":
        hist_parser = argparse.ArgumentParser(
            prog="seo-audit history", description="View recent audit reports"
        )
        hist_parser.add_argument(
            "--limit", type=int, default=20, help="Number of records to show (default: 20)"
        )
        hist_parser.add_argument(
            "--domain", type=str, default=None, help="Filter by target domain"
        )
        parsed_hist = hist_parser.parse_args(args_list[1:])
        return run_history_command(parsed_hist)

    if args_list and args_list[0] == "compare":
        comp_parser = argparse.ArgumentParser(
            prog="seo-audit compare", description="Compare two audit reports"
        )
        comp_parser.add_argument("report_id_1", help="First (baseline/earlier) report ID")
        comp_parser.add_argument("report_id_2", help="Second (newer) report ID")
        comp_parser.add_argument(
            "--json", action="store_true", help="Output diff result as JSON"
        )
        parsed_comp = comp_parser.parse_args(args_list[1:])
        return run_compare_command(parsed_comp)

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
