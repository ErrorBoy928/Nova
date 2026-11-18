"""
utils/researcher.py

Autonomous Web Search & Research Engine for Nova AI.
Uses DuckDuckGo HTML / Lite endpoints with clean text parsing,
requiring ZERO external API keys.
"""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def search_web(query: str, max_results: int = 5) -> list[SearchResult]:
    """Performs a live web search on DuckDuckGo Lite and extracts clean snippets."""
    if not query or not query.strip():
        return []

    encoded = urllib.parse.urlencode({"q": query.strip()})
    url = f"https://html.duckduckgo.com/html/?{encoded}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    results: list[SearchResult] = []
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Extract search result blocks using regex
        blocks = re.findall(r'<div class="result__body">(.*?)</div>\s*</div>', html, re.DOTALL)
        for b in blocks[:max_results]:
            # Title & URL
            t_match = re.search(r'<a class="result__snippet[^>]*href="([^"]+)"[^>]*>(.*?)</a>', b, re.DOTALL)
            # Snippet
            s_match = re.search(r'<a class="result__snippet[^>]*>(.*?)</a>', b, re.DOTALL)

            raw_title = re.search(r'<h2 class="result__title">.*?<a[^>]*>(.*?)</a>', b, re.DOTALL)
            title = re.sub(r'<[^>]+>', '', raw_title.group(1)).strip() if raw_title else "Web Result"

            raw_url = re.search(r'<a class="result__url"[^>]*href="([^"]+)"', b)
            res_url = raw_url.group(1).strip() if raw_url else ""
            if "uddg=" in res_url:
                # Decode DuckDuckGo redirect URL
                uddg = re.search(r'uddg=([^&]+)', res_url)
                if uddg:
                    res_url = urllib.parse.unquote(uddg.group(1))

            snippet = re.sub(r'<[^>]+>', '', s_match.group(1)).strip() if s_match else ""

            if title and (res_url or snippet):
                results.append(SearchResult(title=title, url=res_url, snippet=snippet))

        if not results:
            # Fallback simple search
            matches = re.findall(r'<a class="result__url"[^>]*href="([^"]+)".*?<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
            for u, s in matches[:max_results]:
                results.append(SearchResult(title=query, url=u.strip(), snippet=re.sub(r'<[^>]+>', '', s).strip()))

    except Exception as exc:
        log.warning("DuckDuckGo search failed for '{}': {}", query, exc)

    return results


def research_topic(query: str, max_results: int = 4) -> str:
    """Performs deep research on a topic and returns formatted summary text."""
    results = search_web(query, max_results=max_results)
    if not results:
        return f"No live web results could be retrieved for '{query}'. Please check internet connection."

    summary_lines = [f"**Web Research Findings for:** *{query}*\n"]
    for i, res in enumerate(results, 1):
        summary_lines.append(f"**{i}. {res.title}**")
        if res.snippet:
            summary_lines.append(f"   {res.snippet}")
        if res.url:
            summary_lines.append(f"   [Source Link]({res.url})")
        summary_lines.append("")

    return "\n".join(summary_lines)
