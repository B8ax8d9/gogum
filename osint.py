# GoGum - OSINT Engine
# Deep intelligence gathering: dorking, deep crawl, enrichment, cross-reference

import asyncio
import re
from urllib.parse import quote_plus, urljoin, urlparse
from dataclasses import dataclass, field

import aiohttp
from bs4 import BeautifulSoup

from models import Site, SearchResult, SiteSearchResult
from scraper import DEFAULT_HEADERS, MAX_CONCURRENT, REQUEST_TIMEOUT


# ──────────────────────────────────────────────────────────────────
# OSINT Data Models
# ──────────────────────────────────────────────────────────────────

@dataclass
class EnrichedResult:
    """A search result enriched with OSINT metadata."""
    site_name: str
    title: str
    file_name: str = ""
    link: str = ""
    query_used: str = ""
    # OSINT enrichment fields
    year: str = ""
    quality: str = ""           # 1080p, 720p, 4K, etc.
    media_type: str = ""        # movie, series, episode, etc.
    language: str = ""
    file_size: str = ""
    codec: str = ""             # x264, x265, HEVC, etc.
    source_type: str = ""       # BluRay, WEB-DL, HDRip, etc.
    deep_info: dict = field(default_factory=dict)  # Extra info from deep scan


@dataclass
class DorkResult:
    """Result from a search engine dork."""
    engine: str          # duckduckgo, bing, etc.
    site_name: str       # Which registered site it was found on
    title: str
    link: str
    snippet: str = ""


@dataclass
class OSINTReport:
    """Complete OSINT report for an actor search."""
    names: list[str] = field(default_factory=list)
    surface_results: list[SiteSearchResult] = field(default_factory=list)
    enriched_results: list[EnrichedResult] = field(default_factory=list)
    dork_results: list[DorkResult] = field(default_factory=list)
    deep_results: list[EnrichedResult] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────
# Data Enrichment — Extract metadata from titles/filenames
# ──────────────────────────────────────────────────────────────────

# Patterns for metadata extraction
YEAR_PATTERN = re.compile(r'[\(\[\. ]((?:19|20)\d{2})[\)\]\. ]')
QUALITY_PATTERNS = [
    (re.compile(r'4[Kk]|2160[pP]', re.IGNORECASE), "4K"),
    (re.compile(r'1080[pPiI]', re.IGNORECASE), "1080p"),
    (re.compile(r'720[pPiI]', re.IGNORECASE), "720p"),
    (re.compile(r'480[pPiI]', re.IGNORECASE), "480p"),
    (re.compile(r'360[pP]', re.IGNORECASE), "360p"),
]
CODEC_PATTERNS = [
    (re.compile(r'[xX]\.?265|HEVC|H\.?265', re.IGNORECASE), "x265/HEVC"),
    (re.compile(r'[xX]\.?264|H\.?264|AVC', re.IGNORECASE), "x264/AVC"),
    (re.compile(r'AV1', re.IGNORECASE), "AV1"),
    (re.compile(r'VP9', re.IGNORECASE), "VP9"),
]
SOURCE_PATTERNS = [
    (re.compile(r'BluRay|BDRip|BRRip', re.IGNORECASE), "BluRay"),
    (re.compile(r'WEB-?DL|WEB\.?DL', re.IGNORECASE), "WEB-DL"),
    (re.compile(r'WEB-?Rip|WEB\.?Rip', re.IGNORECASE), "WEBRip"),
    (re.compile(r'HDRip', re.IGNORECASE), "HDRip"),
    (re.compile(r'DVDRip|DVD-?R', re.IGNORECASE), "DVDRip"),
    (re.compile(r'HDTV|PDTV', re.IGNORECASE), "HDTV"),
    (re.compile(r'CAM|HDCAM|TS|TELESYNC', re.IGNORECASE), "CAM/TS"),
]
TYPE_PATTERNS = [
    (re.compile(r'S\d{1,2}E\d{1,2}|Season|الموسم|الحلقة|Episode', re.IGNORECASE), "series"),
    (re.compile(r'Complete.?Series|مسلسل|Series|سلسلة', re.IGNORECASE), "series"),
    (re.compile(r'فيلم|Movie|Film', re.IGNORECASE), "movie"),
    (re.compile(r'وثائقي|Documentary', re.IGNORECASE), "documentary"),
    (re.compile(r'أنمي|Anime', re.IGNORECASE), "anime"),
]
SIZE_PATTERN = re.compile(r'(\d+(?:\.\d+)?\s*(?:GB|MB|TB|gb|mb|tb))', re.IGNORECASE)
LANG_PATTERNS = [
    (re.compile(r'مترجم|Arabic\.?Sub|عربي', re.IGNORECASE), "Arabic Sub"),
    (re.compile(r'مدبلج|Arabic\.?Dub|دبلجة', re.IGNORECASE), "Arabic Dub"),
    (re.compile(r'English|ENG', re.IGNORECASE), "English"),
    (re.compile(r'Multi', re.IGNORECASE), "Multi"),
]


