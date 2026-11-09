"""CSV and self-contained HTML report generators."""

from __future__ import annotations

import csv
import html
import io

from seo_audit.models import SiteAuditReport


def generate_csv_report(report: SiteAuditReport) -> str:
    """Generate RFC 4180 compliant CSV string with 17 standard columns."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    # Write Header
    writer.writerow(
        [
            "URL",
            "HTTP Status",
            "Response Time (ms)",
            "Title",
            "Title Length",
            "Meta Description",
            "Description Length",
            "H1 Count",
            "H1 Text",
            "H2 Count",
            "H2 Preview",
            "Canonical URL",
            "Internal Links Count",
            "External Links Count",
            "Broken Links Count",
            "Broken Links Detail",
            "SEO Issues",
        ]
    )

    for page in report.pages:
        h1_str = " | ".join(page.h1_list)
        h2_str = " | ".join(page.h2_list[:3])
        broken_str = " | ".join(
            f"{bl.target_url} ({bl.error or bl.status_code})"
            for bl in page.broken_links
        )
        issues_str = " | ".join(page.issues)

        writer.writerow(
            [
                page.url,
                page.status_code if page.status_code is not None else "ERROR",
                round(page.response_time_ms, 1),
                page.title,
                page.title_length,
                page.meta_description,
                page.description_length,
                len(page.h1_list),
                h1_str,
                len(page.h2_list),
                h2_str,
                page.canonical_url,
                page.internal_links_count,
                page.external_links_count,
                len(page.broken_links),
                broken_str,
                issues_str,
            ]
        )

    return output.getvalue()


def generate_html_report(report: SiteAuditReport) -> str:
    """Generate self-contained HTML5 report with inline styling and metrics."""
    score_color = (
        "#15803D"
        if report.health_score >= 80
        else "#B45309"
        if report.health_score >= 50
        else "#B91C1C"
    )
    score_bg = (
        "#DCFCE7"
        if report.health_score >= 80
        else "#FEF3C7"
        if report.health_score >= 50
        else "#FEE2E2"
    )

    total_issues = sum(len(p.issues) for p in report.pages)
    total_broken = len(report.broken_links)

    # Render pages table rows
    pages_rows = []
    for p in report.pages:
        status_badge_bg = (
            "#DCFCE7"
            if p.status_code and p.status_code < 300
            else "#FEF3C7"
            if p.status_code and p.status_code < 400
            else "#FEE2E2"
        )
        status_badge_color = (
            "#15803D"
            if p.status_code and p.status_code < 300
            else "#B45309"
            if p.status_code and p.status_code < 400
            else "#B91C1C"
        )
        status_text = str(p.status_code) if p.status_code else "ERROR"

        issues_html = (
            "".join(
                f'<span class="badge badge-warning">{html.escape(i)}</span> '
                for i in p.issues
            )
            if p.issues
            else '<span class="badge badge-success">No issues</span>'
        )

        pages_rows.append(
            f"""
            <tr>
              <td class="mono font-sm">{html.escape(p.url)}</td>
              <td><span class="badge" style="background:{status_badge_bg}; color:{status_badge_color}">{status_text}</span></td>
              <td class="mono">{p.response_time_ms:.1f}ms</td>
              <td>{html.escape(p.title or '-')} <span class="muted font-xs">({p.title_length})</span></td>
              <td>{len(p.h1_list)}</td>
              <td class="mono font-sm">{html.escape(p.canonical_url or '-')}</td>
              <td>{issues_html}</td>
            </tr>
            """
        )

    # Render broken links rows
    broken_rows = []
    for bl in report.broken_links:
        ext_badge = (
            '<span class="badge badge-info">External</span>'
            if bl.is_external
            else '<span class="badge badge-neutral">Internal</span>'
        )
        broken_rows.append(
            f"""
            <tr>
              <td class="mono font-sm">{html.escape(bl.source_url)}</td>
              <td class="mono font-sm font-bold">{html.escape(bl.target_url)}</td>
              <td>{ext_badge}</td>
              <td>{html.escape(bl.anchor_text or '-')}</td>
              <td><span class="badge badge-error">{html.escape(bl.error or str(bl.status_code))}</span></td>
            </tr>
            """
        )

    empty_broken = (
        '<tr><td colspan="5" style="text-align:center; color:#15803D; padding:24px;">🎉 Great news! No broken links found.</td></tr>'
        if not broken_rows
        else "".join(broken_rows)
    )

    robots_badge = (
        '<span class="badge badge-success">Found & Valid</span>'
        if report.site_meta.robots_found
        else '<span class="badge badge-warning">Missing</span>'
    )
    sitemap_badge = (
        f'<span class="badge badge-success">Valid ({report.site_meta.sitemap_url_count} URLs)</span>'
        if report.site_meta.sitemap_found and report.site_meta.sitemap_valid_xml
        else '<span class="badge badge-warning">Missing / Invalid</span>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SEO Audit Report - {html.escape(report.target_url)}</title>
  <style>
    :root {{
      --background: #F8FAFC;
      --surface: #FFFFFF;
      --foreground: #0F172A;
      --muted: #64748B;
      --border: #E2E8F0;
      --primary: #0F766E;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--background);
      color: var(--foreground);
      line-height: 1.5;
      padding: 24px;
    }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    header {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 24px;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
    }}
    h1 {{ font-size: 1.5rem; font-weight: 700; color: #0F172A; }}
    h2 {{ font-size: 1.15rem; font-weight: 600; margin-bottom: 12px; }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }}
    .font-sm {{ font-size: 0.85rem; }}
    .font-xs {{ font-size: 0.75rem; }}
    .font-bold {{ font-weight: 600; }}
    .muted {{ color: var(--muted); }}
    
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
    }}
    .score-circle {{
      font-size: 2.25rem;
      font-weight: 800;
      line-height: 1;
      display: inline-block;
      padding: 8px 16px;
      border-radius: 8px;
    }}
    .table-container {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 24px;
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }}
    th, td {{
      padding: 10px 14px;
      border-bottom: 1px solid var(--border);
    }}
    th {{
      background: #F1F5F9;
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
    }}
    tr:hover td {{ background: #F8FAFC; }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 600;
    }}
    .badge-success {{ background: #DCFCE7; color: #15803D; }}
    .badge-warning {{ background: #FEF3C7; color: #B45309; }}
    .badge-error {{ background: #FEE2E2; color: #B91C1C; }}
    .badge-info {{ background: #E0F2FE; color: #0369A1; }}
    .badge-neutral {{ background: #F1F5F9; color: #475569; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>🔍 SEO Audit Report</h1>
        <p class="mono muted font-sm">Target: {html.escape(report.target_url)}</p>
        <p class="muted font-xs">Audited at: {html.escape(report.audited_at)} ({report.duration_seconds}s)</p>
      </div>
      <div>
        <span class="score-circle" style="background:{score_bg}; color:{score_color}">
          {report.health_score}/100
        </span>
      </div>
    </header>

    <div class="grid">
      <div class="card">
        <div class="muted font-xs font-bold">TOTAL PAGES CRAWLED</div>
        <div style="font-size: 1.75rem; font-weight: 700; margin-top: 4px;">{len(report.pages)}</div>
      </div>
      <div class="card">
        <div class="muted font-xs font-bold">TOTAL ISSUES FOUND</div>
        <div style="font-size: 1.75rem; font-weight: 700; margin-top: 4px; color: {score_color};">{total_issues}</div>
      </div>
      <div class="card">
        <div class="muted font-xs font-bold">BROKEN LINKS (404/5xx)</div>
        <div style="font-size: 1.75rem; font-weight: 700; margin-top: 4px; color: {'#B91C1C' if total_broken > 0 else '#15803D'};">{total_broken}</div>
      </div>
      <div class="card">
        <div class="muted font-xs font-bold">ROBOTS & SITEMAP</div>
        <div style="margin-top: 8px;">robots.txt: {robots_badge}</div>
        <div style="margin-top: 4px;">sitemap.xml: {sitemap_badge}</div>
      </div>
    </div>

    <div class="table-container">
      <h2>Pages Audited ({len(report.pages)})</h2>
      <table>
        <thead>
          <tr>
            <th>URL</th>
            <th>Status</th>
            <th>Latency</th>
            <th>Title</th>
            <th>H1</th>
            <th>Canonical</th>
            <th>Issues</th>
          </tr>
        </thead>
        <tbody>
          {"".join(pages_rows)}
        </tbody>
      </table>
    </div>

    <div class="table-container">
      <h2>Broken Links Detected ({total_broken})</h2>
      <table>
        <thead>
          <tr>
            <th>Source Page</th>
            <th>Target Link</th>
            <th>Type</th>
            <th>Anchor Text</th>
            <th>Status / Error</th>
          </tr>
        </thead>
        <tbody>
          {empty_broken}
        </tbody>
      </table>
    </div>
  </div>
</body>
</html>
"""
