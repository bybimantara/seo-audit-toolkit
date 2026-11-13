"""Unit and integration tests for FastAPI Web App and CLI."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from seo_audit.cli import main
from seo_audit.db import save_report
from seo_audit.models import PageAudit, SiteAuditReport
from seo_audit.web import REPORT_CACHE, app

client = TestClient(app)


def test_web_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_web_index_page():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SEO Audit Toolkit" in resp.text
    assert '<form id="auditForm">' in resp.text
    assert "Recent Audit History" in resp.text


def test_web_api_audit_and_downloads():
    # Mock crawler to return an instant report
    mock_report = SiteAuditReport(
        target_url="https://mocktest.com",
        health_score=92,
        pages=[
            PageAudit(
                url="https://mocktest.com",
                status_code=200,
                response_time_ms=50.0,
                title="Mock Test Website Home",
                title_length=22,
                meta_description="A good test description for mock testing",
                description_length=38,
                canonical_url="https://mocktest.com",
                h1_list=["Mock Title"],
            )
        ],
    )

    with patch("seo_audit.web.crawl_site", return_value=mock_report):
        post_resp = client.post(
            "/api/audit",
            json={
                "url": "https://mocktest.com",
                "max_pages": 5,
                "max_external_links": 5,
            },
        )
        assert post_resp.status_code == 200
        data = post_resp.json()
        assert data["health_score"] == 92
        report_id = data["report_id"]

        # Test JSON report endpoint
        json_resp = client.get(f"/api/reports/{report_id}")
        assert json_resp.status_code == 200
        assert json_resp.json()["target_url"] == "https://mocktest.com"

        # Test CSV download endpoint
        csv_resp = client.get(f"/api/reports/{report_id}/csv")
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers["content-type"]
        assert "https://mocktest.com,200" in csv_resp.text

        # Test HTML report endpoint
        html_resp = client.get(f"/api/reports/{report_id}/html")
        assert html_resp.status_code == 200
        assert "https://mocktest.com" in html_resp.text


def test_web_history_and_diff_endpoints(tmp_path, monkeypatch):
    test_db = tmp_path / "web_test.db"
    monkeypatch.setenv("SEO_AUDIT_DB_PATH", str(test_db))

    r1 = SiteAuditReport(
        report_id="rep-old",
        target_url="https://history-diff.com",
        health_score=70,
        pages=[
            PageAudit(
                url="https://history-diff.com/",
                status_code=200,
                issues=["Missing meta description"],
            )
        ],
    )
    r2 = SiteAuditReport(
        report_id="rep-new",
        target_url="https://history-diff.com",
        health_score=88,
        pages=[
            PageAudit(
                url="https://history-diff.com/",
                status_code=200,
                issues=["Multiple H1 tags (2)"],
            )
        ],
    )

    save_report(r1)
    save_report(r2)

    # 1. Test /api/history
    hist_resp = client.get("/api/history")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert "reports" in hist_data
    report_ids = [r["report_id"] for r in hist_data["reports"]]
    assert "rep-old" in report_ids
    assert "rep-new" in report_ids

    # 2. Test /api/reports/{id_old}/diff/{id_new}
    diff_resp = client.get("/api/reports/rep-old/diff/rep-new")
    assert diff_resp.status_code == 200
    diff_data = diff_resp.json()
    assert diff_data["score_delta"] == 18
    assert len(diff_data["resolved_issues"]) == 1
    assert diff_data["resolved_issues"][0]["issue"] == "Missing meta description"
    assert len(diff_data["new_issues"]) == 1
    assert diff_data["new_issues"][0]["issue"] == "Multiple H1 tags (2)"

    # 3. Test DB fallback when cache is cleared
    REPORT_CACHE.clear()
    html_fallback = client.get("/api/reports/rep-old/html")
    assert html_fallback.status_code == 200
    assert "https://history-diff.com" in html_fallback.text


def test_cli_help():
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_cli_no_args():
    code = main([])
    assert code == 2


def test_cli_audit_execution(tmp_path, monkeypatch):
    test_db = tmp_path / "cli_test.db"
    monkeypatch.setenv("SEO_AUDIT_DB_PATH", str(test_db))

    csv_file = tmp_path / "test_report.csv"
    html_file = tmp_path / "test_report.html"

    mock_report = SiteAuditReport(
        report_id="cli-101",
        target_url="https://clitest.com",
        health_score=80,
        pages=[
            PageAudit(
                url="https://clitest.com",
                status_code=200,
                response_time_ms=75.0,
                title="CLI Test Page",
                title_length=13,
                canonical_url="https://clitest.com",
                h1_list=["CLI Title"],
            )
        ],
    )

    with patch("seo_audit.cli.crawl_site", return_value=mock_report):
        code = main([
            "https://clitest.com",
            "--max-pages",
            "5",
            "--csv",
            str(csv_file),
            "--html",
            str(html_file),
        ])
        assert code == 0
        assert csv_file.exists()
        assert html_file.exists()
        assert "https://clitest.com,200" in csv_file.read_text(encoding="utf-8")
        assert "SEO Audit Report" in html_file.read_text(encoding="utf-8")

        # Test CLI history command
        code_hist = main(["history"])
        assert code_hist == 0


def test_cli_compare(tmp_path, monkeypatch, capsys):
    test_db = tmp_path / "cli_compare.db"
    monkeypatch.setenv("SEO_AUDIT_DB_PATH", str(test_db))

    r1 = SiteAuditReport(
        report_id="comp-1",
        target_url="https://compare.com",
        health_score=60,
        pages=[
            PageAudit(url="https://compare.com/", issues=["Missing canonical"])
        ],
    )
    r2 = SiteAuditReport(
        report_id="comp-2",
        target_url="https://compare.com",
        health_score=75,
        pages=[PageAudit(url="https://compare.com/", issues=[])],
    )
    save_report(r1)
    save_report(r2)

    # Human-readable comparison output
    code = main(["compare", "comp-1", "comp-2"])
    assert code == 0
    captured = capsys.readouterr()
    assert "SEO AUDIT COMPARISON (DIFF)" in captured.out
    assert "Health Score Delta: +15 points [IMPROVEMENT]" in captured.out
    assert "Resolved Issues Fixed" in captured.out

    # JSON comparison output
    code_json = main(["compare", "comp-1", "comp-2", "--json"])
    assert code_json == 0
    captured_json = capsys.readouterr()
    assert '"score_delta": 15' in captured_json.out