def enrich_result(result: SearchResult) -> EnrichedResult:
    """Extract metadata from a search result's title and filename."""
    enriched = EnrichedResult(
        site_name=result.site_name,
        title=result.title,
        file_name=result.file_name,
        link=result.link,
        query_used=result.query_used,
    )

    text = f"{result.title} {result.file_name}"

    # Year
    m = YEAR_PATTERN.search(text)
    if m:
        enriched.year = m.group(1)

    # Quality
    for pattern, label in QUALITY_PATTERNS:
        if pattern.search(text):
            enriched.quality = label
            break

    # Codec
    for pattern, label in CODEC_PATTERNS:
        if pattern.search(text):
            enriched.codec = label
            break

    # Source type
    for pattern, label in SOURCE_PATTERNS:
        if pattern.search(text):
            enriched.source_type = label
            break

    # Media type
    for pattern, label in TYPE_PATTERNS:
        if pattern.search(text):
            enriched.media_type = label
            break
    if not enriched.media_type:
        enriched.media_type = "movie"  # default

    # File size
    m = SIZE_PATTERN.search(text)
    if m:
        enriched.file_size = m.group(1)

    # Language
    for pattern, label in LANG_PATTERNS:
        if pattern.search(text):
            enriched.language = label
            break

    return enriched


def enrich_all(results: list[SiteSearchResult]) -> list[EnrichedResult]:
    """Enrich all search results with metadata."""
    enriched = []
    for sr in results:
        for r in sr.results:
            enriched.append(enrich_result(r))
    return enriched


# ──────────────────────────────────────────────────────────────────
# Deep Scan — Follow links and extract detailed page info
# ──────────────────────────────────────────────────────────────────

MAX_DEEP_PER_SITE = 10  # Max pages to deep-scan per site
DEEP_TIMEOUT = 12


