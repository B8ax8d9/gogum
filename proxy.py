# GoGum - Proxy Rotator
# Smart proxy rotation with health checks, auto-failover, and multi-protocol support

import asyncio
import json
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

import aiohttp


# ──────────────────────────────────────────────────────────────────
# Proxy Models
# ──────────────────────────────────────────────────────────────────

class ProxyProtocol(Enum):
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


@dataclass
class Proxy:
    """Represents a single proxy."""
    url: str                          # Full URL: protocol://user:pass@host:port
    protocol: ProxyProtocol = ProxyProtocol.HTTP
    host: str = ""
    port: int = 0
    username: str = ""
    password: str = ""
    # Health tracking
    alive: bool = True
    last_used: float = 0.0
    success_count: int = 0
    fail_count: int = 0
    avg_response_ms: float = 0.0
    consecutive_fails: int = 0
    last_error: str = ""
    country: str = ""
    # Ban tracking per domain
    banned_domains: set = field(default_factory=set)

    @classmethod
    def from_string(cls, proxy_str: str) -> "Proxy":
        """
        Parse proxy from string. Supports formats:
          - http://host:port
          - socks5://user:pass@host:port
          - host:port (defaults to HTTP)
          - host:port:user:pass
        """
        proxy_str = proxy_str.strip()
        if not proxy_str:
            raise ValueError("Empty proxy string")

        protocol = ProxyProtocol.HTTP
        username = ""
        password = ""

        # Detect protocol
        for proto in ProxyProtocol:
            if proxy_str.lower().startswith(f"{proto.value}://"):
                protocol = proto
                break

        if "://" in proxy_str:
            parsed = urlparse(proxy_str)
            host = parsed.hostname or ""
            port = parsed.port or 8080
            username = parsed.username or ""
            password = parsed.password or ""
        else:
            parts = proxy_str.split(":")
            if len(parts) == 2:
                host, port = parts[0], int(parts[1])
            elif len(parts) == 4:
                host, port = parts[0], int(parts[1])
                username, password = parts[2], parts[3]
            else:
                raise ValueError(f"Invalid proxy format: {proxy_str}")

        # Build clean URL
        auth = f"{username}:{password}@" if username else ""
        url = f"{protocol.value}://{auth}{host}:{port}"

        return cls(
            url=url,
            protocol=protocol,
            host=host,
            port=port,
            username=username,
            password=password,
        )

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "protocol": self.protocol.value,
            "alive": self.alive,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "avg_response_ms": round(self.avg_response_ms, 1),
            "country": self.country,
        }

    @property
    def score(self) -> float:
        """Quality score: higher is better."""
        if not self.alive:
            return -1.0
        total = self.success_count + self.fail_count
        if total == 0:
            return 50.0  # Untested proxy gets medium score
        success_rate = self.success_count / total
        speed_score = max(0, 100 - self.avg_response_ms / 50)
        return (success_rate * 70) + (speed_score * 0.3)

    @property
    def is_socks(self) -> bool:
        return self.protocol in (ProxyProtocol.SOCKS4, ProxyProtocol.SOCKS5)


# ──────────────────────────────────────────────────────────────────
# Proxy Rotator
# ──────────────────────────────────────────────────────────────────

MAX_CONSECUTIVE_FAILS = 5        # Disable proxy after this many consecutive failures
COOLDOWN_AFTER_BAN = 300         # Seconds to cool down a banned proxy
PROXY_TEST_URL = "http://httpbin.org/ip"
PROXY_TEST_TIMEOUT = 10


