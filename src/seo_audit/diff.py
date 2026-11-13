"""Audit diffing and regression tracking engine for SEO Audit Toolkit."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from seo_audit.models import SiteAuditReport


@dataclass
class AuditDiffReport:
    """Detailed comparison between an earlier and later audit report."""

    target_url: str
    old_report_id: str
    new_report_id: str
    old_audited_at: str
    new_audited_at: str
    old_score: int
    new_score: int
    score_delta: int
    pages_count_old: int
    pages_count_new: int
    pages_delta: int
    broken_count_old: int
    broken_count_new: int
    broken_delta: int
    new_pages: list[str] = field(default_factory=list)
    removed_pages: list[str] = field(default_factory=list)
    new_issues: list[dict[str, str]] = field(default_factory=list)
    resolved_issues: list[dict[str, str]] = field(default_factory=list)
    new_broken_links: list[dict[str, Any]] = field(default_factory=list)
    fixed_broken_links: list[dict[str, Any]] = field(default_factory=list)
    meta_changes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert diff report to serializable dictionary."""
        return asdict(self)


def compare_reports(
    old_report: SiteAuditReport, new_report: SiteAuditReport
) -> AuditDiffReport:
    """Compare two audit reports to compute score delta, regressions, and resolved issues."""
    old_pages_urls = {p.url for p in old_report.pages}
    new_pages_urls = {p.url for p in new_report.pages}

    new_pages = sorted(new_pages_urls - old_pages_urls)
    removed_pages = sorted(old_pages_urls - new_pages_urls)

    # Issue comparison by (url, issue)
    old_issues_set = {
        (p.url, issue) for p in old_report.pages for issue in p.issues
    }
    new_issues_set = {
        (p.url, issue) for p in new_report.pages for issue in p.issues
    }

    new_issues = [
        {"url": url, "issue": issue}
        for (url, issue) in sorted(new_issues_set - old_issues_set)
    ]
    resolved_issues = [
        {"url": url, "issue": issue}
        for (url, issue) in sorted(old_issues_set - new_issues_set)
    ]

    # Broken links comparison
    old_bl_map = {
        (bl.source_url, bl.target_url): bl for bl in old_report.broken_links
    }
    new_bl_map = {
        (bl.source_url, bl.target_url): bl for bl in new_report.broken_links
    }

    new_broken = [
        asdict(bl) for key, bl in new_bl_map.items() if key not in old_bl_map
    ]
    fixed_broken = [
        asdict(bl) for key, bl in old_bl_map.items() if key not in new_bl_map
    ]

    # Meta directive changes
    meta_changes: list[str] = []
    if old_report.site_meta.robots_found != new_report.site_meta.robots_found:
        status_now = "found" if new_report.site_meta.robots_found else "missing"
        meta_changes.append(f"robots.txt status changed to {status_now}")

    if old_report.site_meta.sitemap_found != new_report.site_meta.sitemap_found:
        status_now = "found" if new_report.site_meta.sitemap_found else "missing"
        meta_changes.append(f"sitemap.xml status changed to {status_now}")

    if old_report.site_meta.llms_txt_found != new_report.site_meta.llms_txt_found:
        status_now = "found" if new_report.site_meta.llms_txt_found else "missing"
        meta_changes.append(f"/llms.txt status changed to {status_now}")

    score_delta = new_report.health_score - old_report.health_score
    pages_delta = len(new_report.pages) - len(old_report.pages)
    broken_delta = len(new_report.broken_links) - len(old_report.broken_links)

    return AuditDiffReport(
        target_url=new_report.target_url,
        old_report_id=old_report.report_id,
        new_report_id=new_report.report_id,
        old_audited_at=old_report.audited_at,
        new_audited_at=new_report.audited_at,
        old_score=old_report.health_score,
        new_score=new_report.health_score,
        score_delta=score_delta,
        pages_count_old=len(old_report.pages),
        pages_count_new=len(new_report.pages),
        pages_delta=pages_delta,
        broken_count_old=len(old_report.broken_links),
        broken_count_new=len(new_report.broken_links),
        broken_delta=broken_delta,
        new_pages=new_pages,
        removed_pages=removed_pages,
        new_issues=new_issues,
        resolved_issues=resolved_issues,
        new_broken_links=new_broken,
        fixed_broken_links=fixed_broken,
        meta_changes=meta_changes,
    )
