"""Unit and integration tests for v1.1 extended rules."""

from bs4 import BeautifulSoup

from seo_audit.analyzer import (
    audit_images,
    check_heading_hierarchy,
    check_json_ld,
    extract_social_meta,
    parse_ai_bot_rules,
)


def test_extract_social_meta_complete():
    html = """
    <html>
      <head>
        <meta property="og:title" content="My Great Article" />
        <meta property="og:description" content="An in-depth guide on SEO" />
        <meta property="og:image" content="https://example.com/cover.png" />
        <meta property="og:url" content="https://example.com/article" />
        <meta name="twitter:card" content="summary_large_image" />
      </head>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    social = extract_social_meta(soup)
    assert social.og_title == "My Great Article"
    assert social.og_description == "An in-depth guide on SEO"
    assert social.og_image == "https://example.com/cover.png"
    assert social.og_url == "https://example.com/article"
    assert social.twitter_card == "summary_large_image"
    assert len(social.issues) == 0


def test_extract_social_meta_missing():
    html = "<html><head><title>No Social</title></head></html>"
    soup = BeautifulSoup(html, "html.parser")
    social = extract_social_meta(soup)
    assert "Missing og:title" in social.issues
    assert "Missing og:description" in social.issues
    assert "Missing og:image" in social.issues


def test_audit_images_alt_and_dimensions():
    html = """
    <div>
      <img src="/img/valid.png" alt="Valid" width="200" height="100" />
      <img src="/img/missing_alt.jpg" width="150" height="80" />
      <img src="/img/missing_dimensions.webp" alt="Optimized" />
      <img src="/img/both_missing.png" />
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    issues = audit_images(soup, "https://example.com")
    assert len(issues) == 3

    missing_alt_urls = [img.src for img in issues if img.missing_alt]
    assert "https://example.com/img/missing_alt.jpg" in missing_alt_urls
    assert "https://example.com/img/both_missing.png" in missing_alt_urls

    missing_dim_urls = [img.src for img in issues if img.missing_dimensions]
    assert "https://example.com/img/missing_dimensions.webp" in missing_dim_urls


def test_heading_hierarchy_check():
    # Valid hierarchy
    valid_html = """
    <div>
      <h1>Main Title</h1>
      <h2>Sub section 1</h2>
      <h3>Sub sub section</h3>
      <h2>Sub section 2</h2>
    </div>
    """
    valid_soup = BeautifulSoup(valid_html, "html.parser")
    assert check_heading_hierarchy(valid_soup) == []

    # Skipped hierarchy (H1 -> H3)
    skipped_html = """
    <div>
      <h1>Main Title</h1>
      <h3>Skipped H2!</h3>
    </div>
    """
    skipped_soup = BeautifulSoup(skipped_html, "html.parser")
    issues = check_heading_hierarchy(skipped_soup)
    assert len(issues) == 1
    assert "Heading level skipped from H1 to H3" in issues[0]


def test_check_json_ld():
    # Valid JSON-LD
    valid_html = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "SEO Testing"
    }
    </script>
    """
    soup = BeautifulSoup(valid_html, "html.parser")
    has_json, valid = check_json_ld(soup)
    assert has_json is True
    assert valid is True

    # Invalid JSON-LD
    broken_html = '<script type="application/ld+json">{ invalid json syntax </script>'
    soup_broken = BeautifulSoup(broken_html, "html.parser")
    has_json2, valid2 = check_json_ld(soup_broken)
    assert has_json2 is True
    assert valid2 is False

    # No JSON-LD
    empty_soup = BeautifulSoup("<div>Nothing</div>", "html.parser")
    has_json3, valid3 = check_json_ld(empty_soup)
    assert has_json3 is False
    assert valid3 is False


def test_parse_ai_bot_rules():
    robots_content = """
    User-agent: *
    Disallow: /admin

    User-agent: GPTBot
    Disallow: /

    User-agent: ClaudeBot
    Allow: /
    """
    rules = parse_ai_bot_rules(robots_content)
    assert rules["Gptbot"] == "disallowed"
    assert rules["Claudebot"] == "allowed"
    assert rules["Perplexitybot"] == "allowed"
