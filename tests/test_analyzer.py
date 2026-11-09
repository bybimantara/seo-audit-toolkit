"""Unit tests for SEO Audit Toolkit models and analyzer."""

from seo_audit.analyzer import (
    analyze_page_html,
    calculate_page_score,
    is_same_site,
    normalize_domain,
    normalize_url,
    parse_robots_txt,
    parse_sitemap_xml,
)


def test_normalize_domain_and_is_same_site():
    assert normalize_domain("example.com") == "example.com"
    assert normalize_domain("www.example.com") == "example.com"
    assert normalize_domain("WWW.EXAMPLE.COM:8080") == "example.com"

    assert is_same_site("https://www.example.com/blog", "https://example.com") is True
    assert is_same_site("http://example.com/contact", "https://www.example.com") is True
    assert is_same_site("https://otherdomain.com", "https://example.com") is False


def test_normalize_url():
    base = "https://example.com/sub/page"
    assert normalize_url("/about#team", base) == "https://example.com/about"
    assert normalize_url("post-1", base) == "https://example.com/sub/post-1"
    assert normalize_url("mailto:test@example.com", base) is None
    assert normalize_url("javascript:void(0)", base) is None


def test_analyze_page_html_healthy():
    html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Valid SEO Title for Testing Purposes</title>
        <meta name="description" content="This is an ideal meta description that contains well over seventy characters for proper SEO testing and analysis." />
        <link rel="canonical" href="https://example.com/page" />
      </head>
      <body>
        <h1>Primary Heading One</h1>
        <h2>Section Heading Two</h2>
        <a href="/internal-link">Internal Page</a>
        <a href="https://external.org/info">External Reference</a>
      </body>
    </html>
    """
    audit = analyze_page_html(
        html=html,
        requested_url="https://example.com/page",
        final_url="https://example.com/page",
        status_code=200,
        initial_status_code=200,
        response_time_ms=120.0,
    )

    assert audit.title == "Valid SEO Title for Testing Purposes"
    assert audit.title_length == len(audit.title)
    assert audit.h1_list == ["Primary Heading One"]
    assert audit.h2_list == ["Section Heading Two"]
    assert audit.canonical_url == "https://example.com/page"
    assert audit.internal_links_count == 1
    assert audit.external_links_count == 1
    assert len(audit.issues) == 0
    assert audit.page_score == 100


def test_analyze_page_html_with_issues():
    html = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Short</title>
        <!-- missing description -->
        <link rel="canonical" href="https://other.com/target" />
      </head>
      <body>
        <h1>Heading 1</h1>
        <h1>Duplicate Heading 1</h1>
        <!-- missing H2 -->
      </body>
    </html>
    """
    audit = analyze_page_html(
        html=html,
        requested_url="https://example.com/test",
        final_url="https://example.com/test",
        status_code=200,
        initial_status_code=200,
        response_time_ms=80.0,
    )

    issue_text = " ".join(audit.issues)
    assert "Meta title too short" in issue_text
    assert "Missing meta description" in issue_text
    assert "Non-self-referencing canonical" in issue_text
    assert "Multiple H1 tags" in issue_text
    assert "Missing H2 tag" in issue_text
    assert audit.page_score < 80


def test_calculate_page_score_error_status():
    assert calculate_page_score([], 404) == 0
    assert calculate_page_score([], 500) == 0
    assert calculate_page_score([], None) == 0


def test_parse_robots_txt():
    robots = """
    User-agent: *
    Disallow: /admin/
    Sitemap: https://example.com/sitemap.xml
    Sitemap: https://example.com/sitemap-news.xml
    """
    sitemaps, issues = parse_robots_txt(robots, "https://example.com/robots.txt")
    assert sitemaps == [
        "https://example.com/sitemap.xml",
        "https://example.com/sitemap-news.xml",
    ]
    assert len(issues) == 0

    _, empty_issues = parse_robots_txt(
        "User-agent: *\nDisallow:", "https://example.com/robots.txt"
    )
    assert any("No Sitemap directive" in i for i in empty_issues)


def test_parse_sitemap_xml():
    urlset_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/</loc></url>
      <url><loc>https://example.com/about</loc></url>
    </urlset>
    """
    valid, is_index, urls = parse_sitemap_xml(urlset_xml)
    assert valid is True
    assert is_index is False
    assert urls == ["https://example.com/", "https://example.com/about"]

    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://example.com/post-sitemap.xml</loc></sitemap>
    </sitemapindex>
    """
    valid_idx, is_idx, idx_urls = parse_sitemap_xml(index_xml)
    assert valid_idx is True
    assert is_idx is True
    assert idx_urls == ["https://example.com/post-sitemap.xml"]

    invalid, _, _ = parse_sitemap_xml("not xml")
    assert invalid is False
