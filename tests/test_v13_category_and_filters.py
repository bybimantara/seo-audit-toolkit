"""Tests for Milestone v1.3: Category Tabs and Severity Filters."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from seo_audit.models import (
    BrokenLink,
    IssueCategory,
    IssueSeverity,
    PageAudit,
    SiteAuditReport,
    classify_issue,
)
from seo_audit.reporters import generate_html_report
from seo_audit.web import app

client = TestClient(app)


def test_classify_issue_rules():
    # Critical checks
    assert classify_issue("Missing title tag") == (
        IssueSeverity.CRITICAL.value,
        IssueCategory.ON_PAGE.value,
    )
    assert classify_issue("Multiple H1 tags (3)") == (
        IssueSeverity.CRITICAL.value,
        IssueCategory.ON_PAGE.value,
    )
    assert classify_issue("Broken link: https://example.com/dead (HTTP 404)") == (
        IssueSeverity.CRITICAL.value,
        IssueCategory.CRAWLABILITY.value,
    )
    assert classify_issue("Disallowed from root / in robots.txt") == (
        IssueSeverity.CRITICAL.value,
        IssueCategory.DIRECTIVES.value,
    )

    # Warning checks
    assert classify_issue("Missing meta description") == (
        IssueSeverity.WARNING.value,
        IssueCategory.ON_PAGE.value,
    )
    assert classify_issue("Missing canonical URL") == (
        IssueSeverity.WARNING.value,
        IssueCategory.ON_PAGE.value,
    )
    assert classify_issue("Heading level skipped: h3 after h1") == (
        IssueSeverity.WARNING.value,
        IssueCategory.ON_PAGE.value,
    )
    assert classify_issue("4 image(s) missing alt text attribute") == (
        IssueSeverity.WARNING.value,
        IssueCategory.IMAGES.value,
    )
    assert classify_issue("Invalid JSON-LD syntax in script tag") == (
        IssueSeverity.WARNING.value,
        IssueCategory.SOCIAL.value,
    )

    # Notice checks
    assert classify_issue("Missing H2 headings") == (
        IssueSeverity.NOTICE.value,
        IssueCategory.ON_PAGE.value,
    )
    assert classify_issue(
        "2 image(s) missing width or height attributes"
    ) == (
        IssueSeverity.NOTICE.value,
        IssueCategory.IMAGES.value,
    )
    assert classify_issue("Missing Open Graph image (og:image)") == (
        IssueSeverity.NOTICE.value,
        IssueCategory.SOCIAL.value,
    )
    assert classify_issue("Missing /llms.txt file") == (
        IssueSeverity.NOTICE.value,
        IssueCategory.DIRECTIVES.value,
    )


def test_report_issue_counts():
    p1 = PageAudit(
        url="https://testsite.com/p1",
        issues=["Missing title tag", "Missing meta description"],
    )
    p2 = PageAudit(
        url="https://testsite.com/p2",
        issues=[
            "2 image(s) missing alt text attribute",
            "Missing Open Graph image (og:image)",
        ],
    )
    bl = BrokenLink(
        source_url="https://testsite.com/p1",
        target_url="https://testsite.com/broken",
        status_code=404,
        error="HTTP 404",
    )

    report = SiteAuditReport(
        target_url="https://testsite.com",
        pages=[p1, p2],
        broken_links=[bl],
    )

    sev = report.issue_counts_by_severity
    cat = report.issue_counts_by_category

    # Broken link adds 1 critical
    # p1 adds 1 critical (title) + 1 warning (meta desc)
    # p2 adds 1 warning (image alt) + 1 notice (og:image)
    assert sev["critical"] == 2
    assert sev["warning"] == 2
    assert sev["notice"] == 1

    assert cat["crawlability"] == 1  # broken link
    assert cat["on_page"] == 2  # title + meta desc
    assert cat["images"] == 1  # image alt
    assert cat["social"] == 1  # og:image


def test_html_report_filter_controls():
    report = SiteAuditReport(
        target_url="https://filtertest.com",
        pages=[
            PageAudit(
                url="https://filtertest.com/",
                status_code=200,
                issues=["Missing title tag"],
            ),
            PageAudit(
                url="https://filtertest.com/about",
                status_code=200,
                issues=["Missing Open Graph image (og:image)"],
            ),
        ],
    )

    html_content = generate_html_report(report)

    # Check category tab controls
    assert 'class="filter-bar"' in html_content
    assert 'data-cat="all"' in html_content
    assert 'data-cat="crawlability"' in html_content
    assert 'data-cat="on_page"' in html_content
    assert 'data-cat="images"' in html_content
    assert 'data-cat="social"' in html_content

    # Check severity controls
    assert 'data-sev="critical"' in html_content
    assert 'data-sev="warning"' in html_content
    assert 'data-sev="notice"' in html_content

    # Check table row data attributes and pills
    assert 'class="page-row"' in html_content
    assert 'data-categories=' in html_content
    assert 'data-severities=' in html_content
    assert 'tag-critical' in html_content
    assert 'tag-notice' in html_content

    # Check client-side filter function
    assert "function applyFilters()" in html_content


def test_web_api_audit_returns_breakdown():
    mock_report = SiteAuditReport(
        target_url="https://catapi.com",
        health_score=88,
        pages=[
            PageAudit(
                url="https://catapi.com/",
                status_code=200,
                issues=["Missing title tag", "Missing canonical URL"],
            )
        ],
    )

    with patch("seo_audit.web.crawl_site", return_value=mock_report):
        resp = client.post(
            "/api/audit",
            json={"url": "https://catapi.com", "max_pages": 5},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert "severity_counts" in data
        assert "category_counts" in data
        assert data["severity_counts"]["critical"] == 1
        assert data["severity_counts"]["warning"] == 1
        assert data["category_counts"]["on_page"] == 2
