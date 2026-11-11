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
  <title>SEO Audit Toolkit — Professional SEO Intelligence Platform</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #F8FAFC;
      --surface: #FFFFFF;
      --surface-subtle: #F1F5F9;
      --border: #E2E8F0;
      --border-subtle: #EDF2F7;
      --border-focus: #005BFF;
      --text: #0F172A;
      --text-muted: #64748B;
      --text-light: #94A3B8;
      
      /* Semrush & Ahrefs vibrant light palette */
      --semrush-orange: #FF642D;
      --semrush-orange-hover: #E8521F;
      --ahrefs-blue: #005BFF;
      --ahrefs-blue-hover: #004ED9;
      --green: #10B981;
      --green-bg: #ECFDF5;
      --green-border: #A7F3D0;
      --amber: #F59E0B;
      --amber-bg: #FFFBEB;
      --red: #EF4444;
      --red-bg: #FEF2F2;

      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 14px;
      --radius-xl: 18px;
      --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.04);
      --shadow-card: 0 2px 8px -2px rgba(15, 23, 42, 0.05), 0 1px 3px rgba(15, 23, 42, 0.03);
      --shadow-float: 0 12px 32px -8px rgba(15, 23, 42, 0.08), 0 4px 12px -2px rgba(15, 23, 42, 0.04);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
    }

    /* Top Navigation bar in Semrush/Ahrefs style */
    .topbar {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      height: 64px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 32px;
      position: sticky;
      top: 0;
      z-index: 50;
    }
    .brand-logo {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 800;
      font-size: 1.15rem;
      letter-spacing: -0.02em;
      color: var(--text);
      text-decoration: none;
    }
    .brand-icon {
      width: 28px;
      height: 28px;
      background: linear-gradient(135deg, var(--semrush-orange), #FF8E3C);
      border-radius: 7px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-size: 0.85rem;
      font-weight: 800;
      box-shadow: 0 2px 6px rgba(255, 100, 45, 0.35);
    }
    .topbar-nav {
      display: flex;
      align-items: center;
      gap: 20px;
      font-size: 0.875rem;
      font-weight: 600;
    }
    .topbar-nav a {
      color: var(--text-muted);
      text-decoration: none;
      transition: color 0.15s;
    }
    .topbar-nav a:hover, .topbar-nav a.active {
      color: var(--ahrefs-blue);
    }
    .topbar-badge {
      background: #EFF6FF;
      color: var(--ahrefs-blue);
      border: 1px solid #BFDBFE;
      padding: 3px 10px;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 700;
    }

    .main-container {
      max-width: 1140px;
      margin: 0 auto;
      padding: 40px 24px 80px;
    }

    /* Hero Search Bar like Ahrefs / Semrush */
    .hero-search {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-xl);
      padding: 32px 36px;
      box-shadow: var(--shadow-card);
      margin-bottom: 32px;
      position: relative;
    }
    .hero-title {
      font-size: 1.5rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: var(--text);
      margin-bottom: 6px;
    }
    .hero-subtitle {
      font-size: 0.95rem;
      color: var(--text-muted);
      margin-bottom: 24px;
    }
    
    .input-bar {
      display: flex;
      background: var(--surface);
      border: 2px solid var(--border);
      border-radius: var(--radius-md);
      overflow: hidden;
      transition: border-color 0.15s, box-shadow 0.15s;
    }
    .input-bar:focus-within {
      border-color: var(--ahrefs-blue);
      box-shadow: 0 0 0 3px rgba(0, 91, 255, 0.12);
    }
    .input-bar input[type="url"] {
      flex: 1;
      border: none;
      padding: 14px 20px;
      font-size: 1rem;
      font-family: 'JetBrains Mono', monospace;
      color: var(--text);
      outline: none;
      background: transparent;
    }
    .btn-audit {
      background: var(--semrush-orange);
      color: white;
      border: none;
      padding: 0 28px;
      font-size: 0.95rem;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: background 0.15s, transform 0.05s;
      white-space: nowrap;
    }
    .btn-audit:hover {
      background: var(--semrush-orange-hover);
    }
    .btn-audit:disabled {
      background: var(--text-light);
      cursor: not-allowed;
    }

    .options-row {
      display: flex;
      align-items: center;
      gap: 24px;
      margin-top: 18px;
      padding-top: 16px;
      border-top: 1px solid var(--border-subtle);
      font-size: 0.85rem;
      color: var(--text-muted);
    }
    .option-item {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .option-item input[type="number"] {
      width: 68px;
      padding: 5px 8px;
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      font-weight: 600;
      font-size: 0.85rem;
      outline: none;
    }

    /* Live Loading state */
    #statusArea {
      margin-top: 24px;
      display: none;
    }
    .loading-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 40px;
      text-align: center;
      box-shadow: var(--shadow-card);
    }
    .pulse-spinner {
      width: 44px;
      height: 44px;
      margin: 0 auto 16px;
      border: 3px solid rgba(0, 91, 255, 0.15);
      border-top-color: var(--ahrefs-blue);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Report Banner Card like the uploaded reference */
    .report-banner {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-xl);
      padding: 32px;
      box-shadow: var(--shadow-float);
      margin-bottom: 28px;
      display: grid;
      grid-template-columns: 1fr 240px;
      gap: 32px;
      align-items: center;
    }
    .report-meta-tag {
      font-size: 0.725rem;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--ahrefs-blue);
      margin-bottom: 6px;
    }
    .report-domain {
      font-size: 1.85rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: var(--text);
      word-break: break-all;
      margin-bottom: 10px;
    }
    .report-subtitle-meta {
      font-size: 0.875rem;
      color: var(--text-muted);
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
      margin-bottom: 20px;
    }
    .pill-info {
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      padding: 2px 10px;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
    }
    
    .report-buttons {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }
    .btn-orange {
      background: var(--semrush-orange);
      color: white;
      border: none;
      padding: 10px 18px;
      border-radius: var(--radius-md);
      font-size: 0.875rem;
      font-weight: 700;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: background 0.15s;
    }
    .btn-orange:hover {
      background: var(--semrush-orange-hover);
    }
    .btn-outline {
      background: var(--surface);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 10px 18px;
      border-radius: var(--radius-md);
      font-size: 0.875rem;
      font-weight: 600;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: background 0.15s;
    }
    .btn-outline:hover {
      background: var(--surface-subtle);
      border-color: #CBD5E1;
    }

    /* Radial Score Gauge like in the image */
    .gauge-wrapper {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
    }
    .radial-gauge {
      width: 140px;
      height: 140px;
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .radial-gauge svg {
      transform: rotate(-90deg);
      width: 100%;
      height: 100%;
    }
    .gauge-bg {
      fill: none;
      stroke: #E2E8F0;
      stroke-width: 10;
    }
    .gauge-fill {
      fill: none;
      stroke-width: 10;
      stroke-linecap: round;
      transition: stroke-dashoffset 0.8s ease;
    }
    .gauge-center-text {
      position: absolute;
      text-align: center;
    }
    .gauge-score {
      font-size: 2.25rem;
      font-weight: 800;
      letter-spacing: -0.04em;
      line-height: 1;
    }
    .gauge-label {
      font-size: 0.725rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-top: 4px;
      color: var(--text-muted);
    }

    /* Sub Tabs & Metrics Grid from reference */
    .section-title {
      font-size: 1.15rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 4px;
      color: var(--text);
    }
    .section-desc {
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-bottom: 16px;
    }

    .metrics-grid-4 {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 28px;
    }
    .metric-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 22px;
      box-shadow: var(--shadow-sm);
    }
    .metric-card .card-title {
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-muted);
      margin-bottom: 6px;
    }
    .metric-card .card-number {
      font-size: 1.85rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: var(--text);
      line-height: 1;
    }
    .metric-card .card-footer {
      font-size: 0.775rem;
      font-weight: 500;
      margin-top: 8px;
    }

    /* Responsive */
    @media (max-width: 840px) {
      .report-banner {
        grid-template-columns: 1fr;
      }
      .metrics-grid-4 {
        grid-template-columns: 1fr 1fr;
      }
    }
    @media (max-width: 520px) {
      .metrics-grid-4 {
        grid-template-columns: 1fr;
      }
      .input-bar {
        flex-direction: column;
      }
      .btn-audit {
        padding: 14px;
        justify-content: center;
      }
    }
  </style>