class ProxyRotator:
    """
    Smart proxy rotation with:
    - Round-robin / random / score-based selection
    - Auto health checks
    - Ban detection per domain
    - Auto-disable dead proxies
    - Proxy chain support
    """

    def __init__(self):
        self._proxies: list[Proxy] = []
        self._index: int = 0
        self._lock = None
        try:
            if asyncio.get_running_loop():
                self._lock = asyncio.Lock()
        except RuntimeError:
            self._lock = None
        self._enabled: bool = False
        self._mode: str = "smart"  # "round_robin", "random", "smart"

    @property
    def enabled(self) -> bool:
        return self._enabled and len(self._proxies) > 0

    @property
    def total(self) -> int:
        return len(self._proxies)

    @property
    def alive_count(self) -> int:
        return sum(1 for p in self._proxies if p.alive)

    @property
    def proxies(self) -> list[Proxy]:
        return self._proxies.copy()

    def set_mode(self, mode: str):
        """Set rotation mode: 'round_robin', 'random', or 'smart'."""
        if mode in ("round_robin", "random", "smart"):
            self._mode = mode

    # ── Loading ───────────────────────────────────────────────────

    def load_from_file(self, file_path: str) -> int:
        """
        Load proxies from a text file (one per line).
        Returns number of proxies loaded.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Proxy file not found: {file_path}")

        count = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    proxy = Proxy.from_string(line)
                    if not any(p.url == proxy.url for p in self._proxies):
                        self._proxies.append(proxy)
                        count += 1
                except (ValueError, Exception):
                    continue

        if count > 0:
            self._enabled = True
        return count

    def load_from_list(self, proxy_strings: list[str]) -> int:
        """Load proxies from a list of strings."""
        count = 0
        for ps in proxy_strings:
            try:
                proxy = Proxy.from_string(ps)
                if not any(p.url == proxy.url for p in self._proxies):
                    self._proxies.append(proxy)
                    count += 1
            except (ValueError, Exception):
                continue
        if count > 0:
            self._enabled = True
        return count

    def add_proxy(self, proxy_str: str) -> bool:
        """Add a single proxy."""
        try:
            proxy = Proxy.from_string(proxy_str)
            if any(p.url == proxy.url for p in self._proxies):
                return False
            self._proxies.append(proxy)
            self._enabled = True
            return True
        except Exception:
            return False

    def remove_proxy(self, proxy_url: str) -> bool:
        """Remove a proxy by URL."""
        for i, p in enumerate(self._proxies):
            if p.url == proxy_url or p.host in proxy_url:
                self._proxies.pop(i)
                if not self._proxies:
                    self._enabled = False
                return True
        return False

    def clear(self):
        """Remove all proxies."""
        self._proxies.clear()
        self._enabled = False
        self._index = 0

    # ── Selection ─────────────────────────────────────────────────

    def get_next(self, domain: str = "") -> Proxy | None:
        """Get the next proxy based on the rotation mode."""
        alive = [
            p for p in self._proxies
            if p.alive and domain not in p.banned_domains
        ]
        if not alive:
            return None

        if self._mode == "round_robin":
            self._index = self._index % len(alive)
            proxy = alive[self._index]
            self._index += 1
            return proxy

        elif self._mode == "random":
            return random.choice(alive)

        else:  # "smart" — score-based with weighted random
            # Sort by score, pick from top 50%
            sorted_proxies = sorted(alive, key=lambda p: p.score, reverse=True)
            top_half = sorted_proxies[:max(1, len(sorted_proxies) // 2)]
            proxy = random.choice(top_half)
            return proxy

    def get_proxy_url(self, domain: str = "") -> str | None:
        """Get proxy URL string for aiohttp."""
        proxy = self.get_next(domain)
        if proxy:
            proxy.last_used = time.time()
            return proxy.url
        return None

    # ── Health Tracking ───────────────────────────────────────────

    def report_success(self, proxy_url: str, response_time_ms: float = 0):
        """Report a successful request through a proxy."""
        for p in self._proxies:
            if p.url == proxy_url:
                p.success_count += 1
                p.consecutive_fails = 0
                if response_time_ms > 0:
                    total = p.success_count + p.fail_count
                    p.avg_response_ms = (
                        (p.avg_response_ms * (total - 1) + response_time_ms) / total
                    )
                break

    def report_failure(self, proxy_url: str, error: str = "", domain: str = ""):
        """Report a failed request through a proxy."""
        for p in self._proxies:
            if p.url == proxy_url:
                p.fail_count += 1
                p.consecutive_fails += 1
                p.last_error = error

                # Auto-disable after too many consecutive failures
                if p.consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                    p.alive = False

                # Detect ban (403, 429, captcha)
                if any(kw in error.lower() for kw in ["403", "429", "captcha", "blocked", "banned"]):
                    if domain:
                        p.banned_domains.add(domain)

                break

    def report_ban(self, proxy_url: str, domain: str):
        """Report that a proxy is banned on a specific domain."""
        for p in self._proxies:
            if p.url == proxy_url:
                p.banned_domains.add(domain)
                break

    # ── Health Check ──────────────────────────────────────────────

    async def test_proxy(self, proxy: Proxy) -> bool:
        """Test if a single proxy is working."""
        try:
            timeout = aiohttp.ClientTimeout(total=PROXY_TEST_TIMEOUT)

            connector_kwargs = {}
            proxy_url = proxy.url

            # For SOCKS proxies, we need aiohttp_socks
            if proxy.is_socks:
                try:
                    from aiohttp_socks import ProxyConnector
                    connector = ProxyConnector.from_url(proxy.url)
                    async with aiohttp.ClientSession(connector=connector) as session:
                        start = time.time()
                        async with session.get(
                            PROXY_TEST_URL, timeout=timeout, ssl=False
                        ) as resp:
                            elapsed = (time.time() - start) * 1000
                            if resp.status == 200:
                                proxy.alive = True
                                proxy.avg_response_ms = elapsed
                                proxy.consecutive_fails = 0
                                return True
                except ImportError:
                    # aiohttp_socks not installed, skip SOCKS proxies
                    proxy.alive = False
                    proxy.last_error = "aiohttp_socks not installed"
                    return False
            else:
                async with aiohttp.ClientSession() as session:
                    start = time.time()
                    async with session.get(
                        PROXY_TEST_URL, proxy=proxy_url,
                        timeout=timeout, ssl=False
                    ) as resp:
                        elapsed = (time.time() - start) * 1000
                        if resp.status == 200:
                            proxy.alive = True
                            proxy.avg_response_ms = elapsed
                            proxy.consecutive_fails = 0
                            return True

        except Exception as e:
            proxy.last_error = str(e)

        proxy.alive = False
        return False

    async def test_all(self, progress_callback=None) -> dict:
        """Test all proxies concurrently. Returns stats."""
        if not self._proxies:
            return {"total": 0, "alive": 0, "dead": 0}

        sem = asyncio.Semaphore(20)
        alive = 0
        dead = 0
        completed = 0

        async def _test(proxy):
            nonlocal alive, dead, completed
            async with sem:
                result = await self.test_proxy(proxy)
                if result:
                    alive += 1
                else:
                    dead += 1
                completed += 1
                if progress_callback:
                    progress_callback(completed, len(self._proxies), proxy.host, "alive" if result else "dead")

        await asyncio.gather(*[_test(p) for p in self._proxies])

        return {"total": len(self._proxies), "alive": alive, "dead": dead}

    def revive_all(self):
        """Reset all proxies to alive (useful after cooldown)."""
        for p in self._proxies:
            p.alive = True
            p.consecutive_fails = 0
            p.banned_domains.clear()

    # ── Persistence ───────────────────────────────────────────────

    def save_to_file(self, file_path: str):
        """Save proxy list with health stats to JSON."""
        data = [p.to_dict() for p in self._proxies]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_stats(self) -> dict:
        """Get proxy pool statistics."""
        return {
            "total": len(self._proxies),
            "alive": sum(1 for p in self._proxies if p.alive),
            "dead": sum(1 for p in self._proxies if not p.alive),
            "mode": self._mode,
            "enabled": self._enabled,
            "avg_score": (
                sum(p.score for p in self._proxies if p.alive) /
                max(1, sum(1 for p in self._proxies if p.alive))
            ),
        }


# ──────────────────────────────────────────────────────────────────
# Global singleton
# ──────────────────────────────────────────────────────────────────

_rotator: ProxyRotator | None = None


def get_rotator() -> ProxyRotator:
    """Get the global proxy rotator singleton."""
    global _rotator
    if _rotator is None:
        _rotator = ProxyRotator()
    return _rotator
