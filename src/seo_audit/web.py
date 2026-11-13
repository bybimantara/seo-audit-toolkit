"""FastAPI web application for SEO Audit Toolkit."""

from __future__ import annotations

import os
from collections import OrderedDict
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, HttpUrl

from seo_audit.crawler import crawl_site
from seo_audit.db import get_report, list_reports, save_report
from seo_audit.diff import compare_reports
from seo_audit.models import SiteAuditReport
from seo_audit.reporters import generate_csv_report, generate_html_report

app = FastAPI(title="SEO Audit Toolkit", version="0.1.0")

# In-memory LRU report cache (last 20 reports)
REPORT_CACHE: OrderedDict[str, SiteAuditReport] = OrderedDict()
MAX_CACHE_SIZE = 20


def _fetch_report(report_id: str) -> SiteAuditReport:
    """Fetch report from in-memory cache or fallback to SQLite DB."""
    if report_id in REPORT_CACHE:
        return REPORT_CACHE[report_id]
    report = get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    REPORT_CACHE[report_id] = report
    if len(REPORT_CACHE) > MAX_CACHE_SIZE:
        REPORT_CACHE.popitem(last=False)
    return report


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
      --ahrefs-blue-hover: #004BD6;
      --green: #10B981;
      --amber: #F59E0B;
      --red: #EF4444;

      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 14px;
      --radius-xl: 18px;
      --shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.04);
      --shadow-card: 0 4px 16px -2px rgba(15, 23, 42, 0.06), 0 2px 4px -1px rgba(15, 23, 42, 0.03);
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
    }

    /* Top Navigation Bar */
    .topbar {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      height: 60px;
      padding: 0 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .brand-logo {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 800;
      font-size: 1.05rem;
      letter-spacing: -0.02em;
      color: var(--text);
      text-decoration: none;
    }
    .brand-icon {
      width: 28px;
      height: 28px;
      background: var(--ahrefs-blue);
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      color: #FFFFFF;
      font-weight: 800;
      font-size: 0.9rem;
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
      transition: color 0.15s ease;
    }
    .topbar-nav a:hover, .topbar-nav a.active {
      color: var(--ahrefs-blue);
    }
    .topbar-badge {
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      color: var(--text-muted);
      font-size: 0.725rem;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 20px;
    }

    /* Main Container */
    .main-container {
      max-width: 1120px;
      margin: 0 auto;
      padding: 40px 24px 80px;
    }

    /* Hero & URL Input Bar */
    .hero-search {
      text-align: center;
      margin-bottom: 36px;
    }
    .hero-title {
      font-size: 2.25rem;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: var(--text);
      margin-bottom: 8px;
    }
    .hero-subtitle {
      font-size: 1rem;
      color: var(--text-muted);
      max-width: 600px;
      margin: 0 auto 28px;
    }

    .input-bar {
      display: flex;
      align-items: center;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-xl);
      padding: 6px 8px 6px 20px;
      box-shadow: var(--shadow-card);
      max-width: 820px;
      margin: 0 auto 20px;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .input-bar:focus-within {
      border-color: var(--ahrefs-blue);
      box-shadow: 0 0 0 3px rgba(0, 91, 255, 0.12), var(--shadow-card);
    }
    .input-bar input {
      flex: 1;
      border: none;
      background: transparent;
      font-size: 1rem;
      font-family: inherit;
      color: var(--text);
      outline: none;
    }
    .input-bar input::placeholder {
      color: var(--text-light);
    }

    .btn-audit {
      background: var(--semrush-orange);
      color: #FFFFFF;
      border: none;
      padding: 12px 28px;
      font-size: 0.95rem;
      font-weight: 700;
      font-family: inherit;
      border-radius: var(--radius-lg);
      cursor: pointer;
      transition: background 0.15s ease, transform 0.05s ease;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .btn-audit:hover {
      background: var(--semrush-orange-hover);
    }
    .btn-audit:active {
      transform: scale(0.99);
    }
    .btn-audit:disabled {
      opacity: 0.65;
      cursor: not-allowed;
    }

    /* Options Bar */
    .options-row {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 24px;
      font-size: 0.85rem;
      color: var(--text-muted);
      max-width: 820px;
      margin: 0 auto;
    }
    .option-item {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .option-item input[type="number"] {
      width: 60px;
      padding: 4px 8px;
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      background: var(--surface);
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      color: var(--text);
      outline: none;
    }
    .option-item input[type="number"]:focus {
      border-color: var(--ahrefs-blue);
    }

    /* Report Summary Banner (Semrush / Ahrefs Style) */
    .report-banner {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-xl);
      padding: 32px 36px;
      margin-top: 32px;
      display: grid;
      grid-template-columns: 1fr 240px;
      gap: 32px;
      align-items: center;
      box-shadow: var(--shadow-card);
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
      margin-bottom: 8px;
      word-break: break-all;
    }
    .report-subtitle-meta {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-bottom: 24px;
    }
    .pill-info {
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      padding: 2px 8px;
      border-radius: 4px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
    }

    .report-buttons {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }
    .btn-orange {
      background: var(--semrush-orange);
      color: #FFFFFF;
      padding: 10px 20px;
      font-size: 0.875rem;
      font-weight: 700;
      border-radius: var(--radius-md);
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: background 0.15s ease;
    }
    .btn-orange:hover {
      background: var(--semrush-orange-hover);
    }
    .btn-outline {
      background: var(--surface);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 10px 20px;
      font-size: 0.875rem;
      font-weight: 600;
      border-radius: var(--radius-md);
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: all 0.15s ease;
    }
    .btn-outline:hover {
      border-color: var(--text-muted);
      background: var(--surface-subtle);
    }

    /* Circular SVG Gauge */
    .gauge-wrapper {
      text-align: center;
    }
    .radial-gauge {
      width: 140px;
      height: 140px;
      margin: 0 auto;
      position: relative;
    }
    .radial-gauge svg {
      width: 100%;
      height: 100%;
      transform: rotate(-90deg);
    }
    .gauge-bg {
      fill: none;
      stroke: var(--surface-subtle);
      stroke-width: 12;
    }
    .gauge-fill {
      fill: none;
      stroke-width: 12;
      stroke-linecap: round;
      transition: stroke-dashoffset 0.8s ease;
    }
    .gauge-center-text {
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }
    .gauge-score {
      font-size: 2.2rem;
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

    /* History & Diff Panels */
    .history-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-xl);
      overflow: hidden;
      box-shadow: var(--shadow-sm);
    }
    .history-table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
    }
    .history-table th, .history-table td {
      padding: 12px 18px;
      border-bottom: 1px solid var(--border-subtle);
      vertical-align: middle;
    }
    .history-table th {
      background: var(--surface-subtle);
      font-size: 0.725rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
    }
    .history-table tr:hover td {
      background: #F8FAFC;
    }
    .history-table tr:last-child td {
      border-bottom: none;
    }
    .score-pill {
      display: inline-block;
      padding: 3px 8px;
      border-radius: 4px;
      font-weight: 700;
      font-size: 0.775rem;
      font-family: 'JetBrains Mono', monospace;
    }
    .action-btn {
      display: inline-flex;
      align-items: center;
      padding: 4px 9px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
      font-size: 0.75rem;
      font-weight: 600;
      text-decoration: none;
      transition: all 0.15s ease;
    }
    .action-btn:hover {
      border-color: var(--ahrefs-blue);
      color: var(--ahrefs-blue);
      background: #EFF6FF;
    }

    .diff-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-xl);
      padding: 28px 32px;
      box-shadow: var(--shadow-card);
      margin-bottom: 32px;
    }
    .diff-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border-subtle);
    }
    .diff-stat-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
      margin-bottom: 24px;
    }
    .diff-stat-box {
      background: var(--surface-subtle);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 16px 20px;
      text-align: center;
    }
    .diff-stat-title {
      font-size: 0.725rem;
      font-weight: 700;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: 6px;
    }
    .diff-stat-val {
      font-size: 1.7rem;
      font-weight: 800;
      letter-spacing: -0.02em;
    }
    .diff-issues-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      margin-top: 10px;
    }
    .diff-issue-row {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 0.85rem;
      padding: 8px 12px;
      border-radius: var(--radius-sm);
    }
    .diff-issue-regress {
      background: #FEF2F2;
      border: 1px solid #FECACA;
      color: #991B1B;
    }
    .diff-issue-resolved {
      background: #ECFDF5;
      border: 1px solid #A7F3D0;
      color: #065F46;
    }

    /* Loading Card */
    .loading-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-xl);
      padding: 48px;
      text-align: center;
      margin-top: 32px;
      box-shadow: var(--shadow-sm);
    }
    .pulse-spinner {
      width: 44px;
      height: 44px;
      border: 4px solid var(--surface-subtle);
      border-top-color: var(--semrush-orange);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin: 0 auto 16px;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    .mono { font-family: 'JetBrains Mono', monospace; }
    .font-xs { font-size: 0.775rem; }
    .font-sm { font-size: 0.875rem; }
    .text-muted { color: var(--text-muted); }
    .text-center { text-align: center; }
    .table-link { color: var(--text); text-decoration: none; font-weight: 600; }
    .table-link:hover { color: var(--ahrefs-blue); text-decoration: underline; }
    .table-responsive { overflow-x: auto; }

    /* Responsive */
    @media (max-width: 840px) {
      .report-banner {
        grid-template-columns: 1fr;
      }
      .metrics-grid-4, .diff-stat-grid {
        grid-template-columns: 1fr 1fr;
      }
    }
    @media (max-width: 520px) {
      .metrics-grid-4, .diff-stat-grid {
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
      <a href="#historySection">History</a>
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

    <!-- Diff Comparison Area (hidden by default) -->
    <div id="diffArea" style="margin-top: 32px; display: none;"></div>

    <!-- Recent Audit History Area -->
    <div id="historySection" style="margin-top: 48px;">
      <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 16px;">
        <div>
          <div class="section-title">Recent Audit History</div>
          <div class="section-desc">Stored in local SQLite database. Select any 2 audits to compare changes and detect regressions.</div>
        </div>
        <div id="compareActionBox" style="display: none; align-items: center; gap: 10px;">
          <span id="selectedCountText" style="font-size: 0.825rem; font-weight: 600; color: var(--text-muted);">2 selected</span>
          <button id="btnCompare" class="btn-orange" style="padding: 7px 16px; font-size: 0.825rem; border-radius: var(--radius-sm); border: none; cursor: pointer;">
            Compare Selected
          </button>
        </div>
      </div>
      <div id="historyTableContainer" class="history-card">
        <div style="padding: 32px; text-align: center; color: var(--text-muted); font-size: 0.875rem;">Loading audit history...</div>
      </div>
    </div>
  </main>

  <script>
    const form = document.getElementById("auditForm");
    const btn = document.getElementById("btnSubmit");
    const btnText = document.getElementById("btnText");
    const statusArea = document.getElementById("statusArea");
    const diffArea = document.getElementById("diffArea");
    let selectedAudits = [];

    // History and Selection Logic
    async function loadHistory() {
      const container = document.getElementById("historyTableContainer");
      try {
        const res = await fetch("/api/history?limit=15");
        const data = await res.json();
        const reports = data.reports || [];
        if (reports.length === 0) {
          container.innerHTML = `<div style="padding: 36px; text-align: center; color: var(--text-muted); font-size: 0.875rem;">No previous audits recorded yet. Run an audit above to start tracking history.</div>`;
          return;
        }

        let rows = reports.map(r => {
          const score = r.health_score;
          const scoreColor = score >= 80 ? '#10B981' : score >= 50 ? '#F59E0B' : '#EF4444';
          const bgPill = score >= 80 ? '#ECFDF5' : score >= 50 ? '#FFFBEB' : '#FEF2F2';
          const borderPill = score >= 80 ? '#A7F3D0' : score >= 50 ? '#FDE68A' : '#FECACA';
          const dateStr = new Date(r.audited_at).toLocaleString();
          const isChecked = selectedAudits.includes(r.report_id) ? 'checked' : '';

          return `
            <tr>
              <td style="width: 36px; text-align: center;">
                <input type="checkbox" class="audit-select-cb" data-id="${r.report_id}" ${isChecked} onchange="toggleSelectAudit('${r.report_id}')" />
              </td>
              <td class="mono font-xs cell-url">
                <a href="${r.target_url}" target="_blank" class="table-link">${r.target_url}</a>
              </td>
              <td class="font-xs text-muted mono">${dateStr}</td>
              <td class="text-center font-sm font-semibold">${r.pages_count}</td>
              <td class="text-center font-sm" style="color: ${r.broken_count > 0 ? '#EF4444' : '#10B981'}; font-weight: 600;">${r.broken_count}</td>
              <td class="text-center">
                <span class="score-pill" style="color: ${scoreColor}; background: ${bgPill}; border: 1px solid ${borderPill};">${score}/100</span>
              </td>
              <td style="text-align: right;">
                <div style="display: flex; gap: 8px; justify-content: flex-end;">
                  <a href="/api/reports/${r.report_id}/html" target="_blank" class="action-btn">HTML ↗</a>
                  <a href="/api/reports/${r.report_id}/csv" class="action-btn">CSV ↓</a>
                </div>
              </td>
            </tr>
          `;
        }).join("");

        container.innerHTML = `
          <div class="table-responsive">
            <table class="history-table">
              <thead>
                <tr>
                  <th style="width: 36px; text-align: center;">Compare</th>
                  <th>Target URL</th>
                  <th>Date Audited</th>
                  <th class="text-center">Pages</th>
                  <th class="text-center">Broken</th>
                  <th class="text-center">Score</th>
                  <th style="text-align: right;">Reports</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        `;
      } catch (err) {
        container.innerHTML = `<div style="padding: 24px; color: #991B1B;">Failed to load history: ${err.message}</div>`;
      }
    }

    window.toggleSelectAudit = function(id) {
      const idx = selectedAudits.indexOf(id);
      if (idx > -1) {
        selectedAudits.splice(idx, 1);
      } else {
        if (selectedAudits.length >= 2) {
          const oldest = selectedAudits.shift();
          const oldCb = document.querySelector(`.audit-select-cb[data-id="${oldest}"]`);
          if (oldCb) oldCb.checked = false;
        }
        selectedAudits.push(id);
      }
      const box = document.getElementById("compareActionBox");
      if (selectedAudits.length === 2) {
        box.style.display = "flex";
      } else {
        box.style.display = "none";
      }
    };

    document.getElementById("btnCompare").addEventListener("click", async () => {
      if (selectedAudits.length !== 2) return;
      const [id1, id2] = selectedAudits;
      diffArea.style.display = "block";
      diffArea.innerHTML = `
        <div class="loading-card">
          <div class="pulse-spinner"></div>
          <div style="font-weight: 700;">Comparing Audits...</div>
        </div>
      `;

      try {
        const res = await fetch(`/api/reports/${id1}/diff/${id2}`);
        if (!res.ok) throw new Error("Failed to compute diff");
        const diff = await res.json();

        const deltaColor = diff.score_delta > 0 ? '#10B981' : diff.score_delta < 0 ? '#EF4444' : 'var(--text)';
        const deltaPrefix = diff.score_delta > 0 ? '+' : '';
        const deltaLabel = diff.score_delta > 0 ? 'Improvement' : diff.score_delta < 0 ? 'Regression' : 'No Change';

        let newIssuesHtml = diff.new_issues.length === 0
          ? '<div style="font-size: 0.85rem; color: #10B981; font-weight: 500;">✓ No new issues introduced.</div>'
          : diff.new_issues.map(i => `<div class="diff-issue-row diff-issue-regress"><span>⚠</span><span><strong>${i.url}</strong>: ${i.issue}</span></div>`).join("");

        let resolvedIssuesHtml = diff.resolved_issues.length === 0
          ? '<div style="font-size: 0.85rem; color: var(--text-muted);">No previously flagged issues resolved.</div>'
          : diff.resolved_issues.map(i => `<div class="diff-issue-row diff-issue-resolved"><span>✓</span><span><strong>${i.url}</strong>: ${i.issue}</span></div>`).join("");

        diffArea.innerHTML = `
          <div class="diff-card">
            <div class="diff-header">
              <div>
                <div style="font-size: 0.725rem; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ahrefs-blue); margin-bottom: 4px;">AUDIT COMPARISON (DIFF)</div>
                <div style="font-size: 1.25rem; font-weight: 800; color: var(--text);">${diff.target_url}</div>
                <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 4px;">
                  Comparing report <span class="mono">${diff.old_report_id}</span> (${diff.old_score}/100) with <span class="mono">${diff.new_report_id}</span> (${diff.new_score}/100)
                </div>
              </div>
              <button onclick="document.getElementById('diffArea').style.display='none'" class="btn-outline" style="padding: 6px 14px; font-size: 0.8rem;">Close</button>
            </div>

            <div class="diff-stat-grid">
              <div class="diff-stat-box">
                <div class="diff-stat-title">Health Score Delta</div>
                <div class="diff-stat-val" style="color: ${deltaColor};">${deltaPrefix}${diff.score_delta}</div>
                <div style="font-size: 0.775rem; color: var(--text-muted); font-weight: 600; margin-top: 4px;">${deltaLabel}</div>
              </div>
              <div class="diff-stat-box">
                <div class="diff-stat-title">Crawled Pages Delta</div>
                <div class="diff-stat-val">${diff.pages_delta >= 0 ? '+' : ''}${diff.pages_delta}</div>
                <div style="font-size: 0.775rem; color: var(--text-muted); margin-top: 4px;">${diff.pages_count_old} → ${diff.pages_count_new} pages</div>
              </div>
              <div class="diff-stat-box">
                <div class="diff-stat-title">Broken Links Delta</div>
                <div class="diff-stat-val" style="color: ${diff.broken_delta > 0 ? '#EF4444' : diff.broken_delta < 0 ? '#10B981' : 'var(--text)'};">
                  ${diff.broken_delta >= 0 ? '+' : ''}${diff.broken_delta}
                </div>
                <div style="font-size: 0.775rem; color: var(--text-muted); margin-top: 4px;">${diff.broken_count_old} → ${diff.broken_count_new} broken</div>
              </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px;">
              <div>
                <div style="font-size: 0.875rem; font-weight: 700; margin-bottom: 8px; color: #991B1B;">New Regressions Detected (${diff.new_issues.length})</div>
                <div class="diff-issues-list">${newIssuesHtml}</div>
              </div>
              <div>
                <div style="font-size: 0.875rem; font-weight: 700; margin-bottom: 8px; color: #065F46;">Resolved Issues (${diff.resolved_issues.length})</div>
                <div class="diff-issues-list">${resolvedIssuesHtml}</div>
              </div>
            </div>
          </div>
        `;
        diffArea.scrollIntoView({ behavior: 'smooth' });
      } catch (err) {
        diffArea.innerHTML = `<div class="loading-card" style="border-color: #FECACA; background: #FEF2F2; color: #991B1B;">${err.message}</div>`;
      }
    });

    // Run audit handler
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

        // Refresh recent history
        loadHistory();
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

    // Initial history fetch
    document.addEventListener("DOMContentLoaded", loadHistory);
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

    # Persist in local SQLite database
    save_report(report)

    return {
        "report_id": report.report_id,
        "target_url": report.target_url,
        "health_score": report.health_score,
        "pages_crawled": len(report.pages),
        "broken_links_count": len(report.broken_links),
        "duration_seconds": report.duration_seconds,
        "llms_txt_found": report.site_meta.llms_txt_found,
    }


@app.get("/api/history")
async def get_history(
    limit: int = Query(default=20, le=100), domain: str | None = None
):
    """List recent audit runs from local SQLite database."""
    return {"reports": list_reports(limit=limit, domain=domain)}


@app.get("/api/reports/{id_old}/diff/{id_new}")
async def get_diff(id_old: str, id_new: str):
    """Compare two audit reports and return regression/improvement delta."""
    report_old = _fetch_report(id_old)
    report_new = _fetch_report(id_new)
    diff = compare_reports(report_old, report_new)
    return JSONResponse(content=diff.to_dict())


@app.get("/api/reports/{report_id}")
async def get_report_json(report_id: str):
    report = _fetch_report(report_id)
    return JSONResponse(content=asdict(report))


@app.get("/api/reports/{report_id}/csv")
async def get_report_csv(report_id: str):
    report = _fetch_report(report_id)
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
    report = _fetch_report(report_id)
    html_data = generate_html_report(report)
    headers = {}
    if download:
        headers["Content-Disposition"] = (
            f'attachment; filename="seo-audit-{report_id}.html"'
        )
    return HTMLResponse(content=html_data, headers=headers)
