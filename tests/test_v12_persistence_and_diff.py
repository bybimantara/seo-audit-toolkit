"""Tests for Milestone v1.2: SQLite Persistence and Diffing Engine."""

from __future__ import annotations

from pathlib import Path

from seo_audit.db import delete_report, get_report, list_reports, save_report
from seo_audit.diff import compare_reports
from seo_audit.models import (
    BrokenLink,
    PageAudit,
    SiteAuditReport,
    SiteMetaResult,
)


def _build_dummy_report(
    report_id: str,
    target_url: str,
    health_score: int = 85,
    issues: list[str] | None = None,
    broken_links: list[BrokenLink] | None = None,
    llms_txt_found: bool = False,
) -> SiteAuditReport:
    p1 = PageAudit(
        url=f"{target_url}/",
        status_code=200,
        title="Home Page",
        title_length=9,
        meta_description="Sample description here",
        description_length=23,
        canonical_url=f"{target_url}/",
        h1_list=["Welcome"],
        issues=issues or ["Missing H2 tags"],
        page_score=health_score,
    )
    bl = broken_links or []
    return SiteAuditReport(
        report_id=report_id,
        target_url=target_url,
        health_score=health_score,
        duration_seconds=1.5,
        site_meta=SiteMetaResult(
            robots_url=f"{target_url}/robots.txt",
            robots_found=True,
            sitemap_url=f"{target_url}/sitemap.xml",
            sitemap_found=True,
            llms_txt_url=f"{target_url}/llms.txt",
            llms_txt_found=llms_txt_found,
        ),
        pages=[p1],
        broken_links=bl,
    )


def test_sqlite_save_and_retrieve(tmp_path: Path):
    db_file = tmp_path / "test_history.db"

    report = _build_dummy_report("rep-101", "https://example.com", health_score=90)
    save_report(report, db_path=db_file)

    retrieved = get_report("rep-101", db_path=db_file)
    assert retrieved is not None
    assert retrieved.report_id == "rep-101"
    assert retrieved.target_url == "https://example.com"
    assert retrieved.health_score == 90
    assert len(retrieved.pages) == 1
    assert retrieved.pages[0].title == "Home Page"
    assert retrieved.site_meta.robots_found is True


def test_sqlite_list_and_filter(tmp_path: Path):
    db_file = tmp_path / "test_history.db"

    r1 = _build_dummy_report("rep-1", "https://site-a.com", health_score=80)
    r2 = _build_dummy_report("rep-2", "https://site-b.com", health_score=95)
    save_report(r1, db_path=db_file)
    save_report(r2, db_path=db_file)

    all_reports = list_reports(limit=10, db_path=db_file)
    assert len(all_reports) == 2

    filtered = list_reports(domain="site-a", db_path=db_file)
    assert len(filtered) == 1
    assert filtered[0]["report_id"] == "rep-1"


def test_sqlite_delete_report(tmp_path: Path):
    db_file = tmp_path / "test_history.db"

    r1 = _build_dummy_report("rep-del", "https://site-del.com")
    save_report(r1, db_path=db_file)

    assert get_report("rep-del", db_path=db_file) is not None
    assert delete_report("rep-del", db_path=db_file) is True
    assert get_report("rep-del", db_path=db_file) is None
    assert delete_report("rep-non-existent", db_path=db_file) is False


def test_audit_diff_improving_score():
    r_old = _build_dummy_report(
        "old-1",
        "https://example.com",
        health_score=70,
        issues=["Missing meta description", "Missing canonical URL"],
        broken_links=[
            BrokenLink(
                source_url="https://example.com/",
                target_url="https://example.com/broken",
                status_code=404,
                error="HTTP 404",
            )
        ],
        llms_txt_found=False,
    )
    r_new = _build_dummy_report(
        "new-1",
        "https://example.com",
        health_score=85,
        issues=["Missing canonical URL", "Multiple H1 tags (2)"],
        broken_links=[],
        llms_txt_found=True,
    )

    diff = compare_reports(r_old, r_new)

    assert diff.old_report_id == "old-1"
    assert diff.new_report_id == "new-1"
    assert diff.score_delta == 15
    assert diff.broken_delta == -1

    # Issue diffs
    assert len(diff.resolved_issues) == 1
    assert diff.resolved_issues[0]["issue"] == "Missing meta description"

    assert len(diff.new_issues) == 1
    assert diff.new_issues[0]["issue"] == "Multiple H1 tags (2)"

    # Broken links
    assert len(diff.fixed_broken_links) == 1
    assert (
        diff.fixed_broken_links[0]["target_url"] == "https://example.com/broken"
    )
    assert len(diff.new_broken_links) == 0

    # Meta changes
    assert any("/llms.txt status changed" in c for c in diff.meta_changes)