</head>
<body>

  <!-- Top Navigation Bar -->
  <header class="topbar">
    <a href="/" class="brand-logo">
      <div class="brand-icon">S</div>
      <span>SEO Audit Toolkit</span>
    </a>
    <nav class="topbar-nav">
      <a href="/" class="active">Site Audit</a>
      <a href="#overview">Overview</a>
      <span class="topbar-badge">v0.1.0 Ready</span>
    </nav>
  </header>

  <main class="main-container">
    <!-- Hero Search Bar (Ahrefs / Semrush style) -->
    <div class="hero-search">
      <h1 class="hero-title">Site Audit & Health Inspector</h1>
      <p class="hero-subtitle">Comprehensive on-page, canonical, broken link, and sitemap crawling for high-impact technical SEO.</p>
      
      <form id="auditForm">
        <div class="input-bar">
          <input type="url" id="url" name="url" required placeholder="https://example.com" autofocus />
          <button type="submit" id="btnSubmit" class="btn-audit">
            <span id="btnText">Start Audit</span>
          </button>
        </div>

        <div class="options-row">
          <div class="option-item">
            <label for="max_pages"><strong>Crawl Depth:</strong></label>
            <input type="number" id="max_pages" name="max_pages" value="30" min="1" max="100" />
            <span>internal pages</span>
          </div>
          <div class="option-item">
            <label for="max_external_links"><strong>External Links:</strong></label>
            <input type="number" id="max_external_links" name="max_external_links" value="50" min="1" max="100" />
            <span>unique check limit</span>
          </div>
          <div style="margin-left: auto; color: var(--text-light); font-size: 0.8rem;">
            Instant report · No account required
          </div>
        </div>
      </form>
    </div>

    <!-- Live Status / Result Area -->
    <div id="statusArea"></div>
  </main>

  <script>
    const form = document.getElementById("auditForm");
    const btn = document.getElementById("btnSubmit");
    const btnText = document.getElementById("btnText");
    const statusArea = document.getElementById("statusArea");

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      btn.disabled = true;
      btnText.innerText = "Crawling Website...";
      statusArea.style.display = "block";

      statusArea.innerHTML = `
        <div class="loading-card">
          <div class="pulse-spinner"></div>
          <div style="font-size: 1.15rem; font-weight: 700; color: var(--text);">Analyzing Website Structure</div>
          <div style="font-size: 0.9rem; color: var(--text-muted); margin-top: 6px;">
            Crawling pages, verifying status codes, checking meta tags, and testing internal/external broken links...
          </div>
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
          throw new Error(data.detail || "Failed to execute audit.");
        }

        const score = data.health_score;
        const strokeColor = score >= 80 ? '#10B981' : score >= 50 ? '#F59E0B' : '#EF4444';
        const ratingText = score >= 80 ? 'Excellent' : score >= 50 ? 'Needs Attention' : 'Critical Issues';
        
        // Circumference for r=58 is 2 * PI * 58 ~= 364.42
        const circumference = 364.42;
        const dashOffset = circumference - (score / 100) * circumference;

        statusArea.innerHTML = `
          <!-- Report Header Banner matching reference -->
          <div class="report-banner">
            <div>
              <div class="report-meta-tag">SEO AUDIT REPORT</div>
              <div class="report-domain">${data.target_url}</div>
              <div class="report-subtitle-meta">
                <span><strong>${data.pages_crawled}</strong> pages crawled</span>
                <span>•</span>
                <span>Duration: <strong>${data.duration_seconds}s</strong></span>
                <span class="pill-info">Full Site BFS</span>
              </div>
              <div class="report-buttons">
                <a href="/api/reports/${data.report_id}/html" target="_blank" class="btn-orange">
                  <span>View Detailed HTML Report</span>
                  <span>↗</span>
                </a>
                <a href="/api/reports/${data.report_id}/csv" class="btn-outline">
                  <span>Download CSV Data</span>
                  <span>↓</span>
                </a>
              </div>
            </div>

            <!-- Radial Gauge -->
            <div class="gauge-wrapper">
              <div class="radial-gauge">
                <svg viewBox="0 0 140 140">
                  <circle class="gauge-bg" cx="70" cy="70" r="58" />
                  <circle class="gauge-fill" cx="70" cy="70" r="58"
                          stroke="${strokeColor}"
                          stroke-dasharray="${circumference}"
                          stroke-dashoffset="${dashOffset}" />
                </svg>
                <div class="gauge-center-text">
                  <div class="gauge-score" style="color: ${strokeColor};">${score}</div>
                  <div class="gauge-label">${ratingText}</div>
                </div>
              </div>
              <div style="font-size: 0.775rem; color: var(--text-muted); margin-top: 8px;">
                Overall SEO Health Score
              </div>
            </div>
          </div>

          <!-- Key Metrics Grid -->
          <div style="margin-top: 32px;">
            <div class="section-title">Key Audit Metrics</div>
            <div class="section-desc">Page-level signals, broken links, status codes, and crawl metadata</div>

            <div class="metrics-grid-4">
              <div class="metric-card">
                <div class="card-title">Pages Audited</div>
                <div class="card-number">${data.pages_crawled}</div>
                <div class="card-footer" style="color: var(--ahrefs-blue);">100% crawl verified</div>
              </div>
              <div class="metric-card">
                <div class="card-title">Broken Links (404)</div>
                <div class="card-number" style="color: ${data.broken_links_count > 0 ? '#EF4444' : '#10B981'};">
                  ${data.broken_links_count}
                </div>
                <div class="card-footer" style="color: ${data.broken_links_count > 0 ? '#EF4444' : '#10B981'};">
                  ${data.broken_links_count === 0 ? '✓ No dead URLs' : 'Requires fixing'}
                </div>
              </div>
              <div class="metric-card">
                <div class="card-title">Execution Speed</div>
                <div class="card-number">${data.duration_seconds}s</div>
                <div class="card-footer" style="color: var(--text-muted);">Async concurrency</div>
              </div>
              <div class="metric-card">
                <div class="card-title">Export Status</div>
                <div class="card-number" style="font-size: 1.3rem; color: #10B981;">Ready</div>
                <div class="card-footer" style="color: var(--text-muted);">HTML & CSV generated</div>
              </div>
            </div>
          </div>
        `;
      } catch (err) {
        statusArea.innerHTML = `
          <div class="loading-card" style="border-color: #FECACA; background: #FEF2F2;">
            <div style="font-size: 1.1rem; font-weight: 700; color: #991B1B;">Audit Execution Failed</div>
            <div style="font-size: 0.875rem; color: #B91C1C; margin-top: 6px;">${err.message}</div>
          </div>
        `;
      } finally {
        btn.disabled = false;
        btnText.innerText = "Start Audit";
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
        "llms_txt_found": report.site_meta.llms_txt_found,
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
