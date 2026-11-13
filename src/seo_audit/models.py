"""Data contracts and models for SEO Audit Toolkit."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    NOTICE = "notice"


class IssueCategory(str, Enum):
    ALL = "all"
    CRAWLABILITY = "crawlability"
    ON_PAGE = "on_page"
    IMAGES = "images"
    SOCIAL = "social"
    DIRECTIVES = "directives"


def classify_issue(issue_str: str) -> tuple[str, str]:
    """Classify an issue string into (severity, category).

    Returns:
        tuple[str, str]: (severity, category) matching IssueSeverity and IssueCategory values.
    """
    msg = issue_str.lower()

    if any(
        k in msg
        for k in [
            "missing title tag",
            "missing meta title",
            "missing h1",
            "multiple h1",
            "redirect loop",
            "http 404",
            "http 500",
            "page returned http error",
            "broken link",
            "disallowed from root",
        ]
    ):
        if any(
            k in msg
            for k in ["http 404", "http 500", "page returned http error", "broken link", "redirect loop"]
        ):
            return IssueSeverity.CRITICAL.value, IssueCategory.CRAWLABILITY.value
        if "disallowed from root" in msg:
            return IssueSeverity.CRITICAL.value, IssueCategory.DIRECTIVES.value
        return IssueSeverity.CRITICAL.value, IssueCategory.ON_PAGE.value

    # Social & Schema category (checked before Images so 'og:image' is recognized as social)
    if any(
        k in msg
        for k in ["open graph", "og:", "twitter card", "json-ld", "schema"]
    ):
        if "invalid json-ld" in msg:
            return IssueSeverity.WARNING.value, IssueCategory.SOCIAL.value
        return IssueSeverity.NOTICE.value, IssueCategory.SOCIAL.value

    if any(k in msg for k in ["image", "alt text", "width or height"]):
        if "width or height" in msg:
            return IssueSeverity.NOTICE.value, IssueCategory.IMAGES.value
        return IssueSeverity.WARNING.value, IssueCategory.IMAGES.value

    if any(k in msg for k in ["robots.txt", "sitemap.xml", "llms.txt", "bot", "noindex", "x-robots-tag"]):
        if "llms.txt" in msg:
            return IssueSeverity.NOTICE.value, IssueCategory.DIRECTIVES.value
        return IssueSeverity.WARNING.value, IssueCategory.DIRECTIVES.value

    if any(
        k in msg
        for k in [
            "redirect",
            "status",
            "latency",
            "timeout",
            "connecterror",
            "slow response",
        ]
    ):
        return IssueSeverity.WARNING.value, IssueCategory.CRAWLABILITY.value

    if any(k in msg for k in ["missing h2", "heading level skipped", "thin content", "spa/csr"]):
        if "heading level skipped" in msg:
            return IssueSeverity.WARNING.value, IssueCategory.ON_PAGE.value
        return IssueSeverity.NOTICE.value, IssueCategory.ON_PAGE.value

    return IssueSeverity.WARNING.value, IssueCategory.ON_PAGE.value


@dataclass
class SocialMeta:
    """OpenGraph and Twitter Card metadata."""

    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    og_url: str = ""
    twitter_card: str = ""
    issues: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SocialMeta:
        return cls(
            og_title=data.get("og_title", ""),
            og_description=data.get("og_description", ""),
            og_image=data.get("og_image", ""),
            og_url=data.get("og_url", ""),
            twitter_card=data.get("twitter_card", ""),
            issues=list(data.get("issues", [])),
        )


@dataclass
class ImageIssue:
    """Details of an image lacking alt text or dimensions."""

    src: str
    missing_alt: bool = False
    missing_dimensions: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImageIssue:
        return cls(
            src=data.get("src", ""),
            missing_alt=bool(data.get("missing_alt", False)),
            missing_dimensions=bool(data.get("missing_dimensions", False)),
        )


@dataclass
class RedirectHop:
    """Details of an intermediate HTTP redirect hop."""

    url: str
    status_code: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RedirectHop:
        return cls(
            url=data.get("url", ""),
            status_code=int(data.get("status_code", 0)),
        )


@dataclass
class SiteMetaResult:
    """Status of robots.txt and sitemap.xml, plus AI readiness."""

    robots_url: str = ""
    robots_status: int | None = None
    robots_found: bool = False
    sitemaps_in_robots: list[str] = field(default_factory=list)
    sitemap_url: str = ""
    sitemap_status: int | None = None
    sitemap_found: bool = False
    sitemap_valid_xml: bool = False
    sitemap_is_index: bool = False
    sitemap_url_count: int = 0
    llms_txt_url: str = ""
    llms_txt_found: bool = False
    ai_bot_rules: dict[str, str] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SiteMetaResult:
        return cls(
            robots_url=data.get("robots_url", ""),
            robots_status=data.get("robots_status"),
            robots_found=bool(data.get("robots_found", False)),
            sitemaps_in_robots=list(data.get("sitemaps_in_robots", [])),
            sitemap_url=data.get("sitemap_url", ""),
            sitemap_status=data.get("sitemap_status"),
            sitemap_found=bool(data.get("sitemap_found", False)),
            sitemap_valid_xml=bool(data.get("sitemap_valid_xml", False)),
            sitemap_is_index=bool(data.get("sitemap_is_index", False)),
            sitemap_url_count=int(data.get("sitemap_url_count", 0)),
            llms_txt_url=data.get("llms_txt_url", ""),
            llms_txt_found=bool(data.get("llms_txt_found", False)),
            ai_bot_rules=dict(data.get("ai_bot_rules", {})),
            issues=list(data.get("issues", [])),
        )


@dataclass
class BrokenLink:
    """Details of a broken link."""

    source_url: str
    target_url: str
    anchor_text: str = ""
    is_external: bool = False
    status_code: int | None = None
    error: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BrokenLink:
        return cls(
            source_url=data.get("source_url", ""),
            target_url=data.get("target_url", ""),
            anchor_text=data.get("anchor_text", ""),
            is_external=bool(data.get("is_external", False)),
            status_code=data.get("status_code"),
            error=data.get("error", ""),
        )


@dataclass
class PageAudit:
    """Audit results for a single HTML page."""

    url: str
    final_url: str = ""
    initial_status_code: int | None = None
    status_code: int | None = None
    response_time_ms: float = 0.0
    content_type: str = ""
    title: str = ""
    title_length: int = 0
    meta_description: str = ""
    description_length: int = 0
    canonical_url: str = ""
    h1_list: list[str] = field(default_factory=list)
    h2_list: list[str] = field(default_factory=list)
    internal_links: list[tuple[str, str]] = field(default_factory=list)  # (url, anchor)
    external_links: list[tuple[str, str]] = field(default_factory=list)  # (url, anchor)
    internal_links_count: int = 0
    external_links_count: int = 0
    broken_links: list[BrokenLink] = field(default_factory=list)
    social_meta: SocialMeta = field(default_factory=SocialMeta)
    image_issues: list[ImageIssue] = field(default_factory=list)
    heading_hierarchy_issues: list[str] = field(default_factory=list)
    has_json_ld: bool = False
    json_ld_valid: bool = False
    redirect_chain: list[RedirectHop] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    page_score: int = 100

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PageAudit:
        raw_int_links = data.get("internal_links", [])
        int_links = [
            (str(item[0]), str(item[1])) for item in raw_int_links if len(item) >= 2
        ]
        raw_ext_links = data.get("external_links", [])
        ext_links = [
            (str(item[0]), str(item[1])) for item in raw_ext_links if len(item) >= 2
        ]

        return cls(
            url=data.get("url", ""),
            final_url=data.get("final_url", ""),
            initial_status_code=data.get("initial_status_code"),
            status_code=data.get("status_code"),
            response_time_ms=float(data.get("response_time_ms", 0.0)),
            content_type=data.get("content_type", ""),
            title=data.get("title", ""),
            title_length=int(data.get("title_length", 0)),
            meta_description=data.get("meta_description", ""),
            description_length=int(data.get("description_length", 0)),
            canonical_url=data.get("canonical_url", ""),
            h1_list=list(data.get("h1_list", [])),
            h2_list=list(data.get("h2_list", [])),
            internal_links=int_links,
            external_links=ext_links,
            internal_links_count=int(data.get("internal_links_count", len(int_links))),
            external_links_count=int(data.get("external_links_count", len(ext_links))),
            broken_links=[
                BrokenLink.from_dict(bl) for bl in data.get("broken_links", [])
            ],
            social_meta=SocialMeta.from_dict(data.get("social_meta", {})),
            image_issues=[
                ImageIssue.from_dict(img) for img in data.get("image_issues", [])
            ],
            heading_hierarchy_issues=list(data.get("heading_hierarchy_issues", [])),
            has_json_ld=bool(data.get("has_json_ld", False)),
            json_ld_valid=bool(data.get("json_ld_valid", False)),
            redirect_chain=[
                RedirectHop.from_dict(hop) for hop in data.get("redirect_chain", [])
            ],
            issues=list(data.get("issues", [])),
            page_score=int(data.get("page_score", 100)),
        )


@dataclass
class SiteAuditReport:
    """Aggregate audit report for the entire website."""

    target_url: str
    audited_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    max_pages: int = 50
    duration_seconds: float = 0.0
    health_score: int = 100
    site_meta: SiteMetaResult = field(default_factory=SiteMetaResult)
    pages: list[PageAudit] = field(default_factory=list)
    broken_links: list[BrokenLink] = field(default_factory=list)

    @property
    def issue_counts_by_severity(self) -> dict[str, int]:
        """Aggregate total count of issues across all pages grouped by severity."""
        counts = {"critical": 0, "warning": 0, "notice": 0}
        counts["critical"] += len(self.broken_links)
        for page in self.pages:
            for issue in page.issues:
                sev, _ = classify_issue(issue)
                counts[sev] = counts.get(sev, 0) + 1
        return counts

    @property
    def issue_counts_by_category(self) -> dict[str, int]:
        """Aggregate total count of issues across all pages grouped by category."""
        counts = {
            "crawlability": len(self.broken_links),
            "on_page": 0,
            "images": 0,
            "social": 0,
            "directives": 0,
        }
        for page in self.pages:
            for issue in page.issues:
                _, cat = classify_issue(issue)
                counts[cat] = counts.get(cat, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        """Convert report to serializable dictionary."""
        return asdict(self)

    def to_json(self, indent: int | None = None) -> str:
        """Serialize report to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SiteAuditReport:
        """Construct SiteAuditReport from dictionary."""
        return cls(
            target_url=data.get("target_url", ""),
            audited_at=data.get("audited_at", ""),
            report_id=data.get("report_id", uuid.uuid4().hex[:8]),
            max_pages=int(data.get("max_pages", 50)),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            health_score=int(data.get("health_score", 100)),
            site_meta=SiteMetaResult.from_dict(data.get("site_meta", {})),
            pages=[PageAudit.from_dict(p) for p in data.get("pages", [])],
            broken_links=[
                BrokenLink.from_dict(bl) for bl in data.get("broken_links", [])
            ],
        )

    @classmethod
    def from_json(cls, json_str: str) -> SiteAuditReport:
        """Construct SiteAuditReport from JSON string."""
        return cls.from_dict(json.loads(json_str))
