"""HTML analyzer, on-page SEO evaluator, and site metadata parser."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from seo_audit.models import PageAudit


def normalize_domain(netloc: str) -> str:
    """Normalize domain by stripping port and www prefix for fair comparison."""
    host = netloc.split(":")[0].lower()
    return host.removeprefix("www.")


def is_same_site(target_url: str, base_url: str) -> bool:
    """Check if target_url belongs to the same site/domain as base_url."""
    t_host = normalize_domain(urlparse(target_url).netloc)
    b_host = normalize_domain(urlparse(base_url).netloc)
    return bool(t_host and b_host and t_host == b_host)


def normalize_url(url: str, base_url: str) -> str | None:
    """Convert relative URL to absolute, remove fragments, and validate scheme."""
    joined = urljoin(base_url, url.strip())
    clean, _ = urldefrag(joined)
    parsed = urlparse(clean)
    if parsed.scheme not in ("http", "https"):
        return None
    return clean


def calculate_page_score(issues: list[str], status_code: int | None) -> int:
    """Calculate 0-100 score for a single page based on status and issues."""
    if status_code is None or status_code >= 400:
        return 0

    score = 100
    for issue in issues:
        if "Missing meta title" in issue:
            score -= 20
        elif "Meta title too" in issue:
            score -= 5
        elif "Missing meta description" in issue:
            score -= 15
        elif "Meta description too" in issue:
            score -= 5
        elif "Missing H1" in issue:
            score -= 20
        elif "Multiple H1" in issue:
            score -= 10
        elif "Missing H2" in issue:
            score -= 5
        elif "Missing canonical" in issue:
            score -= 10
        elif "Non-self-referencing canonical" in issue:
            score -= 5

    return max(0, min(100, score))


def analyze_page_html(
    html: str,
    requested_url: str,
    final_url: str,
    status_code: int | None,
    initial_status_code: int | None,
    response_time_ms: float,
    content_type: str = "text/html",
) -> PageAudit:
    """Analyze page HTML document and extract SEO metrics, tags, and links."""
    issues: list[str] = []
    effective_url = final_url or requested_url

    soup = BeautifulSoup(html, "html.parser")

    # Title extraction
    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else ""
    title_length = len(title)
    if not title:
        issues.append("Missing meta title")
    elif title_length < 30:
        issues.append(f"Meta title too short ({title_length} chars, recommended >= 30)")
    elif title_length > 60:
        issues.append(f"Meta title too long ({title_length} chars, recommended <= 60)")

    # Meta description extraction
    desc_tag = soup.find(
        "meta", attrs={"name": re.compile(r"^description$", re.IGNORECASE)}
    )
    desc = desc_tag.get("content", "").strip() if desc_tag else ""
    desc_length = len(desc)
    if not desc:
        issues.append("Missing meta description")
    elif desc_length < 70:
        issues.append(
            f"Meta description too short ({desc_length} chars, recommended >= 70)"
        )
    elif desc_length > 160:
        issues.append(
            f"Meta description too long ({desc_length} chars, recommended <= 160)"
        )

    # Canonical extraction
    canonical_tag = soup.find("link", attrs={"rel": lambda r: r and "canonical" in r})
    canonical_url = ""
    if canonical_tag and canonical_tag.get("href"):
        raw_canonical = canonical_tag.get("href").strip()
        canonical_url = normalize_url(raw_canonical, effective_url) or raw_canonical

    if not canonical_url:
        issues.append("Missing canonical URL")
    else:
        # Check self-referencing canonical
        clean_effective, _ = urldefrag(effective_url)
        clean_canonical, _ = urldefrag(canonical_url)
        if clean_effective.rstrip("/") != clean_canonical.rstrip("/"):
            issues.append(f"Non-self-referencing canonical (points to: {canonical_url})")

    # Heading tags extraction
    h1_list = [h.get_text().strip() for h in soup.find_all("h1") if h.get_text().strip()]
    if not h1_list:
        issues.append("Missing H1 tag")
    elif len(h1_list) > 1:
        issues.append(f"Multiple H1 tags ({len(h1_list)} found)")

    h2_list = [h.get_text().strip() for h in soup.find_all("h2") if h.get_text().strip()]
    if not h2_list:
        issues.append("Missing H2 tag")

    # Links extraction
    internal_links: list[tuple[str, str]] = []
    external_links: list[tuple[str, str]] = []

    for a in soup.find_all("a", href=True):
        raw_href = a["href"].strip()
        if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        resolved = normalize_url(raw_href, effective_url)
        if not resolved:
            continue

        anchor_text = a.get_text().strip()
        if is_same_site(resolved, effective_url):
            internal_links.append((resolved, anchor_text))
        else:
            external_links.append((resolved, anchor_text))

    page_score = calculate_page_score(issues, status_code)

    return PageAudit(
        url=requested_url,
        final_url=effective_url,
        initial_status_code=initial_status_code,
        status_code=status_code,
        response_time_ms=response_time_ms,
        content_type=content_type,
        title=title,
        title_length=title_length,
        meta_description=desc,
        description_length=desc_length,
        canonical_url=canonical_url,
        h1_list=h1_list,
        h2_list=h2_list,
        internal_links=internal_links,
        external_links=external_links,
        internal_links_count=len(internal_links),
        external_links_count=len(external_links),
        broken_links=[],
        issues=issues,
        page_score=page_score,
    )


def parse_robots_txt(content: str, robots_url: str) -> tuple[list[str], list[str]]:
    """Parse robots.txt to extract declared Sitemap directives and find potential issues."""
    sitemaps: list[str] = []
    issues: list[str] = []

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            if key.strip().lower() == "sitemap":
                sitemap_val = val.strip()
                if sitemap_val:
                    sitemaps.append(sitemap_val)

    if not sitemaps:
        issues.append("No Sitemap directive specified in robots.txt")

    return sitemaps, issues


def parse_sitemap_xml(content: str) -> tuple[bool, bool, list[str]]:
    """Parse sitemap.xml to extract URLs and detect if it is a sitemapindex."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return False, False, []

    tag_clean = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    is_index = tag_clean.lower() == "sitemapindex"
    urls: list[str] = []

    for elem in root.iter():
        elem_tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if elem_tag.lower() == "loc" and elem.text:
            url_text = elem.text.strip()
            if url_text:
                urls.append(url_text)

    return True, is_index, urls
