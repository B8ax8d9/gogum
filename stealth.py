# GoGum - Stealth & Anti-Ban Engine
# Advanced anti-detection: UA rotation, fingerprint masking, rate limiting, ban evasion

import asyncio
import hashlib
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field


# ══════════════════════════════════════════════════════════════════
# User-Agent Pool — 60+ real browser fingerprints
# ══════════════════════════════════════════════════════════════════

USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    # Firefox macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:126.0) Gecko/20100101 Firefox/126.0",
    # Firefox Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    # Opera
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 OPR/110.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 OPR/109.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 OPR/110.0.0.0",
    # Brave
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Brave/125",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Brave/125",
    # Vivaldi
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Vivaldi/6.7",
    # Mobile
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; OnePlus 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
]

# ══════════════════════════════════════════════════════════════════
# Accept-Language pools
# ══════════════════════════════════════════════════════════════════

ACCEPT_LANGUAGES = [
    "ar,en;q=0.9",
    "ar,en-US;q=0.9,en;q=0.8",
    "ar-SA,ar;q=0.9,en-US;q=0.8,en;q=0.7",
    "ar-IQ,ar;q=0.9,en;q=0.8",
    "ar-EG,ar;q=0.9,en;q=0.8",
    "en-US,en;q=0.9",
    "en-US,en;q=0.9,ar;q=0.8",
    "en-GB,en;q=0.9,en-US;q=0.8",
    "en,ar;q=0.9",
    "fr-FR,fr;q=0.9,en;q=0.8,ar;q=0.7",
]

# ══════════════════════════════════════════════════════════════════
# Referer pools
# ══════════════════════════════════════════════════════════════════

REFERERS = [
    "https://www.google.com/",
    "https://www.google.com/search?q=",
    "https://www.google.co.uk/",
    "https://www.bing.com/",
    "https://www.bing.com/search?q=",
    "https://duckduckgo.com/",
    "https://search.yahoo.com/",
    "https://yandex.com/",
    "",  # No referer (direct visit)
    "",
]

# ══════════════════════════════════════════════════════════════════
# Platform hints for sec-ch-ua headers
# ══════════════════════════════════════════════════════════════════

