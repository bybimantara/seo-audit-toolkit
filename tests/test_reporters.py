"""Unit tests for CSV and HTML report generators."""

from seo_audit.models import BrokenLink, PageAudit, SiteAuditReport, SiteMetaResult
from seo_audit.reporters import generate_csv_report, generate_html_report


def test_generate_csv_report():
    report = SiteAuditReport(
        target_url="https://example.com",
        pages=[
            PageAudit(
                url="https://example.com",
                status_code=200,
                response_time_ms=150.2,
                title="Example Domain",
                title_length=14,
                meta_description="Meta desc",
                description_length=9,
                h1_list=["Example H1"],
                h2_list=["H2 Sub"],
                canonical_url="https://example.com",
                internal_links_count=2,
                external_links_count=1,
                broken_links=[
                    BrokenLink(
                        source_url="https://example.com",
                        target_url="https://example.com/404",
                        anchor_text="Dead",
                        is_external=False,
                        status_code=404,
                        error="HTTP 404",
                    )
                ],
                issues=["Meta title too short"],
            )
        ],
        broken_links=[
            BrokenLink(
                source_url="https://example.com",
                target_url="https://example.com/404",
                anchor_text="Dead",
                is_external=False,
                status_code=404,
                error="HTTP 404",
            )
        ],
    )

    csv_out = generate_csv_report(report)
    lines = csv_out.strip().split("\n")
    assert len(lines) == 2  # header + 1 row
    assert "URL,HTTP Status,Response Time (ms)" in lines[0]
    assert "https://example.com,200,150.2" in lines[1]
    assert "HTTP 404" in lines[1]


def test_generate_html_report():
    report = SiteAuditReport(
        target_url="https://example.com",
        health_score=85,
        site_meta=SiteMetaResult(robots_found=True, sitemap_found=True, sitemap_valid_xml=True, sitemap_url_count=5),
        pages=[
            PageAudit(
                url="https://example.com",
                status_code=200,
                response_time_ms=100.0,
                title="Home",
                title_length=4,
                h1_list=["Welcome"],
                canonical_url="https://example.com",
                issues=["Title too short"],
            )
        ],
        broken_links=[],
    )

    html_out = generate_html_report(report)
    assert "<!DOCTYPE html>" in html_out
    assert "SEO Audit Report - https://example.com" in html_out
    assert "85/100" in html_out
    assert "No broken links found" in html_out
