"""CSV and self-contained HTML report generators."""

from __future__ import annotations

import csv
import html
import io

from seo_audit.models import SiteAuditReport, classify_issue


def generate_csv_report(report: SiteAuditReport) -> str:
    """Generate RFC 4180 compliant CSV string with 22 standard columns."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

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
            "OG Title",
            "Images Missing Alt Count",
            "Heading Hierarchy Issues",
            "JSON-LD Valid",
            "Redirect Hops Count",
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
        missing_alt = sum(1 for img in page.image_issues if img.missing_alt)
        hierarchy_str = " | ".join(page.heading_hierarchy_issues)

        def _safe_csv_cell(val: object) -> object:
            if isinstance(val, str) and val and val[0] in ("=", "+", "-", "@", "\t", "\r"):
                return f"'{val}"
            return val

        writer.writerow(
            [
                _safe_csv_cell(c)
                for c in [
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
                    page.social_meta.og_title if page.social_meta else "",
                    missing_alt,
                    hierarchy_str,
                    "YES" if (page.has_json_ld and page.json_ld_valid) else "NO",
                    len(page.redirect_chain),
                    issues_str,
                ]
            ]
        )

    return output.getvalue()


def generate_html_report(report: SiteAuditReport) -> str:
    """Generate a self-contained, offline-ready light HTML5 audit report."""
    score = report.health_score
    score_color = (
        "#047857"
        if score >= 80
        else "#B45309"
        if score >= 50
        else "#B91C1C"
    )
    score_label = (
        "Excellent"
        if score >= 80
        else "Needs Attention"
        if score >= 50
        else "Critical Issues"
    )

    total_issues = sum(len(p.issues) for p in report.pages)
    total_broken = len(report.broken_links)
    total_missing_alt = sum(
        sum(1 for img in p.image_issues if img.missing_alt) for p in report.pages
    )
    llms_badge = (
        '<span class="directive-tag pass"><span class="bullet"></span>Found (/llms.txt)</span>'
        if report.site_meta.llms_txt_found
        else '<span class="directive-tag warn"><span class="bullet"></span>Missing (/llms.txt)</span>'
    )

    sev_counts = report.issue_counts_by_severity
    cat_counts = report.issue_counts_by_category

    # Circumference calculation for gauge (r=56) -> 2 * PI * 56 ~= 351.85
    circumference = 351.85
    dash_offset = circumference - (score / 100) * circumference

    pages_rows = []
    for p in report.pages:
        status_bg = (
            "#ECFDF5"
            if p.status_code and p.status_code < 300
            else "#FFFBEB"
            if p.status_code and p.status_code < 400
            else "#FEF2F2"
        )
        status_border = (
            "#A7F3D0"
            if p.status_code and p.status_code < 300
            else "#FDE68A"
            if p.status_code and p.status_code < 400
            else "#FECACA"
        )
        status_color = (
            "#065F46"
            if p.status_code and p.status_code < 300
            else "#92400E"
            if p.status_code and p.status_code < 400
            else "#991B1B"
        )
        status_text = str(p.status_code) if p.status_code else "ERR"

        page_categories = set()
        page_severities = set()
        issues_badges = []
        for i in p.issues:
            sev, cat = classify_issue(i)
            page_categories.add(cat)
            page_severities.add(sev)
            issues_badges.append(
                f'<span class="tag-pill tag-{sev}">{html.escape(i)}</span>'
            )

        if p.status_code and p.status_code >= 400:
            page_severities.add("critical")
            page_categories.add("crawlability")

        issues_html = (
            "".join(issues_badges)
            if issues_badges
            else '<span class="tag-pill tag-ok">✓ Healthy</span>'
        )

        cat_attr = " ".join(sorted(page_categories)) or "healthy"
        sev_attr = " ".join(sorted(page_severities)) or "healthy"

        pages_rows.append(
            f"""
            <tr class="page-row" data-categories="{cat_attr}" data-severities="{sev_attr}">
              <td class="mono font-xs cell-url">
                <a href="{html.escape(p.url)}" target="_blank" class="table-link font-medium">{html.escape(p.url)}</a>
              </td>
              <td><span class="status-badge" style="background:{status_bg}; border-color:{status_border}; color:{status_color}">{status_text}</span></td>
              <td class="mono font-xs text-muted">{p.response_time_ms:.0f}ms</td>
              <td>
                <div class="cell-title font-medium">{html.escape(p.title or '-')}</div>
                <div class="text-muted font-xxs">{p.title_length} characters</div>
              </td>
              <td class="text-center font-sm font-semibold">{len(p.h1_list)}</td>
              <td class="mono font-xxs text-muted cell-url">{html.escape(p.canonical_url or '-')}</td>
              <td><div class="tags-flex">{issues_html}</div></td>
            </tr>
            """
        )

    empty_pages = (
        '<tr><td colspan="7" class="empty-state empty-neutral">No internal pages were crawled in this audit.</td></tr>'
        if not pages_rows
        else "".join(pages_rows)
    )

    broken_rows = []
    for bl in report.broken_links:
        ext_badge = (
            '<span class="scope-pill scope-ext">External</span>'
            if bl.is_external
            else '<span class="scope-pill scope-int">Internal</span>'
        )
        broken_rows.append(
            f"""
            <tr>
              <td class="mono font-xs cell-url">{html.escape(bl.source_url)}</td>
              <td class="mono font-xs cell-url font-semibold text-danger">{html.escape(bl.target_url)}</td>
              <td>{ext_badge}</td>
              <td class="font-xs">{html.escape(bl.anchor_text or '-')}</td>
              <td><span class="status-badge status-err">{html.escape(bl.error or str(bl.status_code))}</span></td>
            </tr>
            """
        )

    empty_broken = (
        '<tr><td colspan="5" class="empty-state">No broken links found. All endpoints responded safely.</td></tr>'
        if not broken_rows
        else "".join(broken_rows)
    )

    robots_badge = (
        '<span class="directive-tag pass"><span class="bullet"></span>Valid & Present</span>'
        if report.site_meta.robots_found
        else '<span class="directive-tag warn"><span class="bullet"></span>Not Found</span>'
    )
    sitemap_badge = (
        f'<span class="directive-tag pass"><span class="bullet"></span>Valid XML ({report.site_meta.sitemap_url_count} URLs)</span>'
        if report.site_meta.sitemap_found and report.site_meta.sitemap_valid_xml
        else '<span class="directive-tag warn"><span class="bullet"></span>Missing / Invalid</span>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SEO Audit Report - {html.escape(report.target_url)}</title>
  <style>
    :root {{
      --bg: #F8FAFC;
      --surface: #FFFFFF;
      --surface-subtle: #F1F5F9;
      --border: #E2E8F0;
      --border-subtle: #EDF2F7;
      --text: #0F172A;
      --text-muted: #475569;

      --brand-primary: #0052CC;
      --brand-primary-hover: #003E99;
      --brand-accent: #C2410C;
      --green: #047857;
      --amber: #B45309;
      --red: #B91C1C;

      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 14px;
      --radius-xl: 18px;
      --shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.04);
      --shadow-card: 0 4px 16px -2px rgba(15, 23, 42, 0.06), 0 2px 4px -1px rgba(15, 23, 42, 0.03);
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 40px 24px 80px;
      -webkit-font-smoothing: antialiased;
    }}
    .container {{ max-width: 1240px; margin: 0 auto; }}

    .report-header-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-xl);
      padding: 36px 40px;
      margin-bottom: 28px;
      display: grid;
      grid-template-columns: 1fr 240px;
      gap: 32px;
      align-items: center;
      box-shadow: var(--shadow-card);
    }}
    .eyebrow {{
      font-size: 0.75rem;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--brand-primary);
      margin-bottom: 8px;
    }}
    h1.target-url {{
      font-size: 2rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: var(--text);
      word-break: break-all;
      margin-bottom: 12px;
      line-height: 1.2;
    }}
    .meta-bar {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
      font-size: 0.875rem;
      color: var(--text-muted);
      margin-bottom: 24px;
    }}
    .meta-badge {{
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      padding: 3px 10px;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text);
    }}

    /* Circular SVG Gauge */
    .gauge-box {{
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
    }}
    .circle-gauge {{
      width: 136px;
      height: 136px;
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .circle-gauge svg {{
      transform: rotate(-90deg);
      width: 100%;
      height: 100%;
    }}
    .gauge-track {{
      fill: none;
      stroke: #E2E8F0;
      stroke-width: 10;
    }}
    .gauge-progress {{
      fill: none;
      stroke-width: 10;
      stroke-linecap: round;
    }}
    .gauge-inner {{
      position: absolute;
      text-align: center;
      padding: 0 14px;
    }}
    .gauge-val {{
      font-size: 1.6rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      line-height: 1;
    }}
    .gauge-sub {{
      font-size: 0.6rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      line-height: 1.15;
      margin-top: 4px;
      color: var(--text-muted);
    }}

    /* Stat Cards Grid */
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 28px;
    }}
    .stat-box {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 22px 24px;
      box-shadow: var(--shadow-sm);
    }}
    .stat-label {{
      font-size: 0.725rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-muted);
      margin-bottom: 8px;
    }}
    .stat-number {{
      font-size: 1.85rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      line-height: 1;
    }}
    .stat-caption {{
      font-size: 0.775rem;
      color: var(--text-muted);
      margin-top: 8px;
      font-weight: 500;
    }}

    .directive-tag {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 0.8rem;
      font-weight: 600;
    }}
    .directive-tag .bullet {{
      width: 6px;
      height: 6px;
      border-radius: 50%;
    }}
    .directive-tag.pass .bullet {{ background: var(--green); }}
    .directive-tag.warn .bullet {{ background: var(--amber); }}

    /* Table Panels */
    .panel-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-xl);
      margin-bottom: 28px;
      box-shadow: var(--shadow-sm);
      overflow: hidden;
    }}
    .panel-header {{
      padding: 20px 28px;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #FFFFFF;
    }}
    .panel-title {{
      font-size: 1.05rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    .table-responsive {{
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }}
    th, td {{
      padding: 13px 20px;
      border-bottom: 1px solid var(--border-subtle);
      vertical-align: middle;
    }}
    th {{
      background: var(--surface-subtle);
      font-size: 0.725rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
    }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #F8FAFC; }}

    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .font-sm {{ font-size: 0.875rem; }}
    .font-xs {{ font-size: 0.8rem; }}
    .font-xxs {{ font-size: 0.725rem; }}
    .font-semibold {{ font-weight: 600; }}
    .font-medium {{ font-weight: 500; }}
    .text-muted {{ color: var(--text-muted); }}
    .text-danger {{ color: var(--red); }}
    .text-center {{ text-align: center; }}

    .cell-url {{
      max-width: 280px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .cell-title {{
      max-width: 240px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .table-link {{
      color: var(--brand-primary);
      text-decoration: none;
    }}
    .table-link:hover {{
      color: var(--brand-primary-hover);
      text-decoration: underline;
    }}
    .table-link:focus-visible,
    .tab-btn:focus-visible,
    .sev-pill-btn:focus-visible {{
      outline: 2px solid var(--brand-primary);
      outline-offset: 2px;
    }}

    .status-badge {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: var(--radius-sm);
      border: 1px solid transparent;
      font-size: 0.75rem;
      font-weight: 700;
    }}
    .status-err {{
      background: #FEF2F2;
      border-color: #FECACA;
      color: #991B1B;
    }}

    .scope-pill {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 9999px;
      font-size: 0.725rem;
      font-weight: 600;
    }}
    .scope-int {{ background: #F1F5F9; color: #334155; }}
    .scope-ext {{ background: #EFF6FF; color: var(--brand-primary); }}

    .tags-flex {{
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
    }}
    .tag-pill {{
      display: inline-block;
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 0.725rem;
      font-weight: 500;
    }}
    .tag-ok {{ background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0; }}
    .tag-warn {{ background: #FFFBEB; color: #92400E; border: 1px solid #FDE68A; }}
    .tag-critical {{ background: #FEF2F2; color: #991B1B; border: 1px solid #FECACA; }}
    .tag-warning {{ background: #FFFBEB; color: #92400E; border: 1px solid #FDE68A; }}
    .tag-notice {{ background: #F1F5F9; color: #334155; border: 1px solid #CBD5E1; }}

    /* Category Tabs and Filter Controls */
    .filter-bar {{
      padding: 12px 24px;
      background: var(--surface);
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }}
    .tabs-group {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .tab-btn {{
      min-height: 44px;
      padding: 8px 14px;
      font-size: 0.8rem;
      font-weight: 600;
      border-radius: var(--radius-sm);
      border: 1px solid transparent;
      background: transparent;
      color: var(--text-muted);
      cursor: pointer;
      font-family: inherit;
      transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
    }}
    .tab-btn:hover {{
      color: var(--text);
      background: var(--surface-subtle);
    }}
    .tab-btn:active {{
      transform: translateY(1px);
    }}
    .tab-btn.active {{
      background: #EFF6FF;
      border-color: #BFDBFE;
      color: var(--brand-primary);
      font-weight: 700;
    }}
    .severity-group {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
    }}
    .sev-pill-btn {{
      min-height: 44px;
      padding: 8px 14px;
      font-size: 0.775rem;
      font-weight: 600;
      border-radius: 20px;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text-muted);
      cursor: pointer;
      font-family: inherit;
      transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
    }}
    .sev-pill-btn:hover {{
      border-color: var(--text-muted);
      color: var(--text);
    }}
    .sev-pill-btn:active {{
      transform: translateY(1px);
    }}
    .sev-pill-btn.active {{
      font-weight: 700;
      border-color: var(--text);
      color: var(--text);
      background: var(--surface-subtle);
    }}
    .sev-pill-btn.sev-crit.active {{
      background: #FEF2F2;
      border-color: #FECACA;
      color: #991B1B;
    }}
    .sev-pill-btn.sev-warn.active {{
      background: #FFFBEB;
      border-color: #FDE68A;
      color: #92400E;
    }}
    .sev-pill-btn.sev-info.active {{
      background: #F1F5F9;
      border-color: #CBD5E1;
      color: #334155;
    }}

    .empty-state {{
      text-align: center;
      padding: 36px 20px;
      color: var(--green);
      font-size: 0.925rem;
      font-weight: 600;
    }}
    .empty-state.empty-neutral {{
      color: var(--text-muted);
    }}

    @media (max-width: 900px) {{
      body {{ padding: 28px 18px 64px; }}
      .report-header-card {{ grid-template-columns: 1fr; padding: 28px; gap: 24px; }}
      .stats-grid {{ grid-template-columns: 1fr 1fr; }}
      .panel-header {{ flex-wrap: wrap; gap: 8px; padding: 18px 20px; }}
      .filter-bar {{ padding: 12px 20px; }}
    }}
    @media (max-width: 560px) {{
      body {{ padding: 16px 12px 48px; }}
      .report-header-card {{ padding: 20px 18px; gap: 20px; }}
      h1.target-url {{ font-size: 1.45rem; }}
      .stats-grid {{ grid-template-columns: 1fr; }}
      .stat-box {{ padding: 18px; }}
      .panel-header {{ padding: 16px; }}
      .filter-bar {{ padding: 12px 16px; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{ transition: none !important; animation: none !important; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <header class="report-header-card">
      <div>
        <div class="eyebrow">SEO Audit Report</div>
        <h1 class="target-url">{html.escape(report.target_url)}</h1>
        <div class="meta-bar">
          <span class="meta-badge"><strong>{len(report.pages)}</strong> Pages Audited</span>
          <span class="meta-badge"><strong>{report.duration_seconds}s</strong> Crawl Duration</span>
          <span class="text-muted font-xs">Generated: {html.escape(report.audited_at)}</span>
        </div>
      </div>

      <div class="gauge-box">
        <div class="circle-gauge">
          <svg viewBox="0 0 136 136">
            <circle class="gauge-track" cx="68" cy="68" r="56" />
            <circle class="gauge-progress" cx="68" cy="68" r="56"
                    stroke="{score_color}"
                    stroke-dasharray="{circumference}"
                    stroke-dashoffset="{dash_offset}" />
          </svg>
          <div class="gauge-inner">
            <div class="gauge-val" style="color: {score_color};">{score}/100</div>
            <div class="gauge-sub">{score_label}</div>
          </div>
        </div>
        <div class="font-xs text-muted font-semibold" style="margin-top: 8px;">Overall Health Score</div>
      </div>
    </header>

    <main>
    <div class="stats-grid">
      <div class="stat-box">
        <div class="stat-label">Total Pages Crawled</div>
        <div class="stat-number">{len(report.pages)}</div>
        <div class="stat-caption">Internal BFS discovery</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Total Issues Flagged</div>
        <div class="stat-number" style="color: {'#B91C1C' if total_issues > 0 else 'var(--text)'};">{total_issues}</div>
        <div class="stat-caption">Includes {total_missing_alt} image alt issues</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Broken Links (404/5xx)</div>
        <div class="stat-number" style="color: {'#B91C1C' if total_broken > 0 else '#047857'};">{total_broken}</div>
        <div class="stat-caption">{'Requires dead link fixes' if total_broken > 0 else 'All links validated safe'}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">AI & Search Directives</div>
        <div style="margin-top: 4px;">robots.txt: {robots_badge}</div>
        <div style="margin-top: 4px;">sitemap.xml: {sitemap_badge}</div>
        <div style="margin-top: 4px;">AI llms.txt: {llms_badge}</div>
      </div>
    </div>

    <div class="panel-card">
      <div class="panel-header">
        <div class="panel-title">Audited Internal Pages</div>
        <div class="text-muted font-xs">{len(report.pages)} pages crawled</div>
      </div>
      <div class="filter-bar">
        <div class="tabs-group">
          <button type="button" class="tab-btn active" aria-pressed="true" data-cat="all">All Pages ({len(report.pages)})</button>
          <button type="button" class="tab-btn" aria-pressed="false" data-cat="crawlability">Crawlability ({cat_counts['crawlability']})</button>
          <button type="button" class="tab-btn" aria-pressed="false" data-cat="on_page">On-Page ({cat_counts['on_page']})</button>
          <button type="button" class="tab-btn" aria-pressed="false" data-cat="images">Images ({cat_counts['images']})</button>
          <button type="button" class="tab-btn" aria-pressed="false" data-cat="social">Social & Schema ({cat_counts['social']})</button>
          <button type="button" class="tab-btn" aria-pressed="false" data-cat="directives">Directives ({cat_counts['directives']})</button>
        </div>
        <div class="severity-group">
          <span style="font-size: 0.725rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Severity:</span>
          <button type="button" class="sev-pill-btn active" aria-pressed="true" data-sev="all">All</button>
          <button type="button" class="sev-pill-btn sev-crit" aria-pressed="false" data-sev="critical">Critical ({sev_counts['critical']})</button>
          <button type="button" class="sev-pill-btn sev-warn" aria-pressed="false" data-sev="warning">Warning ({sev_counts['warning']})</button>
          <button type="button" class="sev-pill-btn sev-info" aria-pressed="false" data-sev="notice">Notice ({sev_counts['notice']})</button>
        </div>
      </div>
      <div class="table-responsive">
        <table>
          <thead>
            <tr>
              <th>Target URL</th>
              <th>Status</th>
              <th>Latency</th>
              <th>Page Title</th>
              <th class="text-center">H1</th>
              <th>Canonical Tag</th>
              <th>On-Page Findings</th>
            </tr>
          </thead>
          <tbody>
            {empty_pages}
            <tr id="noMatchesRow" style="display: none;">
              <td colspan="7" class="empty-state empty-neutral">No pages match the active category and severity filters.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="panel-card">
      <div class="panel-header">
        <div class="panel-title">Broken Links (404 & Dead Endpoints)</div>
        <div class="text-muted font-xs">{total_broken} links detected</div>
      </div>
      <div class="table-responsive">
        <table>
          <thead>
            <tr>
              <th>Originating Page</th>
              <th>Broken Target Link</th>
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
    </main>
  </div>

  <script>
    let activeCat = 'all';
    let activeSev = 'all';

    function applyFilters() {{
      const rows = document.querySelectorAll('.page-row');
      if (rows.length === 0) return;
      let visible = 0;
      rows.forEach(r => {{
        const cats = (r.getAttribute('data-categories') || '').split(' ');
        const sevs = (r.getAttribute('data-severities') || '').split(' ');

        const matchCat = (activeCat === 'all') || cats.includes(activeCat);
        const matchSev = (activeSev === 'all') || sevs.includes(activeSev);

        if (matchCat && matchSev) {{
          r.style.display = '';
          visible++;
        }} else {{
          r.style.display = 'none';
        }}
      }});

      const noMatch = document.getElementById('noMatchesRow');
      if (noMatch) {{
        noMatch.style.display = visible === 0 ? '' : 'none';
      }}
    }}

    document.querySelectorAll('.tab-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.tab-btn').forEach(b => {{
          b.classList.remove('active');
          b.setAttribute('aria-pressed', 'false');
        }});
        btn.classList.add('active');
        btn.setAttribute('aria-pressed', 'true');
        activeCat = btn.getAttribute('data-cat');
        applyFilters();
      }});
    }});

    document.querySelectorAll('.sev-pill-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.sev-pill-btn').forEach(b => {{
          b.classList.remove('active');
          b.setAttribute('aria-pressed', 'false');
        }});
        btn.classList.add('active');
        btn.setAttribute('aria-pressed', 'true');
        activeSev = btn.getAttribute('data-sev');
        applyFilters();
      }});
    }});
  </script>
</body>
</html>
"""
