"""FastAPI web application for SEO Audit Toolkit."""

from __future__ import annotations

import os
from collections import OrderedDict
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, HttpUrl

from seo_audit.crawler import crawl_site
from seo_audit.models import SiteAuditReport
from seo_audit.reporters import generate_csv_report, generate_html_report

app = FastAPI(title="SEO Audit Toolkit", version="0.1.0")

# In-memory LRU report cache (last 20 reports)
REPORT_CACHE: OrderedDict[str, SiteAuditReport] = OrderedDict()
MAX_CACHE_SIZE = 20


class AuditRequest(BaseModel):
    url: HttpUrl
    max_pages: int = 30
    max_external_links: int = 50


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SEO Audit Toolkit — Elegant Automated Auditor</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #FAFAF9;
      --surface: #FFFFFF;
      --surface-subtle: #F5F5F4;
      --border: #E7E5E4;
      --border-focus: #1C1917;
      --text: #1C1917;
      --text-muted: #78716C;
      --text-light: #A8A29E;
      --accent: #0F766E;
      --accent-hover: #115E59;
      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 16px;
      --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04);
      --shadow-card: 0 4px 20px -2px rgba(0, 0, 0, 0.04), 0 2px 6px -1px rgba(0, 0, 0, 0.02);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
      padding: 64px 20px;
    }
    .wrapper {
      max-width: 680px;
      margin: 0 auto;
    }
    .brand {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 4px 12px;
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: 24px;
    }
    .brand-dot {
      width: 6px;
      height: 6px;
      background: var(--accent);
      border-radius: 50%;
    }
    .header {
      margin-bottom: 40px;
    }
    h1 {
      font-size: 2.25rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: var(--text);
      line-height: 1.15;
      margin-bottom: 12px;
    }
    p.subtitle {
      color: var(--text-muted);
      font-size: 1.05rem;
      font-weight: 400;
      max-width: 580px;
    }
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 36px;
      box-shadow: var(--shadow-card);
    }
    .form-group {
      margin-bottom: 24px;
    }
    label {
      display: flex;
      justify-content: space-between;
      font-size: 0.825rem;
      font-weight: 600;
      color: var(--text);
      margin-bottom: 8px;
      letter-spacing: -0.01em;
    }
    .label-hint {
      color: var(--text-light);
      font-weight: 400;
      font-size: 0.75rem;
    }
    input[type="url"], input[type="number"] {
      width: 100%;
      padding: 12px 16px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      font-size: 0.95rem;
      font-family: inherit;
      color: var(--text);
      transition: all 0.15s ease;
    }
    input[type="url"] {
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.875rem;
    }
    input:focus {
      outline: none;
      border-color: var(--border-focus);
      box-shadow: 0 0 0 3px rgba(28, 25, 23, 0.06);
    }
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }
    button.btn-primary {
      width: 100%;
      padding: 14px 20px;
      background: #1C1917;
      color: #FAFAF9;
      border: 1px solid #1C1917;
      border-radius: var(--radius-md);
      font-size: 0.95rem;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: all 0.2s ease;
    }
    button.btn-primary:hover {
      background: #292524;
      border-color: #292524;
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    button.btn-primary:active {
      transform: translateY(0);
    }
    button.btn-primary:disabled {
      background: var(--text-light);
      border-color: var(--text-light);
      cursor: not-allowed;
      transform: none;
      box-shadow: none;
    }
    #status {
      margin-top: 28px;
      display: none;
    }
    .status-panel {
      padding: 24px;
      border-radius: var(--radius-md);
      border: 1px solid var(--border);
      background: var(--surface-subtle);
      animation: fadeIn 0.3s ease;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(4px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .metrics-row {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
      margin: 16px 0;
      padding: 16px 0;
      border-top: 1px solid var(--border);
      border-bottom: 1px solid var(--border);
    }
    .metric-item {
      text-align: center;
    }
    .metric-value {
      font-size: 1.5rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: var(--text);
    }
    .metric-label {
      font-size: 0.725rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-top: 2px;
    }
    .actions-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-top: 16px;
    }
    .btn-action {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 11px 16px;
      border-radius: var(--radius-md);
      font-size: 0.875rem;
      font-weight: 600;
      text-decoration: none;
      transition: all 0.15s ease;
    }
    .btn-view {
      background: var(--text);
      color: #FFFFFF;
    }
    .btn-view:hover {
      background: #292524;
    }
    .btn-download {
      background: var(--surface);
      color: var(--text);
      border: 1px solid var(--border);
    }
    .btn-download:hover {
      background: var(--surface-subtle);
      border-color: #D6D3D1;
    }
    .spinner {
      width: 16px;
      height: 16px;
      border: 2px solid rgba(255, 255, 255, 0.3);
      border-top-color: #FFFFFF;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    footer {
      text-align: center;
      margin-top: 40px;
      font-size: 0.8rem;
      color: var(--text-light);
    }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <div class="brand">
        <span class="brand-dot"></span>
        SEO Intelligence & Audit
      </div>
      <h1>Automated Website Audit. Minimal & Fast.</h1>
      <p class="subtitle">Deep crawl for on-page SEO metrics, canonical consistency, broken links, robots.txt directives, and sitemaps.</p>
    </div>

    <div class="card">
      <form id="auditForm">
        <div class="form-group">
          <label for="url">
            Website URL
            <span class="label-hint">https://example.com</span>
          </label>
          <input type="url" id="url" name="url" required placeholder="https://example.com" autofocus />
        </div>

        <div class="grid-2">
          <div class="form-group">
            <label for="max_pages">
              Max Pages
              <span class="label-hint">Internal BFS</span>
            </label>
            <input type="number" id="max_pages" name="max_pages" value="30" min="1" max="100" />
          </div>
          <div class="form-group">
            <label for="max_external_links">
              Ext. Links Check
              <span class="label-hint">Deduplicated</span>
            </label>
            <input type="number" id="max_external_links" name="max_external_links" value="50" min="1" max="100" />
          </div>
        </div>

        <button type="submit" id="btnSubmit" class="btn-primary">
          <span id="btnIcon">⚡</span>
          <span id="btnText">Run SEO Audit</span>
        </button>
      </form>

      <div id="status"></div>
    </div>

    <footer>
      SEO Audit Toolkit · Powered by Python Async & FastAPI
    </footer>
  </div>

  <script>
    const form = document.getElementById("auditForm");
    const btn = document.getElementById("btnSubmit");
    const btnText = document.getElementById("btnText");
    const btnIcon = document.getElementById("btnIcon");
    const statusBox = document.getElementById("status");

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      btn.disabled = true;
      btnIcon.innerHTML = '<div class="spinner"></div>';
      btnText.innerText = "Analyzing website...";
      statusBox.style.display = "block";
      statusBox.innerHTML = `
        <div class="status-panel" style="text-align: center;">
          <div style="font-size: 0.9rem; font-weight: 600; color: var(--text);">Crawling in progress</div>
          <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 4px;">Analyzing HTML structure, status codes, and validating links...</div>
        </div>
      `;

      const payload = {
        url: document.getElementById("url").value,
        max_pages: parseInt(document.getElementById("max_pages").value, 10),
        max_external_links: parseInt(document.getElementById("max_external_links").value, 10)
      };

      try {
        const resp = await fetch("/api/audit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.detail || "Audit execution encountered an issue.");
        }

        const scoreColor = data.health_score >= 80 ? '#0F766E' : data.health_score >= 50 ? '#B45309' : '#B91C1C';

        statusBox.innerHTML = `
          <div class="status-panel">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div>
                <div style="font-size: 0.875rem; font-weight: 700; color: var(--text);">Audit Completed</div>
                <div style="font-size: 0.775rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace;">${data.target_url}</div>
              </div>
              <div style="font-size: 1.5rem; font-weight: 800; color: ${scoreColor};">
                ${data.health_score}<span style="font-size: 0.875rem; color: var(--text-light); font-weight: 500;">/100</span>
              </div>
            </div>

            <div class="metrics-row">
              <div class="metric-item">
                <div class="metric-value">${data.pages_crawled}</div>
                <div class="metric-label">Pages</div>
              </div>
              <div class="metric-item">
                <div class="metric-value" style="color: ${data.broken_links_count > 0 ? '#B91C1C' : 'var(--text)'};">
                  ${data.broken_links_count}
                </div>
                <div class="metric-label">Broken Links</div>
              </div>
              <div class="metric-item">
                <div class="metric-value">${data.duration_seconds}s</div>
                <div class="metric-label">Duration</div>
              </div>
            </div>

            <div class="actions-grid">
              <a href="/api/reports/${data.report_id}/html" target="_blank" class="btn-action btn-view">
                <span>View HTML Report</span>
                <span>↗</span>
              </a>
              <a href="/api/reports/${data.report_id}/csv" class="btn-action btn-download">
                <span>Export CSV</span>
                <span>↓</span>
              </a>
            </div>
          </div>
        `;
      } catch (err) {
        statusBox.innerHTML = `
          <div class="status-panel" style="border-color: #FECACA; background: #FEF2F2;">
            <div style="font-size: 0.875rem; font-weight: 700; color: #991B1B;">Audit Failed</div>
            <div style="font-size: 0.8rem; color: #B91C1C; margin-top: 4px;">${err.message}</div>
          </div>
        `;
      } finally {
        btn.disabled = false;
        btnIcon.innerText = "⚡";
        btnText.innerText = "Run SEO Audit";
      }
    });
  </script>
