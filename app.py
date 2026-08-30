# GoGum - Cloud Web Application
# High-performance, in-memory async server for 24/7 cloud hosting (Render, Railway, Koyeb, HuggingFace)

import os
import sys
import asyncio
from aiohttp import web

from config import get_enabled_sites
from translator import resolve_actor_names
from scraper import search_all
from report import generate_search_dashboard


async def handle_home(request):
    """Render home search page."""
    html = """<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GoGum — Cloud Search Engine</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: linear-gradient(-45deg, #090d16, #131b2e, #1a0b2e, #090d16);
            background-size: 400% 400%;
            animation: gradientBG 15s ease infinite;
            color: #f0f4f8; 
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            padding: 20px;
        }
        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        .container { 
            background: rgba(20, 25, 45, 0.65); 
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px; 
            padding: 50px 40px; 
            width: 100%;
            max-width: 750px;
            text-align: center;
            box-shadow: 0 25px 50px rgba(0,0,0,0.5);
            animation: slideUp 0.8s forwards cubic-bezier(0.2, 0.8, 0.2, 1);
        }
        @keyframes slideUp {
            from { transform: translateY(20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        .logo-icon { font-size: 3.5rem; margin-bottom: 5px; display: inline-block; animation: float 3s ease-in-out infinite; }
        @keyframes float {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
            100% { transform: translateY(0px); }
        }

        h1 { 
            background: linear-gradient(90deg, #00d2ff, #3a7bd5, #9d4edd);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 3rem; 
            font-weight: 900;
            margin-bottom: 10px; 
        }
        p { color: #a0aec0; font-size: 1.1rem; margin-bottom: 30px; line-height: 1.5; }

        .mode-selector {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 25px;
            background: rgba(0,0,0,0.3);
            padding: 6px;
            border-radius: 14px;
            border: 1px solid rgba(255,255,255,0.05);
        }
        .mode-btn {
            flex: 1;
            padding: 10px 15px;
            border: none;
            border-radius: 10px;
            background: transparent;
            color: #8b9bb4;
            font-family: inherit;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .mode-btn.active {
            background: linear-gradient(135deg, #00d2ff 0%, #3a7bd5 100%);
            color: #000;
            box-shadow: 0 4px 12px rgba(0,210,255,0.3);
        }

        .search-box {
            display: flex;
            gap: 12px;
            justify-content: center;
            align-items: center;
            flex-wrap: wrap;
        }
        
        input[type="text"] { 
            flex: 1;
            min-width: 250px;
            padding: 16px 22px; 
            font-size: 1.15rem; 
            font-family: inherit;
            border-radius: 14px; 
            border: 2px solid rgba(255, 255, 255, 0.1); 
            background: rgba(0, 0, 0, 0.3); 
            color: white; 
            outline: none; 
            transition: all 0.3s ease; 
        }
        input[type="text"]:focus { 
            border-color: #00d2ff; 
            background: rgba(0, 0, 0, 0.5);
            box-shadow: 0 0 20px rgba(0, 210, 255, 0.2);
        }
        
        input[type="submit"] { 
            padding: 16px 35px; 
            font-size: 1.2rem; 
            font-family: inherit;
            border-radius: 14px; 
            border: none; 
            background: linear-gradient(135deg, #00d2ff 0%, #3a7bd5 100%); 
            color: #000; 
            cursor: pointer; 
            font-weight: 700; 
            transition: all 0.3s ease; 
            box-shadow: 0 8px 18px rgba(0, 210, 255, 0.3);
        }
        input[type="submit"]:hover { 
            transform: translateY(-2px); 
            box-shadow: 0 12px 22px rgba(0, 210, 255, 0.4);
        }

        .features-bar {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 25px;
            font-size: 0.85rem;
            color: #64748b;
            flex-wrap: wrap;
        }
        .feature-pill { display: inline-flex; align-items: center; gap: 5px; }

        .loading { display: none; margin-top: 35px; }
        .spinner { 
            width: 50px; 
            height: 50px; 
            border: 4px solid rgba(0, 210, 255, 0.2); 
            border-top: 4px solid #00d2ff; 
            border-radius: 50%; 
            animation: spin 1s cubic-bezier(0.5, 0.1, 0.4, 0.9) infinite; 
            margin: 0 auto 20px; 
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        .loading-text {
            font-size: 1.2rem;
            color: #00d2ff;
            font-weight: bold;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { opacity: 0.6; }
            50% { opacity: 1; }
            100% { opacity: 0.6; }
        }
    </style>
    <script>
        function setMode(mode) {
            document.getElementById('searchMode').value = mode;
            document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
            if (mode === 'quick') document.getElementById('btnQuick').classList.add('active');
            if (mode === 'deep') document.getElementById('btnDeep').classList.add('active');
        }
        function showLoading() {
            const searchInput = document.querySelector('input[type="text"]').value;
            if(searchInput.trim() !== "") {
                document.getElementById("searchForm").style.display = "none";
                document.getElementById("modeSelector").style.display = "none";
                document.getElementById("loading").style.display = "block";
            }
        }
    </script>
</head>
<body>
    <div class="container">
        <div class="logo-icon">🕵️‍♂️</div>
        <h1>GoGum Search Engine</h1>
        <p>Ultra-fast multi-source media search engine with anti-ban stealth and intelligent OSINT scan.</p>
        
        <div class="mode-selector" id="modeSelector">
            <button type="button" class="mode-btn active" id="btnQuick" onclick="setMode('quick')">⚡ Quick Search</button>
            <button type="button" class="mode-btn" id="btnDeep" onclick="setMode('deep')">🔥 Deep OSINT Search</button>
        </div>

        <form id="searchForm" action="/search" method="get" onsubmit="showLoading()">
            <input type="hidden" name="mode" id="searchMode" value="quick">
            <div class="search-box">
                <input type="text" name="q" placeholder="Enter actor, character, or movie title..." required autocomplete="off" autofocus>
                <input type="submit" value="Search 🔍">
            </div>
        </form>

        <div class="features-bar">
            <span class="feature-pill">🛡️ Anti-Ban Stealth</span>
            <span class="feature-pill">⚡ DoH DNS Bypass</span>
            <span class="feature-pill">🌐 Multi-Engine Dorking</span>
            <span class="feature-pill">🎬 50+ Sources</span>
        </div>
        
        <div id="loading" class="loading">
            <div class="spinner"></div>
            <div class="loading-text">Scanning sources & search engines...<br><span style="font-size: 0.9rem; color: #a0aec0; font-weight: normal; margin-top: 10px; display: inline-block;">(Bypassing restrictions + extracting qualities and direct links)</span></div>
        </div>
    </div>
</body>
</html>"""
    return web.Response(text=html, content_type='text/html')


