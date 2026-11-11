"""HTML analyzer, on-page SEO evaluator, and site metadata parser."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from seo_audit.models import ImageIssue, PageAudit, SocialMeta


def extract_social_meta(soup: BeautifulSoup) -> SocialMeta:
    """Extract OpenGraph and Twitter card metadata."""
    og_title = ""
    og_description = ""
    og_image = ""
    og_url = ""
    twitter_card = ""
    issues: list[str] = []

    for tag in soup.find_all("meta"):
        prop = tag.get("property", "").strip().lower()
        name = tag.get("name", "").strip().lower()
        content = tag.get("content", "").strip()

        if prop == "og:title":
            og_title = content
        elif prop == "og:description":
            og_description = content
        elif prop == "og:image":
            og_image = content
        elif prop == "og:url":
            og_url = content
        elif name == "twitter:card":
            twitter_card = content

    if not og_title:
        issues.append("Missing og:title")
    if not og_description:
        issues.append("Missing og:description")
    if not og_image:
        issues.append("Missing og:image")

    return SocialMeta(
        og_title=og_title,
        og_description=og_description,
        og_image=og_image,
        og_url=og_url,
        twitter_card=twitter_card,
        issues=issues,
    )


def audit_images(soup: BeautifulSoup, base_url: str) -> list[ImageIssue]:
    """Audit <img> tags for missing alt text and dimensions."""
    issues: list[ImageIssue] = []
    for img in soup.find_all("img"):
        src = img.get("src", "").strip()
        if not src:
            continue

        resolved_src = normalize_url(src, base_url) or src
        alt = img.get("alt")
        has_alt = alt is not None and bool(alt.strip())

        has_width = bool(img.get("width"))
        has_height = bool(img.get("height"))
        missing_dimensions = not (has_width and has_height)

        if not has_alt or missing_dimensions:
            issues.append(
                ImageIssue(
                    src=resolved_src,
                    missing_alt=not has_alt,
                    missing_dimensions=missing_dimensions,
                )
            )
    return issues


def check_heading_hierarchy(soup: BeautifulSoup) -> list[str]:
    """Validate heading hierarchy so headings don't skip levels (e.g. H1 -> H3)."""
    issues: list[str] = []
    heading_tags = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

    prev_level = 0
    for tag in heading_tags:
        level = int(tag.name[1])
        # If heading jumps down by more than 1 level (e.g. 1 -> 3 or 2 -> 4)
        if prev_level > 0 and level > prev_level + 1:
            issues.append(f"Heading level skipped from H{prev_level} to H{level}")
        prev_level = level

    return issues


def check_json_ld(soup: BeautifulSoup) -> tuple[bool, bool]:
    """Check for presence of JSON-LD scripts and validate JSON syntax."""
    json_ld_tags = soup.find_all("script", attrs={"type": "application/ld+json"})
    if not json_ld_tags:
        return False, False

    all_valid = True
    for tag in json_ld_tags:
        content = tag.string or tag.get_text() or ""
        content = content.strip()
        if not content:
            all_valid = False
            continue
        try:
            json.loads(content)
        except Exception:
            all_valid = False

    return True, all_valid


def parse_ai_bot_rules(robots_txt: str) -> dict[str, str]:
    """Parse robots.txt to determine directives for AI bots (GPTBot, ClaudeBot, PerplexityBot, etc.)."""
    common_ai_bots = ["gptbot", "claudebot", "perplexitybot", "ccbot", "bytespider"]
    rules: dict[str, str] = {}

    current_agents: list[str] = []
    for line in robots_txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip().lower()
            val = val.strip().lower()

            if key == "user-agent":
                current_agents = [val] if val else []
            elif key == "disallow":
                for agent in current_agents:
                    for bot in common_ai_bots:
                        if agent == bot or agent == "*":
                            # if disallowed root path '/'
                            if val == "/" or val == "/*":
                                rules[bot.capitalize()] = "disallowed"
            elif key == "allow":
                for agent in current_agents:
                    for bot in common_ai_bots:
                        if agent == bot:
                            if val == "/":
                                rules[bot.capitalize()] = "allowed"

    # Default unspecified bots to 'allowed' if not explicitly disallowed
    for bot in common_ai_bots:
        name = bot.capitalize()
        if name not in rules:
            rules[name] = "allowed"

    return rules


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

    # Extended Rules: Heading hierarchy, Social Meta, Images, JSON-LD
    hierarchy_issues = check_heading_hierarchy(soup)
    issues.extend(hierarchy_issues)

    social_meta = extract_social_meta(soup)

    image_issues = audit_images(soup, effective_url)
    missing_alt_count = sum(1 for img in image_issues if img.missing_alt)
    if missing_alt_count > 0:
        issues.append(f"{missing_alt_count} image(s) missing alt text")

    has_json_ld, json_ld_valid = check_json_ld(soup)
    if has_json_ld and not json_ld_valid:
        issues.append("Invalid JSON-LD structured data syntax")

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
        social_meta=social_meta,
        image_issues=image_issues,
        heading_hierarchy_issues=hierarchy_issues,
        has_json_ld=has_json_ld,
        json_ld_valid=json_ld_valid,
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
