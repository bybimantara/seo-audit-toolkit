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
    """Generate self-contained, minimal and elegant HTML5 report."""
    score_color = (
        "#0F766E"
        if report.health_score >= 80
        else "#B45309"
        if report.health_score >= 50
        else "#B91C1C"
    )

    total_issues = sum(len(p.issues) for p in report.pages)
    total_broken = len(report.broken_links)

    # Render pages table rows
    pages_rows = []
    for p in report.pages:
        status_badge_bg = (
            "#F0FDF4"
            if p.status_code and p.status_code < 300
            else "#FFFBEB"
            if p.status_code and p.status_code < 400
            else "#FEF2F2"
        )
        status_badge_border = (
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
        status_text = str(p.status_code) if p.status_code else "ERR"

        issues_html = (
            "".join(
                f'<span class="tag tag-issue">{html.escape(i)}</span>'
                for i in p.issues
            )
            if p.issues
            else '<span class="tag tag-ok">Healthy</span>'
        )

        pages_rows.append(
            f"""
            <tr>
              <td class="mono font-xs cell-url"><a href="{html.escape(p.url)}" target="_blank" class="table-link">{html.escape(p.url)}</a></td>
              <td><span class="badge" style="background:{status_badge_bg}; border-color:{status_badge_border}; color:{status_badge_color}">{status_text}</span></td>
              <td class="mono font-xs muted">{p.response_time_ms:.0f}ms</td>
              <td>
                <div class="cell-title">{html.escape(p.title or '—')}</div>
                <div class="muted font-xxs">{p.title_length} chars</div>
              </td>
              <td class="center font-sm">{len(p.h1_list)}</td>
              <td class="mono font-xxs muted cell-url">{html.escape(p.canonical_url or '—')}</td>
              <td><div class="tags-wrapper">{issues_html}</div></td>
            </tr>
            """
        )

    # Render broken links rows
    broken_rows = []
    for bl in report.broken_links:
        ext_badge = (
            '<span class="badge badge-ext">External</span>'
            if bl.is_external
            else '<span class="badge badge-int">Internal</span>'
        )
        broken_rows.append(
            f"""
            <tr>
              <td class="mono font-xs cell-url">{html.escape(bl.source_url)}</td>
              <td class="mono font-xs cell-url font-medium">{html.escape(bl.target_url)}</td>
              <td>{ext_badge}</td>
              <td class="font-xs">{html.escape(bl.anchor_text or '—')}</td>
              <td><span class="badge badge-err">{html.escape(bl.error or str(bl.status_code))}</span></td>
            </tr>
            """
        )

    empty_broken = (
        '<tr><td colspan="5" class="empty-state">No broken links found. All endpoints responded safely.</td></tr>'
        if not broken_rows
        else "".join(broken_rows)
    )

    robots_badge = (
        '<span class="status-indicator pass"><span class="dot"></span>Accessible</span>'
        if report.site_meta.robots_found
        else '<span class="status-indicator warn"><span class="dot"></span>Not Found</span>'
    )
    sitemap_badge = (
        f'<span class="status-indicator pass"><span class="dot"></span>Valid ({report.site_meta.sitemap_url_count} URLs)</span>'
        if report.site_meta.sitemap_found and report.site_meta.sitemap_valid_xml
        else '<span class="status-indicator warn"><span class="dot"></span>Missing / Invalid</span>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SEO Audit Report - {html.escape(report.target_url)}</title>
  <style>
    :root {{
      --bg: #FAFAF9;
      --surface: #FFFFFF;
      --border: #E7E5E4;
      --border-subtle: #F0F0EE;
      --text: #1C1917;
      --text-muted: #78716C;
      --text-light: #A8A29E;
      --radius: 12px;
      --shadow: 0 1px 3px rgba(0,0,0,0.03), 0 6px 16px -4px rgba(0,0,0,0.02);
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 48px 24px;
      -webkit-font-smoothing: antialiased;
    }}
    .container {{ max-width: 1280px; margin: 0 auto; }}
    
    header {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 28px 32px;
      margin-bottom: 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: var(--shadow);
    }}
    .brand-tag {{
      font-size: 0.725rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text-light);
      margin-bottom: 4px;
    }}
    h1 {{
      font-size: 1.5rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, "JetBrains Mono", Consolas, monospace; }}
    .font-sm {{ font-size: 0.875rem; }}
    .font-xs {{ font-size: 0.8rem; }}
    .font-xxs {{ font-size: 0.7rem; }}
    .font-medium {{ font-weight: 500; }}
    .muted {{ color: var(--text-muted); }}
    .center {{ text-align: center; }}
    
    .score-badge {{
      display: flex;
      flex-direction: column;
      align-items: flex-end;
    }}
    .score-num {{
      font-size: 2.75rem;
      font-weight: 800;
      letter-spacing: -0.04em;
      line-height: 1;
      color: {score_color};
    }}
    .score-label {{
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-light);
      margin-top: 4px;
    }}

    .grid-stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .stat-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 20px 24px;
      box-shadow: var(--shadow);
    }}
    .stat-title {{
      font-size: 0.725rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-light);
      margin-bottom: 6px;
    }}
    .stat-val {{
      font-size: 1.6rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    
    .status-indicator {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.825rem;
      font-weight: 500;
    }}
    .status-indicator .dot {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
    }}
    .status-indicator.pass .dot {{ background: #0F766E; }}
    .status-indicator.warn .dot {{ background: #D97706; }}

    .section-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      margin-bottom: 24px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .section-header {{
      padding: 20px 24px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    h2 {{
      font-size: 1rem;
      font-weight: 600;
      letter-spacing: -0.01em;
    }}
    .table-wrap {{
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }}
    th, td {{
      padding: 12px 18px;
      border-bottom: 1px solid var(--border-subtle);
      vertical-align: middle;
    }}
    th {{
      background: #FDFCFC;
      font-size: 0.7rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-light);
    }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #FAFAF9; }}
    
    .cell-url {{
      max-width: 280px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .cell-title {{
      font-size: 0.825rem;
      font-weight: 500;
      max-width: 220px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .table-link {{
      color: var(--text);
      text-decoration: none;
    }}
    .table-link:hover {{
      text-decoration: underline;
    }}
    
    .badge {{
      display: inline-block;
      padding: 2px 7px;
      border-radius: 5px;
      border: 1px solid transparent;
      font-size: 0.725rem;
      font-weight: 600;
      letter-spacing: -0.01em;
    }}
    .badge-int {{ background: #F5F5F4; border-color: #E7E5E4; color: #57534E; }}
    .badge-ext {{ background: #F0F9FF; border-color: #E0F2FE; color: #0284C7; }}
    .badge-err {{ background: #FEF2F2; border-color: #FEE2E2; color: #DC2626; }}
    
    .tags-wrapper {{
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }}
    .tag {{
      display: inline-block;
      padding: 1px 6px;
      border-radius: 4px;
      font-size: 0.7rem;
      font-weight: 500;
    }}
    .tag-ok {{ background: #F0FDF4; color: #16A34A; }}
    .tag-issue {{ background: #FFFBEB; color: #B45309; border: 1px solid #FEF3C7; }}
    .empty-state {{
      text-align: center;
      padding: 36px;
      color: #0F766E;
      font-size: 0.9rem;
      font-weight: 500;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <div class="brand-tag">SEO Audit Toolkit</div>
        <h1>{html.escape(report.target_url)}</h1>
        <p class="muted font-xs" style="margin-top: 4px;">Audited at {html.escape(report.audited_at)} · Duration {report.duration_seconds}s</p>
      </div>
      <div class="score-badge">
        <div class="score-num">{report.health_score}/100</div>
        <div class="score-label">Health Score</div>
      </div>
    </header>

    <div class="grid-stats">
      <div class="stat-card">
        <div class="stat-title">Pages Analyzed</div>
        <div class="stat-val">{len(report.pages)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-title">Issues Flagged</div>
        <div class="stat-val" style="color: {'#B91C1C' if total_issues > 0 else 'var(--text)'};">{total_issues}</div>
      </div>
      <div class="stat-card">
        <div class="stat-title">Broken Links</div>
        <div class="stat-val" style="color: {'#DC2626' if total_broken > 0 else '#0F766E'};">{total_broken}</div>
      </div>
      <div class="stat-card">
        <div class="stat-title">Site Meta Directives</div>
        <div style="margin-top: 4px;">robots.txt: {robots_badge}</div>
        <div style="margin-top: 2px;">sitemap.xml: {sitemap_badge}</div>
      </div>
    </div>

    <div class="section-card">
      <div class="section-header">
        <h2>Internal Pages Audited</h2>
        <span class="muted font-xs">{len(report.pages)} results</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>URL</th>
              <th>Status</th>
              <th>Latency</th>
              <th>Title</th>
              <th class="center">H1</th>
              <th>Canonical</th>
              <th>Issues</th>
            </tr>
          </thead>
          <tbody>
            {"".join(pages_rows)}
          </tbody>
        </table>
      </div>
    </div>

    <div class="section-card">
      <div class="section-header">
        <h2>Broken Links (404 & Dead URLs)</h2>
        <span class="muted font-xs">{total_broken} detected</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Originating Page</th>
              <th>Broken Target URL</th>
              <th>Scope</th>
              <th>Anchor Context</th>
              <th>HTTP Error</th>
            </tr>
          </thead>
          <tbody>
            {empty_broken}
          </tbody>
        </table>
      </div>
    </div>
  </div>
</body>
</html>
"""
