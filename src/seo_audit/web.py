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
  <title>SEO Audit Toolkit - Automated Website Audit</title>
  <style>
    :root {
      --bg: #F8FAFC;
      --surface: #FFFFFF;
      --text: #0F172A;
      --muted: #64748B;
      --border: #E2E8F0;
      --primary: #0F766E;
      --primary-hover: #115E59;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 32px 16px;
    }
    .wrapper { max-width: 800px; margin: 0 auto; }
    .header { text-align: center; margin-bottom: 32px; }
    h1 { font-size: 2rem; font-weight: 800; color: #0F172A; margin-bottom: 8px; }
    p.subtitle { color: var(--muted); font-size: 1rem; }
    .box {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 32px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .form-group { margin-bottom: 20px; }
    label { display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 6px; }
    input[type="url"], input[type="number"] {
      width: 100%;
      padding: 10px 14px;
      border: 1px solid var(--border);
      border-radius: 8px;
      font-size: 1rem;
      font-family: inherit;
    }
    input:focus { outline: 2px solid var(--primary); border-color: var(--primary); }
    .row { display: flex; gap: 16px; }
    .col { flex: 1; }
    button {
      width: 100%;
      padding: 12px;
      background: var(--primary);
      color: white;
      border: none;
      border-radius: 8px;
      font-size: 1rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s ease;
    }
    button:hover { background: var(--primary-hover); }
    button:disabled { background: var(--muted); cursor: not-allowed; }
    #status { margin-top: 24px; display: none; }
    .alert { padding: 16px; border-radius: 8px; font-size: 0.9rem; }
    .alert-info { background: #E0F2FE; color: #0369A1; }
    .alert-error { background: #FEE2E2; color: #B91C1C; }
    .actions { display: flex; gap: 12px; margin-top: 16px; }
    .btn-secondary {
      flex: 1;
      text-align: center;
      padding: 10px;
      background: #F1F5F9;
      color: var(--text);
      text-decoration: none;
      border-radius: 8px;
      font-weight: 600;
      font-size: 0.9rem;
      border: 1px solid var(--border);
    }
    .btn-secondary:hover { background: #E2E8F0; }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>🔍 SEO Audit Toolkit</h1>
      <p class="subtitle">Automated crawler checking titles, meta descriptions, H1/H2, canonicals, broken links (404), robots.txt & sitemap.xml.</p>
    </div>

    <div class="box">
      <form id="auditForm">
        <div class="form-group">
          <label for="url">Target Website URL</label>
          <input type="url" id="url" name="url" required placeholder="https://example.com" />
        </div>
        <div class="row">
          <div class="form-group col">
            <label for="max_pages">Max Pages to Crawl</label>
            <input type="number" id="max_pages" name="max_pages" value="30" min="1" max="100" />
          </div>
          <div class="form-group col">
            <label for="max_external_links">Max External Links to Check</label>
            <input type="number" id="max_external_links" name="max_external_links" value="50" min="1" max="100" />
          </div>
        </div>
        <button type="submit" id="btnSubmit">Start SEO Audit</button>
      </form>

      <div id="status"></div>
    </div>
  </div>

  <script>
    const form = document.getElementById("auditForm");
    const btn = document.getElementById("btnSubmit");
    const statusBox = document.getElementById("status");

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      btn.disabled = true;
      btn.innerText = "Auditing website (this may take a few seconds)...";
      statusBox.style.display = "block";
      statusBox.innerHTML = '<div class="alert alert-info">Crawling pages, checking meta tags and verifying broken links...</div>';

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
          throw new Error(data.detail || "Audit failed to run.");
        }

        statusBox.innerHTML = `
          <div class="alert alert-info" style="background:#DCFCE7; color:#15803D;">
            <strong>Audit Complete!</strong> Health Score: <strong>${data.health_score}/100</strong> | Pages Crawled: <strong>${data.pages_crawled}</strong> | Broken Links: <strong>${data.broken_links_count}</strong>
          </div>
          <div class="actions">
            <a href="/api/reports/${data.report_id}/html" target="_blank" class="btn-secondary">View HTML Report</a>
            <a href="/api/reports/${data.report_id}/csv" class="btn-secondary">Download CSV</a>
          </div>
        `;
      } catch (err) {
        statusBox.innerHTML = `<div class="alert alert-error"><strong>Error:</strong> ${err.message}</div>`;
      } finally {
        btn.disabled = false;
        btn.innerText = "Start SEO Audit";
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
