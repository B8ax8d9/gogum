# GoGum - Smart Name & Multilingual Resolver
# Automatically detects Arabic/foreign names and resolves their English equivalents

import asyncio
import json
import re
import urllib.parse
from typing import List

import aiohttp


# Arabic character detection
ARABIC_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')


def is_arabic(text: str) -> bool:
    """Check if the text contains Arabic characters."""
    return bool(ARABIC_RE.search(text))


# Common phonetic mapping table for Arabic actor name spellings
PHONETIC_MAP = {
    "سكارليت": ["Scarlett", "Scarlet"],
    "جوهانسون": ["Johansson", "Johanson"],
    "السا": ["Elsa", "Elza"],
    "ايلسا": ["Elsa", "Elza"],
    "جين": ["Jean", "Jane", "Jen"],
    "ايفا": ["Eva"],
    "إيفا": ["Eva"],
    "الفي": ["Elfie"],
    "الفاي": ["Elfie"],
    "إلفي": ["Elfie"],
    "ميا": ["Mia"],
    "خليفة": ["Khalifa"],
    "انجيلا": ["Angela"],
    "أنجيلا": ["Angela"],
    "وايت": ["White"],
    "رايلي": ["Riley"],
    "ريد": ["Reid"],
    "لانا": ["Lana"],
    "رودس": ["Rhoades"],
    "لينا": ["Lena"],
    "توم": ["Tom"],
    "كروز": ["Cruise"],
    "هانكس": ["Hanks"],
    "براد": ["Brad"],
    "بيت": ["Pitt"],
    "ليوناردو": ["Leonardo"],
    "دي كابريو": ["DiCaprio"],
    "ديكابريو": ["DiCaprio"],
    "جوني": ["Johnny"],
    "ديب": ["Depp"],
    "كيانو": ["Keanu"],
    "ريفز": ["Reeves"],
    "روبرت": ["Robert"],
    "داوني": ["Downey"],
    "ويل": ["Will"],
    "سميث": ["Smith"],
    "مورغان": ["Morgan"],
    "فريمان": ["Freeman"],
    "ايما": ["Emma"],
    "إيما": ["Emma"],
    "واتسون": ["Watson"],
    "ستون": ["Stone"],
    "مارجو": ["Margot"],
    "روبي": ["Robbie"],
    "غال": ["Gal"],
    "غادوت": ["Gadot"],
    "سيدني": ["Sydney"],
    "سويني": ["Sweeney"],
    "انا": ["Ana"],
    "دي ارماس": ["de Armas"],
}


async def _resolve_wikipedia(session: aiohttp.ClientSession, name: str) -> List[str]:
    """Query Arabic Wikipedia to get official English article title."""
    candidates = []
    url = (
        f"https://ar.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(name)}"
        f"&prop=langlinks&lllang=en&redirects=1&format=json"
    )
    headers = {"User-Agent": "GoGum-Search/2.0 (Windows NT 10.0)"}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=4), ssl=False) as resp:
            if resp.status == 200:
                data = await resp.json()
                pages = data.get("query", {}).get("pages", {})
                for pid, pdata in pages.items():
                    if pid == "-1":
                        continue
                    langlinks = pdata.get("langlinks", [])
                    for ll in langlinks:
                        if ll.get("lang") == "en":
                            en_title = ll.get("*", "").strip()
                            if en_title:
                                candidates.append(en_title)
    except Exception:
        pass
    return candidates


async def _resolve_wikidata(session: aiohttp.ClientSession, name: str) -> List[str]:
    """Query Wikidata API for English label of an Arabic search entity."""
    candidates = []
    url = (
        f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={urllib.parse.quote(name)}"
        f"&language=ar&uselang=en&type=item&limit=3&format=json"
    )
    headers = {"User-Agent": "GoGum-Search/2.0 (Windows NT 10.0)"}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=4), ssl=False) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = data.get("search", [])
                for r in results:
                    label = r.get("label", "").strip()
                    desc = r.get("description", "").lower()
                    # Check if it looks like a person/actor
                    if label and not is_arabic(label):
                        candidates.append(label)
    except Exception:
        pass
    return candidates


def _resolve_phonetic(name: str) -> List[str]:
    """Resolve Arabic words using local phonetic dictionary."""
    words = name.strip().split()
    matched_lists = []
    all_matched = True

    for w in words:
        # Clean word from punctuation / prefixes
        clean_w = re.sub(r'^[وفلكب]', '', w) if len(w) > 3 and w.startswith(('و', 'ف', 'ل', 'ك', 'ب')) else w
        if w in PHONETIC_MAP:
            matched_lists.append(PHONETIC_MAP[w])
        elif clean_w in PHONETIC_MAP:
            matched_lists.append(PHONETIC_MAP[clean_w])
        else:
            all_matched = False

    if all_matched and matched_lists:
        # Generate combinations
        combos = [""]
        for word_options in matched_lists:
            new_combos = []
            for c in combos:
                for opt in word_options:
                    new_combos.append(f"{c} {opt}".strip())
            combos = new_combos
        return combos[:3]

    return []


async def resolve_actor_names(input_names: List[str]) -> List[str]:
    """
    Given a list of input names (in Arabic or English),
    returns an expanded list of search variations (English + original).
    """
    resolved = []
    seen = set()

    for name in input_names:
        name = name.strip()
        if not name:
            continue
        if name.lower() not in seen:
            resolved.append(name)
            seen.add(name.lower())

        if is_arabic(name):
            # Try Wikipedia & Wikidata in parallel
            try:
                connector = aiohttp.TCPConnector(ssl=False)
                async with aiohttp.ClientSession(connector=connector) as session:
                    wiki_task = _resolve_wikipedia(session, name)
                    wikidata_task = _resolve_wikidata(session, name)
                    wiki_results, wikidata_results = await asyncio.gather(wiki_task, wikidata_task, return_exceptions=True)

                    if isinstance(wiki_results, list):
                        for en_name in wiki_results:
                            if en_name.lower() not in seen:
                                resolved.append(en_name)
                                seen.add(en_name.lower())

                    if isinstance(wikidata_results, list):
                        for en_name in wikidata_results:
                            if en_name.lower() not in seen:
                                resolved.append(en_name)
                                seen.add(en_name.lower())
            except Exception:
                pass

            # Also check phonetic dictionary
            phonetic_results = _resolve_phonetic(name)
            for en_name in phonetic_results:
                if en_name.lower() not in seen:
                    resolved.append(en_name)
                    seen.add(en_name.lower())

    return resolved


def expand_search_names(input_names: List[str]) -> List[str]:
    """Synchronous wrapper for resolve_actor_names."""
    return asyncio.run(resolve_actor_names(input_names))
