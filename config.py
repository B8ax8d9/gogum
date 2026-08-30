# GoGum - Configuration Manager
# Handles loading, saving, and managing site configurations (English)

import json
import sys
from pathlib import Path
from typing import List, Tuple
from models import Site


def get_config_dir() -> Path:
    """Get the configuration directory (same as the script directory)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_config_path() -> Path:
    """Get the path to the sites.json config file."""
    return get_config_dir() / "sites.json"


def load_sites() -> List[Site]:
    """Load all sites from the config file."""
    config_path = get_config_path()
    if not config_path.exists():
        return []
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [Site.from_dict(s) for s in data.get("sites", [])]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"  [!] Error reading config file: {e}")
        return []


def save_sites(sites: List[Site]) -> None:
    """Save all sites to the config file."""
    config_path = get_config_path()
    data = {"sites": [s.to_dict() for s in sites]}
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_site(site: Site) -> Tuple[bool, str]:
    """Add a new site. Returns (success, message)."""
    sites = load_sites()
    for s in sites:
        if s.name.lower() == site.name.lower():
            return False, f"Site '{site.name}' already exists"
    sites.append(site)
    save_sites(sites)
    return True, f"Site '{site.name}' added successfully ✅"


def remove_site(name: str) -> Tuple[bool, str]:
    """Remove a site by name. Returns (success, message)."""
    sites = load_sites()
    for i, s in enumerate(sites):
        if s.name.lower() == name.lower():
            sites.pop(i)
            save_sites(sites)
            return True, f"Site '{name}' removed successfully 🗑️"
    return False, f"Site '{name}' not found"


def toggle_site(name: str) -> Tuple[bool, str]:
    """Enable/disable a site. Returns (success, message)."""
    sites = load_sites()
    for s in sites:
        if s.name.lower() == name.lower():
            s.enabled = not s.enabled
            save_sites(sites)
            status = "ENABLED ✅" if s.enabled else "DISABLED ❌"
            return True, f"Site '{name}' is now {status}"
    return False, f"Site '{name}' not found"


def get_enabled_sites() -> List[Site]:
    """Get only enabled sites."""
    return [s for s in load_sites() if s.enabled]


def import_sites(file_path: str) -> Tuple[bool, str]:
    """Import sites from a JSON file. Skips duplicates."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            new_sites = [Site.from_dict(s) for s in data]
        elif isinstance(data, dict) and "sites" in data:
            new_sites = [Site.from_dict(s) for s in data["sites"]]
        else:
            return False, "Invalid file format. Must be JSON array or object with 'sites' key"

        existing = load_sites()
        existing_names = {s.name.lower() for s in existing}
        added = 0
        for site in new_sites:
            if site.name.lower() not in existing_names:
                existing.append(site)
                existing_names.add(site.name.lower())
                added += 1
        save_sites(existing)
        return True, f"Successfully imported {added} new sites ✅ (duplicates skipped)"
    except Exception as e:
        return False, f"Error importing file: {e}"


def export_sites(file_path: str) -> Tuple[bool, str]:
    """Export all sites to a JSON file."""
    try:
        sites = load_sites()
        data = {"sites": [s.to_dict() for s in sites]}
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True, f"Successfully exported {len(sites)} sites to {file_path} ✅"
    except Exception as e:
        return False, f"Error exporting sites: {e}"
