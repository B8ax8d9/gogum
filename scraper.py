# GoGum - Async Scraper Engine (v2 — with Proxy + Stealth + DoH Bypass)
# Concurrent web scraper with multi-name fallback, proxy rotation, anti-ban, and DoH DNS

import asyncio
import re
import socket
import time
from urllib.parse import quote_plus, urljoin, urlparse

import aiohttp
from aiohttp.resolver import AbstractResolver
from bs4 import BeautifulSoup

from models import Site, SearchResult, SiteSearchResult
from proxy import get_rotator
from stealth import get_stealth


# --- Constants ---
MAX_CONCURRENT = 30
REQUEST_TIMEOUT = 10
MAX_RETRIES = 2
RETRY_DELAY = 0.5
MAX_BODY_SIZE = 10 * 1024 * 1024

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ar,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

# ──────────────────────────────────────────────────────────────────
# DoH (DNS-over-HTTPS) Resolver — Bypasses ISP DNS blocking/censorship
# ──────────────────────────────────────────────────────────────────

_DNS_CACHE: dict[str, list[str]] = {}


async def _resolve_via_doh(host: str) -> list[str]:
    """Resolve a hostname via Cloudflare or Google DoH."""
    if host in _DNS_CACHE:
        return _DNS_CACHE[host]

    # Try Cloudflare DoH
    cf_url = f"https://cloudflare-dns.com/dns-query?name={host}&type=A"
    try:
        timeout = aiohttp.ClientTimeout(total=2)
        async with aiohttp.ClientSession() as session:
            async with session.get(cf_url, headers={"Accept": "application/dns-json"}, timeout=timeout, ssl=False) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1]
                    if ips:
                        _DNS_CACHE[host] = ips
                        return ips
    except Exception:
        pass

    # Fallback to Google DoH
    google_url = f"https://dns.google/resolve?name={host}&type=A"
    try:
        timeout = aiohttp.ClientTimeout(total=2)
        async with aiohttp.ClientSession() as session:
            async with session.get(google_url, timeout=timeout, ssl=False) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1]
                    if ips:
                        _DNS_CACHE[host] = ips
                        return ips
    except Exception:
        pass

    return []


class DoHResolver(AbstractResolver):
    """Custom aiohttp resolver with automatic DoH fallback."""

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET) -> list[dict]:
        # 1. Try standard system DNS first
        try:
            loop = asyncio.get_running_loop()
            infos = await loop.getaddrinfo(host, port, family=family, type=socket.SOCK_STREAM)
            hosts = []
            for fam, typ, proto, cname, sockaddr in infos:
                hosts.append({
                    "hostname": host,
                    "host": sockaddr[0],
                    "port": sockaddr[1],
                    "family": fam,
                    "proto": proto,
                    "flags": socket.AI_NUMERICHOST,
                })
            if hosts:
                return hosts
        except socket.gaierror:
            pass  # Fall back to DoH

        # 2. Fall back to DNS-over-HTTPS
        ips = await _resolve_via_doh(host)
        if ips:
            hosts = []
            for ip in ips:
                hosts.append({
                    "hostname": host,
                    "host": ip,
                    "port": port,
                    "family": socket.AF_INET,
                    "proto": 6,
                    "flags": socket.AI_NUMERICHOST,
                })
            return hosts

        raise socket.gaierror(socket.EAI_NONAME, f"Cannot resolve {host} via DNS or DoH")

    async def close(self) -> None:
        pass


def _build_url(template: str, query: str) -> str:
    return template.replace("{query}", quote_plus(query))


def _clean_title(text: str) -> str:
    """Clean raw scraped title of duration, resolution, quality stamps, percentages, and site branding."""
    text = re.sub(r'[\r\n\t]+', ' ', text)
    # Remove leading duration & resolution (e.g. "17:49", "21:14", "1:23:45", "17:49100%", "39:254K")
    text = re.sub(r'^\s*\d{1,2}:\d{2}(?::\d{2})?(?:\d{1,3}%)?(?:\s*(?:4[Kk]|HD|1080p|720p))?\s*', '', text)
    # Remove percentage ratings (e.g. "100%", "95%")
    text = re.sub(r'^\s*\d{1,3}%\s*', '', text)
    # Remove surrounding quotes and brackets
    text = text.strip(" \t\n\r\"'[]()-–—")
    return text.strip()


STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "with", "by", "from",
    "في", "من", "على", "عن", "مع", "و", "او", "إلى", "الي", "ال"
}

JUNK_TITLES = {
    "latest videos", "longest videos", "random videos", "most viewed", "latest", "longest",
    "random", "discussed", "rating", "top rated", "trending", "popular", "top", "best",
    "de", "it", "en", "fr", "es", "ru", "ar", "pt", "ja", "zh", "nl", "pl", "sv",
    "home", "search", "categories", "tags", "channels", "pornstars", "models", "actors",
    "login", "signup", "register", "dmca", "terms", "privacy", "contact", "about",
    "2257", "community", "blog", "news", "forum", "help", "faq", "upload", "submit",
    "join", "vip", "premium", "full hd", "4k", "hd", "1080p", "720p", "watch", "view",
    "download", "play", "share", "embed", "next", "prev", "previous", "page",
}

THUMB_BLOCKLIST = [
    "logo", "popcorn", "placeholder", "default", "avatar", "flag", "banner",
    "spacer", "pixel", "icon", "blank", "assets/img", "theme", "header",
    "button", "sprite", "badge", "/de.png", "/it.png", "/en.png", "/fr.png",
    "/es.png", "/de.", "/it.", "/fr.", "/es.", "/ru.", "thotflix-logo",
    "site-logo", "favicon", "data:image", "40x40", "48x48", "32x32", "16x16",
    "cropped-cropped", "vpnanon",
]


def _is_strict_match(query: str, title: str, link: str) -> bool:
    """
    Ensure the result matches the query accurately:
    - For 1-2 words (e.g. Actor names): Requires ALL words to be present.
    - For 3+ words (e.g. Movie titles/long titles): Filters stop words and requires >= 70% match or substring match.
    """
    clean_text = (title + " " + link.replace("-", " ").replace("/", " ").replace("_", " ")).lower()
    raw_words = [w.lower() for w in re.findall(r'[\w\u0600-\u06FF]+', query) if len(w) >= 2]
    
    if not raw_words:
        return True

    # Check direct phrase match
    query_clean = " ".join(raw_words)
    if query_clean in clean_text:
        return True

    # Filter out common stop words if we have enough words
    sig_words = [w for w in raw_words if w not in STOP_WORDS] if len(raw_words) >= 3 else raw_words
    if not sig_words:
        sig_words = raw_words

    if len(sig_words) <= 2:
        return all(w in clean_text for w in sig_words)
    
    # For long titles: count matched significant words (at least 70%)
    matches = sum(1 for w in sig_words if w in clean_text)
    match_ratio = matches / len(sig_words)
    return match_ratio >= 0.7


