# GoGum - HTML Report & Interactive Results Dashboard
# Generate modern dark-theme interactive dashboards and open them in browser (English)

import json
import os
import re
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List

from models import SiteSearchResult, SearchResult


def _extract_badges(text: str) -> str:
    """Extract quality, year, and source badges from title text."""
    badges = []
    
    # Year
    m_year = re.search(r'[\(\[\. ]((?:19|20)\d{2})[\)\]\. ]', text)
    if m_year:
        badges.append(f'<span class="badge-tag tag-year">📅 {m_year.group(1)}</span>')
        
    # Quality
    if re.search(r'4[Kk]|2160[pP]', text):
        badges.append('<span class="badge-tag tag-4k">4K UHD</span>')
    elif re.search(r'1080[pPiI]', text):
        badges.append('<span class="badge-tag tag-1080p">1080p</span>')
    elif re.search(r'720[pPiI]', text):
        badges.append('<span class="badge-tag tag-720p">720p</span>')
        
    # Codec / Source
    if re.search(r'[xX]\.?265|HEVC', text, re.IGNORECASE):
        badges.append('<span class="badge-tag tag-codec">HEVC</span>')
    if re.search(r'BluRay|BDRip|BRRip', text, re.IGNORECASE):
        badges.append('<span class="badge-tag tag-source">BluRay</span>')
    elif re.search(r'WEB-?DL|WEBRip', text, re.IGNORECASE):
        badges.append('<span class="badge-tag tag-source">WEB-DL</span>')
        
    return "".join(badges)