</body>
</html>
"""


@app.post("/api/audit")
async def run_audit(req: AuditRequest, request: Request):
    allow_private = os.getenv("ALLOW_PRIVATE_NETWORK", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    url_str = str(req.url)

    try:
        report = await crawl_site(
            start_url=url_str,
            max_pages=req.max_pages,
            max_external_links=req.max_external_links,
            allow_private_network=allow_private,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:
        raise HTTPException(
            status_code=500, detail=f"Audit execution error: {err.__class__.__name__}"
        ) from err

    # Store in memory cache
    REPORT_CACHE[report.report_id] = report
    if len(REPORT_CACHE) > MAX_CACHE_SIZE:
        REPORT_CACHE.popitem(last=False)

    return {
        "report_id": report.report_id,
        "target_url": report.target_url,
        "health_score": report.health_score,
        "pages_crawled": len(report.pages),
        "broken_links_count": len(report.broken_links),
        "duration_seconds": report.duration_seconds,
    }


@app.get("/api/reports/{report_id}")
async def get_report_json(report_id: str):
    if report_id not in REPORT_CACHE:
        raise HTTPException(status_code=404, detail="Report not found")
    report = REPORT_CACHE[report_id]
    return JSONResponse(content=asdict(report))


@app.get("/api/reports/{report_id}/csv")
async def get_report_csv(report_id: str):
    if report_id not in REPORT_CACHE:
        raise HTTPException(status_code=404, detail="Report not found")
    report = REPORT_CACHE[report_id]
    csv_data = generate_csv_report(report)
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="seo-audit-{report_id}.csv"'
        },
    )


@app.get("/api/reports/{report_id}/html", response_class=HTMLResponse)
async def get_report_html(report_id: str, download: int = Query(default=0)):
    if report_id not in REPORT_CACHE:
        raise HTTPException(status_code=404, detail="Report not found")
    report = REPORT_CACHE[report_id]
    html_data = generate_html_report(report)
    headers = {}
    if download:
        headers["Content-Disposition"] = (
            f'attachment; filename="seo-audit-{report_id}.html"'
        )
    return HTMLResponse(content=html_data, headers=headers)