async def handle_search(request):
    """Perform async search and render dashboard directly."""
    query = request.rel_url.query.get('q', '').strip()
    mode = request.rel_url.query.get('mode', 'quick')
    if not query:
        return web.HTTPFound('/')

    # 1. Resolve names & aliases
    expanded_names = await resolve_actor_names([query])
    sites = get_enabled_sites()

    # 2. Execute async search
    include_google = (mode == 'deep')
    results = await search_all(sites, expanded_names, include_google=include_google)

    dork_results = []
    if mode == 'deep':
        try:
            from osint import dork_all_sites
            dork_results = await dork_all_sites(sites, expanded_names)
        except Exception:
            pass

    # 3. Generate HTML report
    tmp_path = f"/tmp/gogum_{abs(hash(query))}.html" if os.name != 'nt' else f"gogum_{abs(hash(query))}.html"
    try:
        report_file = generate_search_dashboard(expanded_names, results, output_path=tmp_path, dork_results=dork_results)
        with open(report_file, 'r', encoding='utf-8') as f:
            content = f.read()
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    # 4. Inject direct in-page search header
    injection_html = f"""
    <!-- GoGum Cloud Injected Search Hub -->
    <div style="background: linear-gradient(135deg, #111a2e 0%, #1e1b4b 100%); border: 1px solid #23304d; border-radius: 16px; padding: 20px; margin-bottom: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 15px;">
        <div style="display: flex; gap: 10px; align-items: center;">
            <a href="/" style="display: inline-flex; align-items: center; gap: 6px; padding: 10px 18px; background: rgba(255,255,255,0.05); color: #00d2ff; text-decoration: none; border-radius: 10px; font-weight: bold; border: 1px solid rgba(0,210,255,0.3); font-size: 0.9em; transition: all 0.2s;">
                🏠 Home
            </a>
        </div>
        <div style="flex: 1; min-width: 320px;">
            <form action="/search" method="get" onsubmit="document.getElementById('gui-floating-loading').style.display='flex'; this.style.opacity='0.5';" style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; align-items: center;">
                <div style="display: flex; background: #0b1120; border-radius: 10px; padding: 3px; border: 1px solid #334155;">
                    <button type="button" id="injectedBtnQuick" onclick="setInjectedMode('quick')" style="padding: 6px 14px; border: none; border-radius: 8px; font-size: 0.85em; font-weight: bold; cursor: pointer; background: {'linear-gradient(135deg, #00d2ff, #3a7bd5)' if mode == 'quick' else 'transparent'}; color: {'#000' if mode == 'quick' else '#8b9bb4'};">⚡ Quick</button>
                    <button type="button" id="injectedBtnDeep" onclick="setInjectedMode('deep')" style="padding: 6px 14px; border: none; border-radius: 8px; font-size: 0.85em; font-weight: bold; cursor: pointer; background: {'linear-gradient(135deg, #00d2ff, #3a7bd5)' if mode == 'deep' else 'transparent'}; color: {'#000' if mode == 'deep' else '#8b9bb4'};">🔥 Deep + Google</button>
                </div>
                <input type="hidden" name="mode" id="injectedSearchMode" value="{mode}">
                <input type="text" name="q" placeholder="Search for another actor or movie..." required style="flex: 1; min-width: 200px; padding: 10px 16px; border-radius: 10px; border: 1px solid #334155; background: #0b1120; color: white; outline: none; font-size: 0.95em;">
                <input type="submit" value="Search 🔍" style="padding: 10px 22px; background: linear-gradient(135deg, #00d2ff 0%, #3a7bd5 100%); color: #000; border: none; border-radius: 10px; font-weight: bold; cursor: pointer;">
            </form>
        </div>
    </div>
    <script>
        function setInjectedMode(m) {{
            document.getElementById('injectedSearchMode').value = m;
            document.getElementById('injectedBtnQuick').style.background = m === 'quick' ? 'linear-gradient(135deg, #00d2ff, #3a7bd5)' : 'transparent';
            document.getElementById('injectedBtnQuick').style.color = m === 'quick' ? '#000' : '#8b9bb4';
            document.getElementById('injectedBtnDeep').style.background = m === 'deep' ? 'linear-gradient(135deg, #00d2ff, #3a7bd5)' : 'transparent';
            document.getElementById('injectedBtnDeep').style.color = m === 'deep' ? '#000' : '#8b9bb4';
        }}
    </script>
    <div id="gui-floating-loading" style="display: none; justify-content: center; align-items: center; gap: 10px; color: #00d2ff; font-weight: bold; margin-bottom: 20px; padding: 14px; background: rgba(0, 210, 255, 0.1); border-radius: 12px; border: 1px dashed #00d2ff;">
        <div style="width: 20px; height: 20px; border: 3px solid rgba(0,210,255,0.3); border-top-color: #00d2ff; border-radius: 50%; animation: spin 1s linear infinite;"></div>
        Searching for new query... Please wait
    </div>
    """

    content = content.replace('<div class="controls-panel">', injection_html + '\n        <div class="controls-panel">')

    return web.Response(text=content, content_type='text/html')


async def handle_health(request):
    """Health check for cloud platform monitors."""
    return web.json_response({"status": "healthy", "service": "GoGum Search Engine"})


def create_app():
    app = web.Application()
    app.add_routes([
        web.get('/', handle_home),
        web.get('/search', handle_search),
        web.get('/health', handle_health),
    ])
    return app


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    host = '0.0.0.0'
    print(f"🚀 Starting GoGum Cloud App on http://{host}:{port}")
    app = create_app()
    web.run_app(app, host=host, port=port)
