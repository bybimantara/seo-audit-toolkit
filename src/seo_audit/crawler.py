"""Async website crawler, SSRF validator, and broken link checker."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from collections import deque
from urllib.parse import urldefrag, urlparse

import httpx

from seo_audit.analyzer import (
    analyze_page_html,
    is_same_site,
    parse_robots_txt,
    parse_sitemap_xml,
)
from seo_audit.models import BrokenLink, PageAudit, SiteAuditReport, SiteMetaResult

DEFAULT_USER_AGENT = "SEOAuditToolkit/0.1 (+https://github.com/bybimantara/seo-audit-toolkit)"


def is_private_or_local_host(hostname: str) -> bool:
    """Validate if hostname points to localhost or private/link-local/loopback IP."""
    if not hostname:
        return True
    host_clean = hostname.split(":")[0].strip().lower()
    if host_clean in ("localhost", "127.0.0.1", "::1"):
        return True
    try:
        ip = ipaddress.ip_address(host_clean)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
        )
    except ValueError:
        # Hostname, not direct IP. Try DNS resolution
        try:
            addr_info = socket.getaddrinfo(host_clean, None)
            for item in addr_info:
                ip_str = item[4][0]
                resolved_ip = ipaddress.ip_address(ip_str)
                if (
                    resolved_ip.is_private
                    or resolved_ip.is_loopback
                    or resolved_ip.is_link_local
                    or resolved_ip.is_multicast
                    or resolved_ip.is_reserved
                ):
                    return True
        except (socket.gaierror, OSError):
            return False
    return False


async def check_single_link(
    client: httpx.AsyncClient,
    target_url: str,
    semaphore: asyncio.Semaphore,
) -> tuple[int | None, str, bool]:
    """Check target URL status using HEAD first, then GET fallback if restricted.

    Returns (status_code, error_msg, is_broken).
    """
    async with semaphore:
        try:
            resp = await client.head(target_url, timeout=10.0, follow_redirects=True)
            status = resp.status_code

            # Some servers reject HEAD with 403, 405, or 501. Try lightweight GET
            if status in (403, 405, 501):
                try:
                    resp_get = await client.get(
                        target_url, timeout=10.0, follow_redirects=True
                    )
                    status = resp_get.status_code
                except (httpx.RequestError, OSError):
                    pass

            # Distinguish broken (404, 410, 5xx) from restricted/bot-blocked (403, 429, 999)
            if status in (404, 410) or status >= 500:
                return status, f"HTTP {status}", True
            if status in (403, 429, 999):
                return status, f"Blocked/Restricted ({status})", False
            return status, "", False

        except httpx.TimeoutException:
            return None, "Timeout", True
        except (httpx.ConnectError, httpx.RequestError) as err:
            return None, f"Connection error: {err.__class__.__name__}", True
        except Exception as err:  # noqa: BLE001
            return None, f"Error: {err.__class__.__name__}", True


async def check_site_meta(
    client: httpx.AsyncClient,
    base_url: str,
) -> SiteMetaResult:
    """Check robots.txt and sitemap.xml on the target domain."""
    result = SiteMetaResult()
    parsed_base = urlparse(base_url)
    origin = f"{parsed_base.scheme}://{parsed_base.netloc}"

    # 1. Check robots.txt
    robots_url = f"{origin}/robots.txt"
    result.robots_url = robots_url
    try:
        r_resp = await client.get(robots_url, timeout=10.0, follow_redirects=True)
        result.robots_status = r_resp.status_code
        if r_resp.status_code == 200:
            result.robots_found = True
            sitemaps, issues = parse_robots_txt(r_resp.text, robots_url)
            result.sitemaps_in_robots = sitemaps
            result.issues.extend(issues)
        else:
            result.issues.append(f"robots.txt returned HTTP {r_resp.status_code}")
    except (httpx.RequestError, OSError) as err:
        result.issues.append(f"Failed to fetch robots.txt ({err.__class__.__name__})")

    # 2. Determine and check sitemap.xml
    candidate_sitemap = (
        result.sitemaps_in_robots[0]
        if result.sitemaps_in_robots
        else f"{origin}/sitemap.xml"
    )
    result.sitemap_url = candidate_sitemap
    try:
        s_resp = await client.get(candidate_sitemap, timeout=10.0, follow_redirects=True)
        result.sitemap_status = s_resp.status_code
        if s_resp.status_code == 200:
            result.sitemap_found = True
            valid_xml, is_index, urls = parse_sitemap_xml(s_resp.text)
            result.sitemap_valid_xml = valid_xml
            result.sitemap_is_index = is_index
            result.sitemap_url_count = len(urls)
            if not valid_xml:
                result.issues.append("sitemap.xml is not valid XML")
        else:
            result.issues.append(f"sitemap.xml returned HTTP {s_resp.status_code}")
    except (httpx.RequestError, OSError) as err:
        result.issues.append(f"Failed to fetch sitemap.xml ({err.__class__.__name__})")

    return result


async def crawl_site(
    start_url: str,
    max_pages: int = 50,
    max_external_links: int = 100,
    concurrency: int = 10,
    timeout: float = 10.0,
    allow_private_network: bool = False,
    client: httpx.AsyncClient | None = None,
) -> SiteAuditReport:
    """Async BFS full-site crawl with broken link detection and report aggregation."""
    start_time = time.perf_counter()

    parsed = urlparse(start_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid URL: {start_url}. Must include http:// or https://")

    if not allow_private_network and is_private_or_local_host(parsed.netloc):
        raise ValueError(
            f"Access to private/local network address '{parsed.netloc}' is forbidden."
        )

    clean_start, _ = urldefrag(start_url)

    # Use provided client or create one
    close_client = False
    if client is None:
        client = httpx.AsyncClient(
            headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
        )
        close_client = True

    try:
        # Step 1: Check site metadata (robots.txt & sitemap.xml)
        site_meta = await check_site_meta(client, clean_start)

        # Step 2: BFS crawl for internal pages
        pages_audit: list[PageAudit] = []
        visited_urls: set[str] = set()
        queue: deque[str] = deque([clean_start])

        # Also queue URLs from sitemap if same site and not too many
        if site_meta.sitemap_found and site_meta.sitemap_valid_xml:
            try:
                s_resp = await client.get(
                    site_meta.sitemap_url, timeout=timeout, follow_redirects=True
                )
                if s_resp.status_code == 200:
                    _, _, s_urls = parse_sitemap_xml(s_resp.text)
                    for u in s_urls:
                        if is_same_site(u, clean_start):
                            clean_u, _ = urldefrag(u)
                            if clean_u not in queue and clean_u not in visited_urls:
                                queue.append(clean_u)
            except (httpx.RequestError, OSError):
                pass

        semaphore = asyncio.Semaphore(concurrency)

        while queue and len(visited_urls) < max_pages:
            current_url = queue.popleft()
            if current_url in visited_urls:
                continue
            visited_urls.add(current_url)

            # Fetch page
            page_start = time.perf_counter()
            initial_status = None
            final_status = None
            final_url = current_url
            html_text = ""
            content_type = ""

            try:
                async with semaphore:
                    # Non-redirect first to capture initial status
                    resp_initial = await client.get(
                        current_url, timeout=timeout, follow_redirects=False
                    )
                    initial_status = resp_initial.status_code

                    if resp_initial.is_redirect:
                        resp_final = await client.get(
                            current_url, timeout=timeout, follow_redirects=True
                        )
                        final_status = resp_final.status_code
                        final_url = str(resp_final.url)
                        html_text = resp_final.text
                        content_type = resp_final.headers.get("content-type", "")
                    else:
                        final_status = initial_status
                        final_url = str(resp_initial.url)
                        html_text = resp_initial.text
                        content_type = resp_initial.headers.get("content-type", "")

            except (httpx.RequestError, OSError):
                final_status = None
                initial_status = None

            duration_ms = (time.perf_counter() - page_start) * 1000

            if html_text and "text/html" in content_type:
                audit = analyze_page_html(
                    html=html_text,
                    requested_url=current_url,
                    final_url=final_url,
                    status_code=final_status,
                    initial_status_code=initial_status,
                    response_time_ms=duration_ms,
                    content_type=content_type,
                )
                # Enqueue new internal links found
                for link_url, _ in audit.internal_links:
                    if (
                        link_url not in visited_urls
                        and link_url not in queue
                        and len(visited_urls) + len(queue) < max_pages * 2
                    ):
                        queue.append(link_url)
            else:
                issues = []
                if final_status is None:
                    issues.append("Failed to connect or request timed out")
                elif final_status >= 400:
                    issues.append(f"Page returned HTTP error {final_status}")
                audit = PageAudit(
                    url=current_url,
                    final_url=final_url,
                    initial_status_code=initial_status,
                    status_code=final_status,
                    response_time_ms=duration_ms,
                    content_type=content_type,
                    issues=issues,
                    page_score=0 if final_status is None or final_status >= 400 else 100,
                )

            pages_audit.append(audit)

        # Step 3: Deduplicate and check broken links
        link_occurrences: dict[str, list[tuple[str, str, bool]]] = {}
        for page in pages_audit:
            for i_url, i_anchor in page.internal_links:
                link_occurrences.setdefault(i_url, []).append((page.url, i_anchor, False))
            for e_url, e_anchor in page.external_links:
                link_occurrences.setdefault(e_url, []).append((page.url, e_anchor, True))

        already_healthy_internal = {
            p.url: p.status_code for p in pages_audit if p.status_code and p.status_code < 400
        }

        urls_to_check: list[tuple[str, bool]] = []
        ext_count = 0
        for target, occs in link_occurrences.items():
            is_ext = occs[0][2]
            if is_ext:
                if ext_count < max_external_links:
                    urls_to_check.append((target, True))
                    ext_count += 1
            elif target not in already_healthy_internal:
                urls_to_check.append((target, False))

        async def _probe(target: str, is_ext: bool):
            st, err, broken = await check_single_link(client, target, semaphore)
            return target, is_ext, st, err, broken

        probe_tasks = [_probe(t, ext) for t, ext in urls_to_check]
        probe_results = await asyncio.gather(*probe_tasks)

        all_broken_links: list[BrokenLink] = []
        broken_target_map: dict[str, tuple[int | None, str]] = {}

        for target, _is_ext, status, err, broken in probe_results:
            if broken:
                broken_target_map[target] = (status, err)

        # Check internal pages that returned >= 400 during crawl
        for p in pages_audit:
            if p.status_code and p.status_code >= 400:
                broken_target_map[p.url] = (p.status_code, f"HTTP {p.status_code}")

        # Map broken links back to source pages
        for target, (status, err) in broken_target_map.items():
            for src_url, anchor, is_ext in link_occurrences.get(target, []):
                bl = BrokenLink(
                    source_url=src_url,
                    target_url=target,
                    anchor_text=anchor,
                    is_external=is_ext,
                    status_code=status,
                    error=err,
                )
                all_broken_links.append(bl)
                for p in pages_audit:
                    if p.url == src_url:
                        p.broken_links.append(bl)

        # Step 4: Calculate overall site health score (0-100)
        avg_page_score = (
            sum(p.page_score for p in pages_audit) / len(pages_audit)
            if pages_audit
            else 0
        )
        health_score = int(avg_page_score)

        if not site_meta.robots_found:
            health_score -= 5
        if not site_meta.sitemap_found or not site_meta.sitemap_valid_xml:
            health_score -= 5

        # Penalty for unique broken links (-3 per broken link, max -20)
        unique_broken_count = len(broken_target_map)
        broken_penalty = min(20, unique_broken_count * 3)
        health_score -= broken_penalty
        health_score = max(0, min(100, health_score))

        total_duration = time.perf_counter() - start_time

        return SiteAuditReport(
            target_url=clean_start,
            max_pages=max_pages,
            duration_seconds=round(total_duration, 2),
            health_score=health_score,
            site_meta=site_meta,
            pages=pages_audit,
            broken_links=all_broken_links,
        )

    finally:
        if close_client:
            await client.aclose()