async def _deep_scan_page(
    session: aiohttp.ClientSession, result: EnrichedResult
) -> EnrichedResult:
    """Deep scan a single result page to extract more info."""
    if not result.link or not result.link.startswith("http"):
        return result

    try:
        timeout = aiohttp.ClientTimeout(total=DEEP_TIMEOUT)
        async with session.get(
            result.link, headers=DEFAULT_HEADERS, timeout=timeout,
            ssl=False, allow_redirects=True
        ) as resp:
            if resp.status != 200:
                return result

            html = await resp.text(errors="replace")
            soup = BeautifulSoup(html, "lxml")

            deep = {}

            # Extract page title
            page_title = soup.select_one("h1, .entry-title, .post-title, title")
            if page_title:
                deep["page_title"] = page_title.get_text(strip=True)

            # Find all download/file links
            file_links = []
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                text = a.get_text(strip=True)
                if any(ext in href.lower() for ext in [".mkv", ".mp4", ".avi", ".srt", ".zip", ".rar"]):
                    file_links.append({"text": text, "href": href})
                elif any(kw in text.lower() for kw in ["download", "تحميل", "direct", "مباشر", "link"]):
                    file_links.append({"text": text, "href": href})

            if file_links:
                deep["file_links"] = file_links[:20]

            # Find file names in the page content
            page_text = soup.get_text()
            file_names = re.findall(
                r'[\w\.\-]+\.(?:mkv|mp4|avi|srt|zip|rar|iso)',
                page_text, re.IGNORECASE
            )
            if file_names:
                deep["detected_files"] = list(set(file_names))[:15]
                if not result.file_name and file_names:
                    result.file_name = file_names[0]

            # Extract quality/size info from page if not already found
            if not result.quality:
                for pat, label in QUALITY_PATTERNS:
                    if pat.search(page_text):
                        result.quality = label
                        break

            if not result.file_size:
                m = SIZE_PATTERN.search(page_text)
                if m:
                    result.file_size = m.group(1)

            if not result.codec:
                for pat, label in CODEC_PATTERNS:
                    if pat.search(page_text):
                        result.codec = label
                        break

            # Find screenshots/images
            images = []
            for img in soup.find_all("img", src=True):
                src = img.get("src", "")
                alt = img.get("alt", "")
                if any(kw in src.lower() or kw in alt.lower()
                       for kw in ["screen", "shot", "poster", "cover", "thumb"]):
                    if src.startswith("//"):
                        src = "https:" + src
                    elif not src.startswith("http"):
                        base = f"{urlparse(result.link).scheme}://{urlparse(result.link).netloc}"
                        src = urljoin(base, src)
                    images.append(src)

            if images:
                deep["images"] = images[:5]

            # Find IMDb/rating info
            imdb_links = [
                a.get("href") for a in soup.find_all("a", href=True)
                if "imdb.com" in a.get("href", "")
            ]
            if imdb_links:
                deep["imdb_link"] = imdb_links[0]

            result.deep_info = deep

    except Exception:
        pass

    return result


async def deep_scan(
    enriched_results: list[EnrichedResult],
    progress_callback=None,
) -> list[EnrichedResult]:
    """Deep scan all results to extract additional information."""
    if not enriched_results:
        return enriched_results

    # Limit deep scanning per site
    site_counts: dict[str, int] = {}
    to_scan: list[EnrichedResult] = []
    skipped: list[EnrichedResult] = []

    for r in enriched_results:
        count = site_counts.get(r.site_name, 0)
        if count < MAX_DEEP_PER_SITE and r.link:
            to_scan.append(r)
            site_counts[r.site_name] = count + 1
        else:
            skipped.append(r)

    if not to_scan:
        return enriched_results

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT, ssl=False, force_close=True)
    completed = 0
    total = len(to_scan)

    async def scan_with_progress(session, result):
        nonlocal completed
        async with semaphore:
            scanned = await _deep_scan_page(session, result)
            completed += 1
            if progress_callback:
                progress_callback(completed, total, result.site_name, "scanning")
            return scanned

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [scan_with_progress(session, r) for r in to_scan]
        scanned = await asyncio.gather(*tasks, return_exceptions=True)

    results = []
    for i, r in enumerate(scanned):
        if isinstance(r, Exception):
            results.append(to_scan[i])
        else:
            results.append(r)

    results.extend(skipped)
    return results


# ──────────────────────────────────────────────────────────────────
# Search Engine Dorking — DuckDuckGo Global & Site Operators
# ──────────────────────────────────────────────────────────────────

DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"