SEC_CH_UA_SETS = [
    {
        "sec-ch-ua": '"Chromium";v="125", "Google Chrome";v="125", "Not-A.Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    },
    {
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    },
    {
        "sec-ch-ua": '"Chromium";v="125", "Google Chrome";v="125", "Not-A.Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
    },
    {
        "sec-ch-ua": '"Chromium";v="125", "Microsoft Edge";v="125", "Not-A.Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    },
    {
        "sec-ch-ua": '"Chromium";v="125", "Brave";v="125", "Not-A.Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    },
]


# ══════════════════════════════════════════════════════════════════
# Ban Detection Patterns
# ══════════════════════════════════════════════════════════════════

BAN_STATUS_CODES = {403, 429, 503, 407, 451}

BAN_BODY_PATTERNS = [
    "captcha", "recaptcha", "hcaptcha", "cloudflare",
    "access denied", "blocked", "forbidden",
    "rate limit", "too many requests", "try again later",
    "bot detected", "automated", "suspicious activity",
    "please verify", "security check", "challenge",
    "just a moment", "checking your browser",
    "ddos-guard", "incapsula", "sucuri",
]


# ══════════════════════════════════════════════════════════════════
# Stealth Engine
# ══════════════════════════════════════════════════════════════════

@dataclass
class StealthConfig:
    """Configuration for stealth behavior."""
    enabled: bool = True
    rotate_ua: bool = True
    rotate_headers: bool = True
    random_delays: bool = True
    min_delay: float = 0.05      # Min seconds between requests to same domain
    max_delay: float = 0.3       # Max seconds between requests to same domain
    respect_robots: bool = False  # Respect robots.txt
    max_requests_per_domain: int = 50   # Max requests per domain per session
    backoff_multiplier: float = 1.5     # Exponential backoff multiplier
    max_backoff: float = 15.0           # Max backoff seconds
    cookie_persistence: bool = True     # Keep cookies across requests


class StealthEngine:
    """
    Anti-detection engine that makes requests look like real browser traffic.

    Features:
    - Random User-Agent rotation (60+ real UAs)
    - Full header fingerprint randomization
    - Per-domain rate limiting with jitter
    - Exponential backoff on failures
    - Ban detection (status codes, body patterns)
    - Cookie jar management
    - Referer spoofing
    - sec-ch-ua client hints
    """

    def __init__(self, config: StealthConfig | None = None):
        self.config = config or StealthConfig()
        self._domain_timestamps: dict[str, float] = {}
        self._domain_counts: dict[str, int] = defaultdict(int)
        self._domain_backoffs: dict[str, float] = defaultdict(lambda: 0.5)
        self._session_ua: str = random.choice(USER_AGENTS)
        self._session_lang: str = random.choice(ACCEPT_LANGUAGES)
        self._session_hints: dict = random.choice(SEC_CH_UA_SETS)
        self._banned_domains: set[str] = set()
        self._cookie_jars: dict[str, dict] = defaultdict(dict)

    # ── Header Generation ─────────────────────────────────────────

    def get_headers(self, domain: str = "", referer: str = "") -> dict:
        """Generate realistic browser headers with randomization."""
        if not self.config.enabled:
            return {"User-Agent": self._session_ua}

        # UA rotation
        if self.config.rotate_ua:
            ua = random.choice(USER_AGENTS)
        else:
            ua = self._session_ua

        # Determine browser type from UA for consistent headers
        is_firefox = "Firefox" in ua
        is_safari = "Safari" in ua and "Chrome" not in ua
        is_chrome = "Chrome" in ua and "Safari" in ua

        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": random.choice(ACCEPT_LANGUAGES) if self.config.rotate_headers else self._session_lang,
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": random.choice(["max-age=0", "no-cache", ""]),
        }

        # Remove empty values
        headers = {k: v for k, v in headers.items() if v}

        # Referer
        if referer:
            headers["Referer"] = referer
        elif random.random() < 0.6:
            headers["Referer"] = random.choice(REFERERS)

        # Chrome-specific headers (sec-ch-ua)
        if is_chrome and not is_safari:
            hints = random.choice(SEC_CH_UA_SETS) if self.config.rotate_headers else self._session_hints
            headers.update(hints)
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-Site"] = random.choice(["none", "cross-site", "same-origin"])
            headers["Sec-Fetch-User"] = "?1"

        # Firefox-specific
        if is_firefox:
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-Site"] = "none"
            headers["Sec-Fetch-User"] = "?1"
            headers["TE"] = "trailers"

        # DNT (Do Not Track) — random
        if random.random() < 0.3:
            headers["DNT"] = "1"

        # Randomize header order by rebuilding dict
        items = list(headers.items())
        random.shuffle(items)
        return dict(items)

    # ── Rate Limiting ─────────────────────────────────────────────

    async def rate_limit(self, domain: str):
        """Apply rate limiting for a domain with random jitter."""
        if not self.config.random_delays:
            return

        now = time.time()
        last = self._domain_timestamps.get(domain, 0)
        elapsed = now - last

        # Calculate delay with jitter
        base_delay = random.uniform(self.config.min_delay, self.config.max_delay)

        # Add extra delay if domain has been hit recently
        if elapsed < base_delay:
            wait = base_delay - elapsed
            # Add random jitter (±30%)
            jitter = wait * random.uniform(-0.3, 0.3)
            wait = max(0.1, wait + jitter)
            await asyncio.sleep(wait)

        self._domain_timestamps[domain] = time.time()
        self._domain_counts[domain] += 1

    # ── Backoff ───────────────────────────────────────────────────

    async def apply_backoff(self, domain: str):
        """Apply exponential backoff for a domain after failure."""
        current = self._domain_backoffs[domain]
        await asyncio.sleep(current)
        # Increase backoff for next time
        self._domain_backoffs[domain] = min(
            current * self.config.backoff_multiplier,
            self.config.max_backoff,
        )

    def reset_backoff(self, domain: str):
        """Reset backoff for a domain after success."""
        self._domain_backoffs[domain] = 0.5

    # ── Ban Detection ─────────────────────────────────────────────

    def is_banned_response(self, status_code: int, body: str = "") -> bool:
        """Check if a response indicates we're banned/blocked."""
        if status_code in BAN_STATUS_CODES:
            return True
        if body:
            body_lower = body[:5000].lower()
            return any(pattern in body_lower for pattern in BAN_BODY_PATTERNS)
        return False

    def is_domain_banned(self, domain: str) -> bool:
        """Check if a domain has banned us."""
        return domain in self._banned_domains

    def mark_banned(self, domain: str):
        """Mark a domain as having banned us."""
        self._banned_domains.add(domain)

    def is_rate_limited(self, domain: str) -> bool:
        """Check if we've exceeded the rate limit for a domain."""
        return self._domain_counts[domain] >= self.config.max_requests_per_domain

    # ── Session Management ────────────────────────────────────────

    def rotate_identity(self):
        """Rotate the session identity (UA, language, hints)."""
        self._session_ua = random.choice(USER_AGENTS)
        self._session_lang = random.choice(ACCEPT_LANGUAGES)
        self._session_hints = random.choice(SEC_CH_UA_SETS)

    def get_cookie_jar(self, domain: str) -> dict:
        """Get the cookie jar for a domain."""
        return self._cookie_jars[domain]

    def reset(self):
        """Full reset of all stealth state."""
        self._domain_timestamps.clear()
        self._domain_counts.clear()
        self._domain_backoffs.clear()
        self._banned_domains.clear()
        self._cookie_jars.clear()
        self.rotate_identity()

    # ── Stats ─────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get stealth engine statistics."""
        return {
            "enabled": self.config.enabled,
            "ua_rotation": self.config.rotate_ua,
            "banned_domains": list(self._banned_domains),
            "rate_limited_domains": [
                d for d, c in self._domain_counts.items()
                if c >= self.config.max_requests_per_domain
            ],
            "total_domains_accessed": len(self._domain_counts),
            "requests_per_domain": dict(self._domain_counts),
        }


# ══════════════════════════════════════════════════════════════════
# Global singleton
# ══════════════════════════════════════════════════════════════════

_engine: StealthEngine | None = None


def get_stealth() -> StealthEngine:
    """Get the global stealth engine singleton."""
    global _engine
    if _engine is None:
        _engine = StealthEngine()
    return _engine
