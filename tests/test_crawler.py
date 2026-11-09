"""Unit and integration tests for async crawler and broken links checker."""

import httpx
import pytest

from seo_audit.crawler import crawl_site, is_private_or_local_host


def test_is_private_or_local_host():
    assert is_private_or_local_host("localhost") is True
    assert is_private_or_local_host("127.0.0.1") is True
    assert is_private_or_local_host("10.0.0.1") is True
    assert is_private_or_local_host("192.168.1.1") is True
    assert is_private_or_local_host("example.com") is False


@pytest.mark.asyncio
async def test_crawl_site_with_mock_transport():
    # Setup mock responses for a small website
    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)

        if url_str == "https://testsite.com/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /admin\nSitemap: https://testsite.com/sitemap.xml",
            )
        if url_str == "https://testsite.com/sitemap.xml":
            return httpx.Response(
                200,
                text="""<?xml version="1.0" encoding="UTF-8"?>
                <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                  <url><loc>https://testsite.com/</loc></url>
                  <url><loc>https://testsite.com/about</loc></url>
                </urlset>""",
            )
        if url_str in ("https://testsite.com/", "https://testsite.com"):
            html = """
            <!DOCTYPE html>
            <html>
              <head>
                <title>Testsite Homepage - Welcome to our website</title>
                <meta name="description" content="This is an informative test description exceeding seventy characters length easily." />
                <link rel="canonical" href="https://testsite.com/" />
              </head>
              <body>
                <h1>Homepage Title</h1>
                <h2>Subheading</h2>
                <a href="/about">About Us</a>
                <a href="/broken-internal">Broken Page</a>
                <a href="https://external-broken.com/dead">Dead Link</a>
              </body>
            </html>
            """
            return httpx.Response(200, text=html, headers={"content-type": "text/html"})
        if url_str == "https://testsite.com/about":
            html = """
            <!DOCTYPE html>
            <html>
              <head>
                <title>About Us Page Title - Testsite Company Info</title>
                <meta name="description" content="Learn more about our great team and company mission right here on our about page." />
                <link rel="canonical" href="https://testsite.com/about" />
              </head>
              <body>
                <h1>About Us</h1>
                <h2>History</h2>
                <a href="/">Home</a>
              </body>
            </html>
            """
            return httpx.Response(200, text=html, headers={"content-type": "text/html"})
        if url_str in ("https://testsite.com/broken-internal", "https://external-broken.com/dead"):
            return httpx.Response(404, text="Not Found")
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        report = await crawl_site(
            start_url="https://testsite.com/",
            max_pages=10,
            max_external_links=10,
            allow_private_network=True,
            client=client,
        )

        assert report.target_url == "https://testsite.com/"
        assert report.site_meta.robots_found is True
        assert report.site_meta.sitemap_found is True
        assert len(report.pages) >= 2
        assert len(report.broken_links) >= 1

        broken_targets = {bl.target_url for bl in report.broken_links}
        assert (
            "https://external-broken.com/dead" in broken_targets
            or "https://testsite.com/broken-internal" in broken_targets
        )