async def _execute_ddg_query(
    session: aiohttp.ClientSession,
    query: str,
    site_name: str,
    engine_name: str,
    semaphore: asyncio.Semaphore,
) -> list[DorkResult]:
    """Execute a single query against DuckDuckGo search."""
    async with semaphore:
        results: list[DorkResult] = []
        try:
            timeout = aiohttp.ClientTimeout(total=8)
            data = {"q": query, "b": ""}
            headers = {**DEFAULT_HEADERS, "Content-Type": "application/x-www-form-urlencoded"}

            async with session.post(
                DUCKDUCKGO_URL, data=data, headers=headers,
                timeout=timeout, ssl=False, allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    return results

                html = await resp.text(errors="replace")
                soup = BeautifulSoup(html, "lxml")

                for item in soup.select(".result"):
                    title_el = item.select_one(".result__a")
                    snippet_el = item.select_one(".result__snippet")
                    link_el = item.select_one(".result__url")

                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    link = ""

                    href = title_el.get("href", "")
                    if "uddg=" in href:
                        from urllib.parse import unquote, parse_qs
                        parsed = parse_qs(urlparse(href).query)
                        if "uddg" in parsed:
                            link = unquote(parsed["uddg"][0])
                    elif link_el:
                        link = link_el.get_text(strip=True)
                        if not link.startswith("http"):
                            link = "https://" + link

                    if link:
                        results.append(DorkResult(
                            engine=engine_name,
                            site_name=site_name,
                            title=title,
                            link=link,
                            snippet=snippet,
                        ))

        except Exception:
            pass

        return results


async def _dork_single_site(
    session: aiohttp.ClientSession,
    site: Site,
    actor_name: str,
    semaphore: asyncio.Semaphore,
) -> list[DorkResult]:
    """Dork a single site via DuckDuckGo: site:example.com "actor name"."""
    domain = urlparse(site.search_url).netloc
    query = f'site:{domain} "{actor_name}"'
    return await _execute_ddg_query(session, query, site.name, "Site Dork", semaphore)


async def dork_all_sites(
    sites: list[Site],
    names: list[str],
    progress_callback=None,
) -> list[DorkResult]:
    """
    Run comprehensive OSINT dorking:
    1. Global Web Searches across search engines (Streaming, Clouds, Torrents, Indexers)
    2. Site-Specific Dorking across all registered sites
    """
    if not names:
        return []

    semaphore = asyncio.Semaphore(15)  # Fast concurrent execution
    connector = aiohttp.TCPConnector(limit=25, ssl=False, force_close=False)
    all_results: list[DorkResult] = []
    seen_links = set()

    # Global search query templates
    global_dork_templates = [
        ('"{name}" (watch OR stream OR 1080p OR 720p OR movie OR video)', 'Global Web Search', 'Google/DDG Web'),
        ('"{name}" (site:streamtape.com OR site:doodstream.com OR site:mixdrop.co OR site:gofile.io OR site:mega.nz OR site:archive.org)', 'Cloud & Direct Hosters', 'Cloud Search'),
        ('"{name}" (site:imdb.com OR site:themoviedb.org OR site:trakt.tv OR site:rottentomatoes.com)', 'Media Databases', 'Database Search'),
    ]

    total_tasks_count = (len(names) * len(global_dork_templates)) + (len(sites) * len(names))
    completed = 0

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []

        # 1. Add Global Web Dorks
        for name in names:
            for query_tmpl, site_label, engine_label in global_dork_templates:
                q = query_tmpl.format(name=name)
                tasks.append(_execute_ddg_query(session, q, site_label, engine_label, semaphore))

        # 2. Add Site-Specific Dorks
        for name in names:
            for site in sites:
                tasks.append(_dork_single_site(session, site, name, semaphore))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            completed += 1
            if isinstance(r, list):
                for item in r:
                    if item.link and item.link not in seen_links:
                        seen_links.add(item.link)
                        all_results.append(item)
            if progress_callback:
                progress_callback(completed, total_tasks_count, "", "dorking")

    return all_results


# ──────────────────────────────────────────────────────────────────
# Cross-Reference — Find duplicates and unique entries
# ──────────────────────────────────────────────────────────────────

def cross_reference(enriched: list[EnrichedResult]) -> dict:
    """Cross-reference results to find duplicates and unique entries."""
    # Normalize titles for comparison
    def normalize(title: str) -> str:
        t = re.sub(r'[\(\)\[\]\{\}]', ' ', title.lower())
        t = re.sub(r'\b(19|20)\d{2}\b', '', t)
        t = re.sub(r'\b(1080p|720p|480p|4k|2160p)\b', '', t, flags=re.IGNORECASE)
        t = re.sub(r'\b(bluray|web-?dl|webrip|hdrip|dvdrip|hdtv)\b', '', t, flags=re.IGNORECASE)
        t = re.sub(r'\b(x264|x265|hevc|avc)\b', '', t, flags=re.IGNORECASE)
        t = re.sub(r'[^\w\s]', '', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    title_groups: dict[str, list[EnrichedResult]] = {}
    for r in enriched:
        key = normalize(r.title)
        if key and len(key) > 2:
            title_groups.setdefault(key, []).append(r)

    # Entries found on multiple sites
    multi_site = {}
    single_site = {}
    for key, group in title_groups.items():
        sites_found = set(r.site_name for r in group)
        if len(sites_found) > 1:
            multi_site[key] = {
                "title": group[0].title,
                "sites": list(sites_found),
                "count": len(group),
                "results": group,
            }
        else:
            single_site[key] = {
                "title": group[0].title,
                "site": group[0].site_name,
                "results": group,
            }

    return {
        "multi_site": multi_site,
        "single_site": single_site,
        "total_unique": len(title_groups),
        "total_duplicates": sum(v["count"] - 1 for v in multi_site.values()),
    }


# ──────────────────────────────────────────────────────────────────
# Statistics
# ──────────────────────────────────────────────────────────────────

def compute_stats(
    enriched: list[EnrichedResult],
    dork_results: list[DorkResult],
    xref: dict,
) -> dict:
    """Compute statistics for the OSINT report."""
    stats = {
        "total_results": len(enriched),
        "total_dork_results": len(dork_results),
        "unique_titles": xref.get("total_unique", 0),
        "duplicates": xref.get("total_duplicates", 0),
        "multi_site_count": len(xref.get("multi_site", {})),
        "sites_with_results": len(set(r.site_name for r in enriched)),
        "by_quality": {},
        "by_type": {},
        "by_year": {},
        "by_source": {},
        "by_site": {},
    }

    for r in enriched:
        if r.quality:
            stats["by_quality"][r.quality] = stats["by_quality"].get(r.quality, 0) + 1
        if r.media_type:
            stats["by_type"][r.media_type] = stats["by_type"].get(r.media_type, 0) + 1
        if r.year:
            stats["by_year"][r.year] = stats["by_year"].get(r.year, 0) + 1
        if r.source_type:
            stats["by_source"][r.source_type] = stats["by_source"].get(r.source_type, 0) + 1
        stats["by_site"][r.site_name] = stats["by_site"].get(r.site_name, 0) + 1

    return stats


# ──────────────────────────────────────────────────────────────────
# Full OSINT Pipeline
# ──────────────────────────────────────────────────────────────────

async def run_osint_pipeline(
    sites: list[Site],
    names: list[str],
    enable_dorking: bool = True,
    enable_deep_scan: bool = True,
    surface_callback=None,
    dork_callback=None,
    deep_callback=None,
) -> OSINTReport:
    """
    Run the full OSINT pipeline:
    1. Surface scan (regular search)
    2. Data enrichment
    3. Dorking (search engine site: queries)
    4. Deep scan (follow links)
    5. Cross-reference
    6. Statistics
    """
    from scraper import search_all

    report = OSINTReport(names=names)

    # Phase 1: Surface scan + Google & Web Search
    report.surface_results = await search_all(sites, names, include_google=True, progress_callback=surface_callback)

    # Phase 2: Enrichment
    report.enriched_results = enrich_all(report.surface_results)

    # Phase 3: Dorking
    if enable_dorking and sites:
        report.dork_results = await dork_all_sites(sites, names, dork_callback)

    # Phase 4: Deep scan
    if enable_deep_scan and report.enriched_results:
        report.deep_results = await deep_scan(
            report.enriched_results, deep_callback
        )
    else:
        report.deep_results = report.enriched_results

    # Phase 5 & 6: Cross-reference and stats
    xref = cross_reference(report.deep_results)
    report.stats = compute_stats(report.deep_results, report.dork_results, xref)
    report.stats["cross_reference"] = {
        "multi_site": {
            k: {"title": v["title"], "sites": v["sites"], "count": v["count"]}
            for k, v in xref.get("multi_site", {}).items()
        },
        "unique_titles": xref.get("total_unique", 0),
    }

    return report


def run_osint(
    sites: list[Site],
    names: list[str],
    enable_dorking: bool = True,
    enable_deep_scan: bool = True,
    surface_callback=None,
    dork_callback=None,
    deep_callback=None,
) -> OSINTReport:
    """Synchronous wrapper for run_osint_pipeline."""
    return asyncio.run(run_osint_pipeline(
        sites, names, enable_dorking, enable_deep_scan,
        surface_callback, dork_callback, deep_callback,
    ))
