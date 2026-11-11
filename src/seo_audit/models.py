"""Data contracts and models for SEO Audit Toolkit."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class SocialMeta:
    """OpenGraph and Twitter Card metadata."""

    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    og_url: str = ""
    twitter_card: str = ""
    issues: list[str] = field(default_factory=list)


@dataclass
class ImageIssue:
    """Details of an image lacking alt text or dimensions."""

    src: str
    missing_alt: bool = False
    missing_dimensions: bool = False


@dataclass
class RedirectHop:
    """Details of an intermediate HTTP redirect hop."""

    url: str
    status_code: int


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


@dataclass
class BrokenLink:
    """Details of a broken link."""

    source_url: str
    target_url: str
    anchor_text: str = ""
    is_external: bool = False
    status_code: int | None = None
    error: str = ""


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