def generate_search_dashboard(
    names: List[str],
    results: List[SiteSearchResult],
    output_path: str = "",
    dork_results: list = None,
    open_browser: bool = False,
) -> str:
    """
    Generate an interactive, responsive HTML search dashboard with collapsible site cards,
    dynamic sorting & filtering, result counts, and direct 1-click links.
    """
    if not output_path:
        output_path = str(Path.cwd() / "gogum_results.html")

    names_str = ", ".join(names)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_results = sum(len(sr.results) for sr in results)
    sites_with_results = sum(1 for sr in results if sr.results)
    sites_with_errors = sum(1 for sr in results if sr.status == "error")
    total_dorks = len(dork_results) if dork_results else 0

    # Build site sections
    site_cards_html = ""
    card_index = 0
    for sr in results:
        if not sr.results and sr.status != "error":
            continue

        card_index += 1
        site_name = sr.site.name
        count = len(sr.results)
        is_error = sr.status == "error" and not sr.results
        query_info = sr.query_used or ""

        # Build items inside each site card
        items_html = ""
        for i, r in enumerate(sr.results, 1):
            safe_title = r.title.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
            file_badge = f'<span class="file-name">📁 {r.file_name}</span>' if r.file_name else ''
            meta_badges = _extract_badges(r.title + " " + (r.file_name or ""))

            thumb_html = ""
            thumb_url = getattr(r, 'thumb_url', '')
            if thumb_url:
                thumb_html = f"""
                <div class="result-thumb-wrapper">
                    <img src="{thumb_url}" class="result-thumb-img" alt="preview" loading="lazy" onerror="this.parentElement.style.display='none'">
                </div>
                """

            items_html += f"""
            <div class="result-card" data-title="{safe_title.lower()}" data-site="{site_name.lower()}">
                <div class="result-num">#{i}</div>
                {thumb_html}
                <div class="result-content">
                    <h3 class="result-title">{safe_title}</h3>
                    <div class="result-meta">
                        {meta_badges}
                        {file_badge}
                    </div>
                    <div class="result-url-box">
                        <input type="text" readonly class="url-input" value="{r.link}" id="url-{card_index}-{i}">
                        <button class="btn-copy" onclick="copyUrl('url-{card_index}-{i}')">📋</button>
                    </div>
                </div>
                <div class="result-action">
                    <a href="{r.link}" target="_blank" rel="noopener noreferrer" class="btn-direct-link">
                        ▶ Open
                    </a>
                </div>
            </div>
            """

        if is_error:
            status_class = "site-card-error"
            count_html = '<span class="site-count error-count">❌ Error</span>'
        else:
            status_class = "site-card-success"
            count_html = f'<span class="site-count">{count} 🎬</span>'

        site_cards_html += f"""
        <div class="site-card {status_class}" id="site-{card_index}" data-count="{count}" data-name="{site_name.lower()}">
            <div class="site-card-header" onclick="toggleSite('site-{card_index}')">
                <div class="site-card-info">
                    <span class="site-card-name">🌐 {site_name}</span>
                    {f'<span class="site-card-query">🔍 {query_info}</span>' if query_info else ''}
                </div>
                {count_html}
                <span class="site-card-arrow" id="arrow-site-{card_index}">▼</span>
            </div>
            <div class="site-card-body" id="body-site-{card_index}" style="display:none;">
                <div class="results-list">
                    {items_html if sr.results else '<p class="empty-msg">No results</p>'}
                </div>
            </div>
        </div>
        """

    # Build Dorking section if present
    dork_section_html = ""
    if dork_results:
        dork_items_html = ""
        for i, d in enumerate(dork_results, 1):
            d_title = getattr(d, 'title', '')
            d_site = getattr(d, 'site_name', '')
            d_link = getattr(d, 'link', '')
            d_engine = getattr(d, 'engine', 'Search Engine')
            
            safe_d_title = d_title.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
            dork_items_html += f"""
            <div class="result-card dork-card" data-title="{safe_d_title.lower()}" data-site="{d_site.lower()}">
                <div class="result-num" style="color:#00d2ff;">#{i}</div>
                <div class="result-content">
                    <h3 class="result-title">{safe_d_title}</h3>
                    <div class="result-meta">
                        <span class="badge-tag" style="background:#1e1b4b; color:#c084fc; border:1px solid #7e22ce;">🌐 {d_engine}</span>
                        <span class="badge-tag" style="background:#0f172a; color:#38bdf8;">📌 {d_site}</span>
                    </div>
                    <div class="result-url-box">
                        <input type="text" readonly class="url-input" value="{d_link}" id="durl-{i}">
                        <button class="btn-copy" onclick="copyUrl('durl-{i}')">📋</button>
                    </div>
                </div>
                <div class="result-action">
                    <a href="{d_link}" target="_blank" rel="noopener noreferrer" class="btn-direct-link" style="background: linear-gradient(135deg, #a855f7 0%, #6366f1 100%); color:#fff !important;">
                        ▶ Open Link
                    </a>
                </div>
            </div>
            """
            
        dork_section_html = f"""
        <div class="site-card site-card-dork" id="site-dork" data-count="{total_dorks}" data-name="osint dorking" style="border: 2px solid #7c3aed; margin-top: 25px;">
            <div class="site-card-header" onclick="toggleSite('site-dork')" style="background: linear-gradient(135deg, #1e1b4b 0%, #31104b 100%);">
                <div class="site-card-info">
                    <span class="site-card-name" style="color: #c084fc;">🕵️ OSINT Search Engine Dorking (Google & DuckDuckGo)</span>
                </div>
                <span class="site-count" style="background: #7c3aed;">{total_dorks} 🌐</span>
                <span class="site-card-arrow" id="arrow-site-dork">▼</span>
            </div>
            <div class="site-card-body" id="body-site-dork" style="display:block;">
                <div class="results-list">
                    {dork_items_html}
                </div>
            </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GoGum — {names_str}</title>
    <style>
        :root {{
            --bg: #090d16;
            --card-bg: #131b2e;
            --card-hover: #1b2640;
            --border: #23304d;
            --accent: #00d2ff;
            --accent2: #9d4edd;
            --text: #f0f4f8;
            --text-dim: #8b9bb4;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --btn-gradient: linear-gradient(135deg, #00d2ff 0%, #3a7bd5 100%);
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 20px;
            direction: ltr;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}

        /* Top Header */
        .top-header {{
            background: linear-gradient(135deg, #111a2e 0%, #1e1b4b 100%);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 25px 30px;
            text-align: center;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }}
        .top-header h1 {{
            font-size: 2.2em;
            background: linear-gradient(90deg, var(--accent), var(--accent2));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 6px;
        }}
        .search-term {{
            font-size: 1.25em;
            color: #fbbf24;
            margin: 8px 0;
            font-weight: 600;
        }}
        .stats-bar {{
            display: flex;
            justify-content: center;
            gap: 12px;
            margin-top: 12px;
            flex-wrap: wrap;
        }}
        .stat-pill {{
            padding: 5px 14px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: bold;
        }}
        .stat-total {{ background: rgba(0, 210, 255, 0.15); border: 1px solid var(--accent); color: var(--accent); }}
        .stat-sites {{ background: rgba(16, 185, 129, 0.15); border: 1px solid var(--success); color: var(--success); }}
        .stat-dork {{ background: rgba(168, 85, 247, 0.15); border: 1px solid #a855f7; color: #c084fc; }}
        .stat-errors {{ background: rgba(239, 68, 68, 0.15); border: 1px solid var(--danger); color: var(--danger); }}
        .stat-time {{ background: rgba(245, 158, 11, 0.15); border: 1px solid var(--warning); color: var(--warning); }}

        /* Filter & Sorting bar */
        .controls-panel {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 14px 18px;
            margin-bottom: 18px;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            align-items: center;
            justify-content: space-between;
        }}
        .filter-input {{
            flex: 1;
            min-width: 250px;
            background: #0b1120;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 10px 14px;
            color: white;
            font-size: 0.95em;
            outline: none;
        }}
        .filter-input:focus {{ border-color: var(--accent); }}
        
        .sort-select {{
            background: #0b1120;
            border: 1px solid var(--border);
            color: var(--text);
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 0.9em;
            outline: none;
            cursor: pointer;
        }}
        .sort-select:focus {{ border-color: var(--accent); }}

        .btn-expand-all {{
            background: rgba(0,210,255,0.1);
            border: 1px solid var(--accent);
            color: var(--accent);
            padding: 10px 18px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            font-size: 0.9em;
            white-space: nowrap;
            transition: all 0.2s;
        }}
        .btn-expand-all:hover {{ background: rgba(0,210,255,0.2); }}

        /* ======= Site Card (Accordion) ======= */
        .site-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 14px;
            margin-bottom: 10px;
            overflow: hidden;
            transition: all 0.2s;
        }}
        .site-card:hover {{
            border-color: rgba(0, 210, 255, 0.4);
        }}
        .site-card-error {{
            border-color: rgba(239, 68, 68, 0.3);
        }}

        .site-card-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 20px;
            cursor: pointer;
            user-select: none;
            transition: background 0.2s;
        }}
        .site-card-header:hover {{
            background: rgba(255,255,255,0.03);
        }}
        .site-card-info {{
            display: flex;
            align-items: center;
            gap: 12px;
            flex: 1;
            flex-wrap: wrap;
        }}
        .site-card-name {{
            font-size: 1.15em;
            font-weight: 700;
            color: #fbbf24;
        }}
        .site-card-query {{
            font-size: 0.8em;
            color: var(--text-dim);
            background: #0b1120;
            padding: 3px 10px;
            border-radius: 6px;
        }}
        .site-count {{
            background: var(--success);
            color: white;
            padding: 5px 14px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
            margin: 0 12px;
            min-width: 60px;
            text-align: center;
        }}
        .error-count {{
            background: var(--danger);
        }}
        .site-card-arrow {{
            color: var(--text-dim);
            font-size: 0.9em;
            transition: transform 0.3s;
        }}
        .site-card-arrow.open {{
            transform: rotate(180deg);
        }}

        .site-card-body {{
            border-top: 1px solid var(--border);
            padding: 15px 20px;
            background: #0b1120;
        }}

        /* ======= Result card (inside site) ======= */
        .results-list {{ display: flex; flex-direction: column; gap: 8px; }}
        .result-card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 12px 16px;
            display: flex;
            align-items: center;
            gap: 14px;
            transition: all 0.15s ease;
        }}
        .result-card:hover {{
            background: var(--card-hover);
            border-color: var(--accent);
            transform: translateX(4px);
        }}
        .result-num {{
            font-size: 0.9em;
            font-weight: bold;
            color: var(--text-dim);
            min-width: 30px;
            text-align: center;
        }}
        .result-thumb-wrapper {{
            width: 105px;
            height: 68px;
            min-width: 105px;
            border-radius: 8px;
            overflow: hidden;
            background: #090d16;
            border: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .result-thumb-img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.25s ease;
        }}
        .result-card:hover .result-thumb-img {{
            transform: scale(1.08);
        }}
        .result-content {{ flex: 1; min-width: 0; }}
        .result-title {{
            font-size: 1em;
            color: #ffffff;
            margin-bottom: 6px;
            font-weight: 600;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .result-meta {{
            display: flex;
            gap: 6px;
            align-items: center;
            margin-bottom: 6px;
            flex-wrap: wrap;
        }}
        
        .badge-tag {{
            font-size: 0.75em;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 600;
        }}
        .tag-4k {{ background: #7c2d12; color: #fdba74; border: 1px solid #ea580c; }}
        .tag-1080p {{ background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6; }}
        .tag-720p {{ background: #14532d; color: #86efac; border: 1px solid #22c55e; }}
        .tag-year {{ background: #374151; color: #f3f4f6; }}
        .tag-codec {{ background: #581c87; color: #d8b4fe; }}
        .tag-source {{ background: #134e4a; color: #5eead4; }}
        .file-name {{ background: #064e3b; color: #6ee7b7; font-size: 0.75em; padding: 2px 8px; border-radius: 4px; font-family: monospace; }}

        .result-url-box {{
            display: flex;
            gap: 6px;
            align-items: center;
        }}
        .url-input {{
            flex: 1;
            background: #0b1120;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 4px 8px;
            color: #64748b;
            font-size: 0.75em;
            font-family: monospace;
            max-width: 400px;
        }}
        .btn-copy {{
            background: #1e293b;
            border: 1px solid #334155;
            color: white;
            padding: 4px 8px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.8em;
        }}
        .btn-copy:hover {{ background: #334155; }}

        .btn-direct-link {{
            display: inline-flex;
            align-items: center;
            gap: 5px;
            background: var(--btn-gradient);
            color: #000 !important;
            font-weight: bold;
            font-size: 0.85em;
            padding: 8px 16px;
            border-radius: 8px;
            text-decoration: none;
            box-shadow: 0 3px 10px rgba(0, 210, 255, 0.3);
            transition: all 0.2s ease;
            white-space: nowrap;
        }}
        .btn-direct-link:hover {{
            transform: scale(1.05);
            box-shadow: 0 5px 15px rgba(0, 210, 255, 0.5);
        }}

        .empty-msg {{ color: var(--text-dim); text-align: center; padding: 15px; }}

        /* Summary grid */
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 8px;
            margin-bottom: 20px;
        }}
        .summary-chip {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 10px 14px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .summary-chip:hover {{
            border-color: var(--accent);
            background: var(--card-hover);
        }}
        .summary-chip-name {{ font-size: 0.85em; font-weight: 600; color: var(--text); }}
        .summary-chip-count {{ font-size: 0.85em; font-weight: bold; color: var(--accent); }}
        .summary-chip-zero {{ opacity: 0.4; }}

        @media (max-width: 768px) {{
            .result-card {{ flex-direction: column; align-items: flex-start; }}
            .btn-direct-link {{ width: 100%; justify-content: center; }}
            .summary-grid {{ grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }}
            .controls-panel {{ flex-direction: column; align-items: stretch; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="top-header">
            <h1>🎬 GoGum Search Dashboard</h1>
            <p class="search-term">🎭 {names_str}</p>
            <div class="stats-bar">
                <span class="stat-pill stat-total">📊 {total_results} Results</span>
                <span class="stat-pill stat-sites">✅ {sites_with_results} Sites Found</span>
                {f'<span class="stat-pill stat-dork">🌐 {total_dorks} Dorks Found</span>' if total_dorks else ''}
                <span class="stat-pill stat-errors">❌ {sites_with_errors} Errors</span>
                <span class="stat-pill stat-time">📅 {timestamp}</span>
            </div>
        </div>

        <!-- Quick Summary Grid -->
        <div class="summary-grid">
            {''.join(f'<div class="summary-chip {("summary-chip-zero" if not sr.results else "")}" onclick="scrollToSite(\'site-{i+1}\')">'
                     f'<span class="summary-chip-name">{sr.site.name}</span>'
                     f'<span class="summary-chip-count">{len(sr.results) if sr.results else "0"}</span>'
                     f'</div>'
                     for i, sr in enumerate(r for r in results if r.results or r.status == "error"))}
        </div>

        <!-- Interactive Filtering & Sorting Controls -->
        <div class="controls-panel">
            <input type="text" id="filterInput" class="filter-input" placeholder="🔍 Filter results by title or site name...">
            <select id="sortSelect" class="sort-select" onchange="sortSiteCards()">
                <option value="default">↕️ Sort: Default</option>
                <option value="count-desc">🔥 Sort: Most Results (High to Low)</option>
                <option value="count-asc">📉 Sort: Fewest Results</option>
                <option value="name-asc">🔤 Sort: Site Name (A-Z)</option>
            </select>
            <button class="btn-expand-all" onclick="toggleAll()">📂 Expand / Collapse All</button>
        </div>

        <!-- OSINT Dorking Results Section if available -->
        {dork_section_html}

        <!-- Site Cards Container (Accordion) -->
        <div id="cardsContainer">
            {site_cards_html}
        </div>
    </div>

    <script>
        function toggleSite(id) {{
            const body = document.getElementById('body-' + id);
            const arrow = document.getElementById('arrow-' + id);
            if (!body) return;
            if (body.style.display === 'none') {{
                body.style.display = 'block';
                if (arrow) arrow.classList.add('open');
            }} else {{
                body.style.display = 'none';
                if (arrow) arrow.classList.remove('open');
            }}
        }}

        function scrollToSite(id) {{
            const el = document.getElementById(id);
            if (el) {{
                const body = document.getElementById('body-' + id);
                const arrow = document.getElementById('arrow-' + id);
                if (body) body.style.display = 'block';
                if (arrow) arrow.classList.add('open');
                el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            }}
        }}

        let allExpanded = false;
        function toggleAll() {{
            allExpanded = !allExpanded;
            document.querySelectorAll('.site-card-body').forEach(b => b.style.display = allExpanded ? 'block' : 'none');
            document.querySelectorAll('.site-card-arrow').forEach(a => {{
                if (allExpanded) a.classList.add('open');
                else a.classList.remove('open');
            }});
        }}

        function copyUrl(id) {{
            const input = document.getElementById(id);
            if (input) {{
                input.select();
                navigator.clipboard.writeText(input.value);
            }}
        }}

        // Dynamic Filtering
        document.getElementById('filterInput').addEventListener('input', function(e) {{
            const q = e.target.value.toLowerCase().trim();
            document.querySelectorAll('.site-card').forEach(card => {{
                const siteName = (card.querySelector('.site-card-name') || {{}}).textContent || '';
                const resultCards = card.querySelectorAll('.result-card');
                let siteMatch = !q || siteName.toLowerCase().includes(q);
                let anyResultMatch = false;

                resultCards.forEach(rc => {{
                    const title = rc.getAttribute('data-title') || '';
                    if (!q || title.includes(q) || siteMatch) {{
                        rc.style.display = 'flex';
                        anyResultMatch = true;
                    }} else {{
                        rc.style.display = 'none';
                    }}
                }});

                if (!q || siteMatch || anyResultMatch) {{
                    card.style.display = 'block';
                    if (q && (siteMatch || anyResultMatch)) {{
                        const body = card.querySelector('.site-card-body');
                        const arrow = card.querySelector('.site-card-arrow');
                        if (body) body.style.display = 'block';
                        if (arrow) arrow.classList.add('open');
                    }}
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }});

        // Dynamic Sorting
        function sortSiteCards() {{
            const container = document.getElementById('cardsContainer');
            if (!container) return;
            const cards = Array.from(container.querySelectorAll('.site-card'));
            const mode = document.getElementById('sortSelect').value;

            cards.sort((a, b) => {{
                const countA = parseInt(a.getAttribute('data-count') || '0', 10);
                const countB = parseInt(b.getAttribute('data-count') || '0', 10);
                const nameA = a.getAttribute('data-name') || '';
                const nameB = b.getAttribute('data-name') || '';

                if (mode === 'count-desc') return countB - countA;
                if (mode === 'count-asc') return countA - countB;
                if (mode === 'name-asc') return nameA.localeCompare(nameB);
                return 0;
            }});

            cards.forEach(card => container.appendChild(card));
        }}
    </script>
</body>
</html>"""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(html)

    if open_browser:
        try:
            webbrowser.open(output.absolute().as_uri())
        except Exception:
            pass

    return str(output.absolute())