def _extract_thumb(el, base_url: str) -> str:
    """Extract real video/media thumbnail image URL from element or nearby parent/siblings."""
    targets = [el]
    curr = el
    for _ in range(4):
        if curr.parent:
            curr = curr.parent
            targets.append(curr)
        else:
            break

    # 1. Look for direct container data attributes (used by Slutvids, W11, Pornx, Hornyleak)
    for target in targets:
        for attr in ["data-main-thumb", "data-preview", "data-thumb", "data-thumbnail", "data-poster", "data-src", "data-original", "data-lazy-src", "data-webp", "data-img", "data-full"]:
            val = target.get(attr, "").strip() if hasattr(target, "get") else ""
            if val and not any(bad in val.lower() for bad in THUMB_BLOCKLIST):
                if val.startswith("//"): return "https:" + val
                elif not val.startswith("http"): return urljoin(base_url, val)
                return val

    # 2. Look for img tags with valid video thumbnail sources
    for target in targets:
        for img in target.find_all("img"):
            for attr in ["data-main-thumb", "data-preview", "data-src", "data-original", "data-lazy-src", "data-thumb", "data-thumbnail", "data-poster", "data-webp", "data-img", "src"]:
                src = img.get(attr, "").strip()
                if src and not any(bad in src.lower() for bad in THUMB_BLOCKLIST):
                    if src.startswith("//"): return "https:" + src
                    elif not src.startswith("http"): return urljoin(base_url, src)
                    return src

    # 3. Check CSS background-image
    for target in targets:
        style = target.get("style", "") if hasattr(target, "get") else ""
        m = re.search(r'background(?:-image)?\s*:\s*url\([\'\"]?(https?://[^\'\"\)]+)[\'\"]?\)', style, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if not any(bad in val.lower() for bad in THUMB_BLOCKLIST):
                return val

    # 4. Check video poster
    for target in targets:
        video = target.find("video")
        if video and video.get("poster"):
            poster = video.get("poster", "").strip()
            if poster and not any(bad in poster.lower() for bad in THUMB_BLOCKLIST):
                if poster.startswith("//"): return "https:" + poster
                elif not poster.startswith("http"): return urljoin(base_url, poster)
                return poster

    return ""


def _parse_html(html: str, site: Site, query: str) -> list[SearchResult]:
    soup = BeautifulSoup(html, "lxml")
    results: list[SearchResult] = []
    seen_links = set()
    elements = soup.select(site.selector)
    if not elements:
        return results

    # Ignored link segments (categories, tags, auth, filter menus, language paths)
    ignored_path_patterns = [
        "/category/", "/categories/", "/tag/", "/tags/", "/page/", "/login",
        "/signup", "/upgrade", "/membership", "filter=", "order=", "sort=",
        "/de/search", "/it/search", "/fr/search", "/es/search", "/ru/search",
    ]

    for el in elements:
        # Check for clean title inside specific title span/heading if available
        title = ""
        title_el = el.select_one("[class*='title'], [class*='name'], [class*='heading'], h2, h3, h4")
        if title_el:
            title = title_el.get_text(strip=True)

        if not title:
            # Check img alt attribute if element contains an image
            img = el.find("img")
            if img and img.get("alt"):
                title = img.get("alt", "").strip()

        if not title:
            title = el.get_text(strip=True)

        title = _clean_title(title)
        if not title:
            continue

        # Skip junk titles (filters, menus, language codes, short strings)
        if title.lower() in JUNK_TITLES or len(title) <= 2:
            continue
        if re.match(r'^\s*(\d{1,3}%|\d{1,2}:\d{2})\s*$', title):
            continue

        file_name = ""
        link = ""

        # --- Extract file name ---
        if site.file_selector:
            container = el
            for _ in range(8):
                parent = container.parent
                if parent is None:
                    break
                container = parent
                tag = container.name or ""
                classes = " ".join(container.get("class", []))
                if tag in ("tr", "li", "article", "section") or any(
                    kw in classes for kw in ("item", "post", "card", "entry", "movie", "result", "row")
                ):
                    break
            file_el = container.select_one(site.file_selector)
            if file_el:
                file_name = file_el.get_text(strip=True)

        # --- Extract link ---
        if site.link_selector:
            container = el
            for _ in range(8):
                parent = container.parent
                if parent is None:
                    break
                container = parent
                tag = container.name or ""
                classes = " ".join(container.get("class", []))
                if tag in ("tr", "li", "article", "section") or any(
                    kw in classes for kw in ("item", "post", "card", "entry", "movie", "result", "row")
                ):
                    break
            link_el = container.select_one(site.link_selector)
            if link_el:
                link = link_el.get("href", "")
        else:
            if el.name == "a":
                link = el.get("href", "")
            elif el.find_parent("a"):
                link = el.find_parent("a").get("href", "")
            else:
                a_tag = el.find("a")
                if a_tag:
                    link = a_tag.get("href", "")

        # Make relative links absolute
        if link and not link.startswith(("http://", "https://")):
            base = site.search_url.split("//")[0] + "//" + site.search_url.split("//")[1].split("/")[0]
            link = urljoin(base, link)

        # Filter out navigation / category / filter links
        if link:
            link_lower = link.lower()
            if any(p in link_lower for p in ignored_path_patterns):
                continue
            if link in seen_links:
                continue
            seen_links.add(link)

        # Strict Matching: Ensure result matches the specific queried actress/actor
        if not _is_strict_match(query, title, link):
            continue

        # Extract Thumbnail / Poster Preview
        base_url = site.search_url.split("//")[0] + "//" + site.search_url.split("//")[1].split("/")[0]
        thumb_url = _extract_thumb(el, base_url)

        results.append(SearchResult(
            site_name=site.name,
            title=title,
            file_name=file_name,
            link=link,
            query_used=query,
            thumb_url=thumb_url,
        ))

    return results


async def _fetch_page(
    session: aiohttp.ClientSession, url: str, site_headers: dict,
    proxy_url: str | None = None, stealth_headers: dict | None = None,
) -> tuple[str, int]:
    """
    Fetch a page with full stealth + proxy support.
    Returns (html_body, status_code).
    """
    merged = {**(stealth_headers or DEFAULT_HEADERS), **site_headers}
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    kwargs = {
        "headers": merged,
        "timeout": timeout,
        "ssl": False,
        "allow_redirects": True,
        "max_redirects": 5,
    }

    if proxy_url and not any(p in proxy_url for p in ("socks4://", "socks5://")):
        kwargs["proxy"] = proxy_url

    async with session.get(url, **kwargs) as resp:
        body = await resp.read()
        if len(body) > MAX_BODY_SIZE:
            raise ValueError("Response too large")
        encoding = resp.charset or "utf-8"
        try:
            text = body.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            text = body.decode("utf-8", errors="replace")
        return text, resp.status


async def _search_site_single_name(
    session: aiohttp.ClientSession, site: Site, name: str,
    proxy_url: str | None, stealth_headers: dict | None,
) -> list[SearchResult]:
    """Search a single site with a single name, with retry and anti-ban."""
    url = _build_url(site.search_url, name)
    domain = urlparse(url).netloc
    stealth = get_stealth()
    rotator = get_rotator()
    last_err = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            if attempt > 0:
                await stealth.apply_backoff(domain)
                if rotator.enabled:
                    proxy_url = rotator.get_proxy_url(domain)
                    stealth_headers = stealth.get_headers(domain)

            await stealth.rate_limit(domain)

            start = time.time()
            html, status = await _fetch_page(session, url, site.headers, proxy_url, stealth_headers)
            elapsed_ms = (time.time() - start) * 1000

            if stealth.is_banned_response(status, html):
                if proxy_url and rotator.enabled:
                    rotator.report_ban(proxy_url, domain)
                    rotator.report_failure(proxy_url, f"BAN {status}", domain)
                raise aiohttp.ClientResponseError(
                    aiohttp.RequestInfo(url=url, method="GET", headers={}, real_url=url),
                    (), status=status, message=f"Banned/Blocked (HTTP {status})",
                )

            if status != 200:
                raise aiohttp.ClientResponseError(
                    aiohttp.RequestInfo(url=url, method="GET", headers={}, real_url=url),
                    (), status=status, message=f"HTTP {status}",
                )

            stealth.reset_backoff(domain)
            if proxy_url and rotator.enabled:
                rotator.report_success(proxy_url, elapsed_ms)

            return _parse_html(html, site, name)

        except Exception as e:
            last_err = e
            if proxy_url and rotator.enabled:
                rotator.report_failure(proxy_url, str(e), domain)

    return []


async def _search_site_multi_name(
    session: aiohttp.ClientSession,
    site: Site,
    names: list[str],
    semaphore: asyncio.Semaphore,
    progress_callback=None,
    index: int = 0,
    total: int = 0,
) -> SiteSearchResult:
    """Search a site with multiple name variations (fallback) + stealth + proxy."""
    async with semaphore:
        result = SiteSearchResult(site=site)
        stealth = get_stealth()
        rotator = get_rotator()
        domain = urlparse(site.search_url).netloc

        proxy_url = rotator.get_proxy_url(domain) if rotator.enabled else None
        stealth_headers = stealth.get_headers(domain)

        for name in names:
            if stealth.is_domain_banned(domain) or stealth.is_rate_limited(domain):
                result.error = "Domain rate-limited or banned"
                result.status = "error"
                break

            try:
                found = await _search_site_single_name(
                    session, site, name, proxy_url, stealth_headers
                )
                if found:
                    result.results = found
                    result.query_used = name
                    result.status = "success"
                    break
            except Exception as e:
                result.error = str(e)

        if result.results:
            result.status = "success"
        elif not result.error:
            result.status = "success"
            result.query_used = names[0] if names else ""

        if progress_callback:
            progress_callback(index + 1, total, site.name, result.status)

        return result


def _decode_search_url(url: str) -> str:
    """Decode tracking URLs (e.g. Bing u=a1... or DDG uddg=) to direct URLs."""
    import base64
    from urllib.parse import parse_qs, unquote
    if "u=" in url:
        try:
            qs = parse_qs(urlparse(url).query)
            if "u" in qs:
                raw = qs["u"][0]
                if raw.startswith("a1"):
                    b64 = raw[2:]
                    padded = b64 + "=" * ((4 - len(b64) % 4) % 4)
                    return base64.b64decode(padded).decode("utf-8", errors="ignore")
        except Exception:
            pass
    if "uddg=" in url:
        try:
            qs = parse_qs(urlparse(url).query)
            if "uddg" in qs:
                return unquote(qs["uddg"][0])
        except Exception:
            pass
    return url


async def _search_google_web(
    session: aiohttp.ClientSession,
    names: list[str],
    semaphore: asyncio.Semaphore,
) -> SiteSearchResult:
    """
    Search Google & Global Web Search Engines across the entire web,
    extracting clean titles, direct links, and media entries.
    """
    google_site = Site(
        name="Google & Web Search",
        search_url="https://www.google.com/search?q={query}",
        selector="a",
        file_selector="",
        link_selector="",
        enabled=True,
    )
    res = SiteSearchResult(site=google_site, query_used=names[0] if names else "")
    found_results: list[SearchResult] = []
    seen_links: set[str] = set()

    for name in names:
        # Search multiple pages across web search engines
        for page in range(3):
            first = (page * 10) + 1
            search_url = f"https://www.bing.com/search?q={quote_plus(name)}&first={first}"
            try:
                timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                headers = {
                    "User-Agent": DEFAULT_HEADERS["User-Agent"],
                    "Accept-Language": "en-US,en;q=0.9",
                }
                async with session.get(search_url, headers=headers, timeout=timeout, ssl=False) as resp:
                    if resp.status == 200:
                        html = await resp.text(errors="replace")
                        soup = BeautifulSoup(html, "lxml")
                        for li in soup.select("li.b_algo"):
                            a = li.select_one("h2 a")
                            if a and a.get("href"):
                                title = a.get_text(strip=True)
                                link = _decode_search_url(a["href"])
                                if link.startswith("http") and link not in seen_links and not any(x in link for x in ["bing.com", "microsoft.com"]):
                                    seen_links.add(link)
                                    found_results.append(SearchResult(
                                        site_name="Google & Web Search",
                                        title=title,
                                        link=link,
                                        query_used=name,
                                    ))
            except Exception:
                pass

    if found_results:
        res.results = found_results
        res.status = "success"
    else:
        res.status = "success"

    return res


async def search_all(
    sites: list[Site],
    names: list[str],
    include_google: bool = False,
    progress_callback=None,
) -> list[SiteSearchResult]:
    """Search sites concurrently with DoH + proxy + stealth. include_google controls whether web search is added."""
    if not names:
        return []

    stealth = get_stealth()
    rotator = get_rotator()

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    resolver = DoHResolver()
    connector = aiohttp.TCPConnector(
        resolver=resolver,
        limit=MAX_CONCURRENT,
        limit_per_host=5,
        ssl=False,
        force_close=False,
        enable_cleanup_closed=True,
    )

    if rotator.enabled:
        sample = rotator.get_next()
        if sample and sample.is_socks:
            try:
                from aiohttp_socks import ProxyConnector
                connector = ProxyConnector.from_url(
                    sample.url, limit=MAX_CONCURRENT, ssl=False
                )
            except ImportError:
                pass

    async with aiohttp.ClientSession(connector=connector) as session:
        site_tasks = [
            _search_site_multi_name(
                session, site, names, semaphore,
                progress_callback, i, len(sites),
            )
            for i, site in enumerate(sites)
        ]
        
        if include_google:
            tasks = [_search_google_web(session, names, semaphore)] + site_tasks
            all_sites = [
                Site(name="Google & Web Search", search_url="https://www.google.com/search?q={query}", selector="a")
            ] + sites
        else:
            tasks = site_tasks
            all_sites = sites

        results = await asyncio.gather(*tasks, return_exceptions=True)

    final: list[SiteSearchResult] = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            site_obj = all_sites[i] if i < len(all_sites) else sites[0]
            final.append(SiteSearchResult(site=site_obj, error=str(r), status="error"))
        else:
            final.append(r)

    return final


def run_search(
    sites: list[Site],
    names: list[str],
    include_google: bool = False,
    progress_callback=None,
) -> list[SiteSearchResult]:
    """Synchronous wrapper for search_all."""
    return asyncio.run(search_all(sites, names, include_google=include_google, progress_callback=progress_callback))

