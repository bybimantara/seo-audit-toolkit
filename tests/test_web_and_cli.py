"""Unit and integration tests for FastAPI Web App and CLI."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from seo_audit.cli import main
from seo_audit.models import PageAudit, SiteAuditReport
from seo_audit.web import app

client = TestClient(app)


def test_web_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_web_index_page():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SEO Audit Toolkit" in resp.text
    assert "<form id=\"auditForm\">" in resp.text


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
            json={"url": "https://mocktest.com", "max_pages": 5, "max_external_links": 5},
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
        assert "SEO Audit Report - https://mocktest.com" in html_resp.text


def test_cli_help():
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_cli_no_args():
    code = main([])
    assert code == 2


def test_cli_audit_execution(tmp_path):
    csv_file = tmp_path / "test_report.csv"
    html_file = tmp_path / "test_report.html"

    mock_report = SiteAuditReport(
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
            "--max-pages", "5",
            "--csv", str(csv_file),
            "--html", str(html_file),
        ])
        assert code == 0
        assert csv_file.exists()
        assert html_file.exists()
        assert "https://clitest.com,200" in csv_file.read_text(encoding="utf-8")
        assert "SEO Audit Report" in html_file.read_text(encoding="utf-8")
