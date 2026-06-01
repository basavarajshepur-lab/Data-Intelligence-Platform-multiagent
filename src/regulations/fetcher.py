"""Real-time regulatory content fetcher.

Pulls RSS feeds from official banking and data-privacy regulators, caches
the results in the memory DB for 24 hours, and returns relevant items as
structured context for the agent's system prompt.

Sources
-------
- BIS / BCBS   — Basel Committee on Banking Supervision publications
- ICO          — UK Information Commissioner's Office (UK GDPR)
- FCA          — Financial Conduct Authority
- EBA          — European Banking Authority
"""

import hashlib
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from ..memory.memory_store import cache_regulation_items, get_cached_regulations

SOURCES: list[dict] = [
    {
        "key": "BIS_BCBS",
        "rss_url": "https://www.bis.org/rss/bcbs.rss",
        "framework": "BCBS_239",
        "display": "BIS / Basel Committee (BCBS)",
        "keywords": ["bcbs", "239", "risk data", "aggregation", "reporting", "supervisory"],
    },
    {
        "key": "ICO_NEWS",
        "rss_url": "https://ico.org.uk/about-the-ico/media-centre/news-and-blogs/rss/",
        "framework": "UK_GDPR",
        "display": "ICO — UK GDPR",
        "keywords": ["gdpr", "data protection", "personal data", "privacy", "controller"],
    },
    {
        "key": "FCA_NEWS",
        "rss_url": "https://www.fca.org.uk/news/rss.xml",
        "framework": "FCA",
        "display": "FCA — Financial Conduct Authority",
        "keywords": ["data", "reporting", "financial crime", "aml", "consumer", "conduct"],
    },
    {
        "key": "EBA_NEWS",
        "rss_url": "https://www.eba.europa.eu/rss.xml",
        "framework": "EBA",
        "display": "EBA — European Banking Authority",
        "keywords": ["data", "reporting", "supervisory", "capital", "credit", "risk"],
    },
]

_HEADERS = {"User-Agent": "MetadataAgent/1.0 (regulatory-monitor; +github)"}
_TIMEOUT = 10  # seconds


def _fetch_rss(url: str) -> list[dict]:
    """Fetch and parse an RSS feed. Returns a list of item dicts."""
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            content = resp.read()
    except (urllib.error.URLError, OSError):
        return []

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    # Handle both RSS 2.0 and Atom
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item") or root.findall(".//atom:entry", ns)

    results = []
    for item in items[:20]:  # cap at 20 items per source
        def _text(tag: str) -> str:
            el = item.find(tag) or item.find(f"atom:{tag}", ns)
            if el is None:
                return ""
            return (el.text or "").strip()

        # Extract link from <link> or <atom:link href="...">
        link_el = item.find("link") or item.find("atom:link", ns)
        link = ""
        if link_el is not None:
            link = (link_el.text or link_el.get("href", "")).strip()

        title = _text("title")
        pub_date = _text("pubDate") or _text("published") or _text("updated")
        description = _text("description") or _text("summary") or _text("content")

        item_id = hashlib.md5((title + link).encode()).hexdigest()
        results.append(
            {
                "item_id": item_id,
                "headline": title,
                "url": link,
                "published_dt": pub_date,
                "summary": description[:500] if description else "",
            }
        )
    return results


def _is_relevant(item: dict, keywords: list[str]) -> bool:
    text = (item.get("headline", "") + " " + item.get("summary", "")).lower()
    return any(kw in text for kw in keywords)


def refresh_source(source: dict) -> int:
    """Fetch one RSS source and store new items. Returns count of new items stored."""
    raw_items = _fetch_rss(source["rss_url"])
    relevant = [i for i in raw_items if _is_relevant(i, source["keywords"])]
    if not relevant:
        return 0
    cache_regulation_items(source["key"], source["framework"], relevant)
    return len(relevant)


def refresh_all() -> dict[str, int]:
    """Refresh all regulation sources. Returns {source_key: items_stored}."""
    return {src["key"]: refresh_source(src) for src in SOURCES}


def get_regulation_context(frameworks: list[str], max_age_hours: int = 24) -> str:
    """
    Return a formatted string of recent regulatory updates for the given frameworks.

    Automatically refreshes any source whose cache is older than max_age_hours.
    Returns a plain-text summary suitable for injecting into a Claude prompt.
    """
    framework_set = {f.upper() for f in frameworks} if frameworks else set()

    # Determine which sources need refreshing
    for src in SOURCES:
        if framework_set and src["framework"] not in framework_set:
            continue
        cached = get_cached_regulations(src["key"], max_age_hours=max_age_hours)
        if not cached:
            refresh_source(src)

    # Retrieve from cache
    all_items = get_cached_regulations(
        source_key=None,
        frameworks=list(framework_set) if framework_set else None,
        max_age_hours=max_age_hours,
        limit=15,
    )

    if not all_items:
        return (
            "No recent regulatory updates retrieved. "
            "Apply current knowledge of BCBS 239, UK GDPR, and FCA requirements."
        )

    lines = ["RECENT REGULATORY UPDATES (fetched from official sources):"]
    current_fw = None
    for item in all_items:
        fw = item.get("framework", "")
        if fw != current_fw:
            current_fw = fw
            lines.append(f"\n[{fw}]")
        date_str = (item.get("published_dt") or item.get("fetched_at") or "")[:10]
        lines.append(f"• {date_str}  {item['headline']}")
        if item.get("url"):
            lines.append(f"  {item['url']}")
        if item.get("summary"):
            lines.append(f"  {item['summary'][:200]}")
    return "\n".join(lines)
