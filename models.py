# GoGum - Actor Search Engine
# Data models for sites and search results

from dataclasses import dataclass, field


@dataclass
class Site:
    """Represents a website source for searching."""
    name: str
    search_url: str              # URL with {query} placeholder
    selector: str                # CSS selector for result titles
    file_selector: str = ""      # CSS selector for file names
    link_selector: str = ""      # CSS selector for links
    headers: dict = field(default_factory=dict)
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "search_url": self.search_url,
            "selector": self.selector,
            "file_selector": self.file_selector,
            "link_selector": self.link_selector,
            "headers": self.headers,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Site":
        return cls(
            name=data.get("name", ""),
            search_url=data.get("search_url", ""),
            selector=data.get("selector", ""),
            file_selector=data.get("file_selector", ""),
            link_selector=data.get("link_selector", ""),
            headers=data.get("headers", {}),
            enabled=data.get("enabled", True),
        )


@dataclass
class SearchResult:
    """A single search result from a site."""
    site_name: str
    title: str
    file_name: str = ""
    link: str = ""
    query_used: str = ""  # Which name/query found this result
    thumb_url: str = ""   # Extracted image/thumbnail URL


@dataclass
class SiteSearchResult:
    """All results from searching a single site."""
    site: Site
    results: list[SearchResult] = field(default_factory=list)
    error: str = ""
    status: str = "pending"  # "success", "error", "timeout"
    query_used: str = ""     # Which name produced the results
