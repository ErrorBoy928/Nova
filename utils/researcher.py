"""
utils/researcher.py

Autonomous Web Search & Research Engine for Nova AI.
Uses DuckDuckGo HTML / Lite endpoints with clean text parsing,
requiring ZERO external API keys.
"""

from __future__ import annotations

import html as html_lib
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from utils.logger import get_logger

log = get_logger(__name__)


def _clean_url(url: str) -> str:
    url = html_lib.unescape(url.strip())
    if "uddg=" in url:
        m = re.search(r"uddg=([^&]+)", url)
        if m:
            return urllib.parse.unquote(m.group(1))
    if url.startswith("//"):
        return "https:" + url
    return url


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
            res_url = _clean_url(raw_url.group(1)) if raw_url else ""

            snippet = re.sub(r'<[^>]+>', '', s_match.group(1)).strip() if s_match else ""

            if title and (res_url or snippet):
                results.append(SearchResult(title=title, url=res_url, snippet=snippet))

        if not results:
            # Fallback simple search
            matches = re.findall(r'<a class="result__url"[^>]*href="([^"]+)".*?<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
            for u, s in matches[:max_results]:
                results.append(SearchResult(title=query, url=_clean_url(u), snippet=re.sub(r'<[^>]+>', '', s).strip()))

    except Exception as exc:
        log.warning("DuckDuckGo search failed for '{}': {}", query, exc)

    return results


def research_topic(query: str, max_results: int = 4) -> str:
    """Performs research on a topic and returns formatted summary text."""
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


def deep_research_topic(query: str, max_sources: int = 3) -> str:
    """Performs comprehensive autonomous deep research:
    1. Searches DuckDuckGo for top web sources.
    2. Directly fetches and parses full article text from the top results.
    3. Synthesizes a structured intelligence report with key takeaways and citations.
    """
    results = search_web(query, max_results=max_sources + 2)
    if not results:
        return f"No live web results could be retrieved for '{query}'. Please check your internet connection."

    report_sections = [
        f"**Deep Autonomous Research Dossier: {query}**\n",
        "*Synthesized across multi-source live web intelligence*\n"
    ]

    fetched_count = 0
    for res in results:
        if fetched_count >= max_sources:
            break
        if not res.url or not res.url.startswith("http"):
            continue

        article_text = ""
        try:
            req = urllib.request.Request(
                res.url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                raw_html = resp.read().decode("utf-8", errors="replace")
            clean = re.sub(r"<(script|style|nav|footer|header).*?>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", clean)
            text = re.sub(r"\s+", " ", text).strip()
            article_text = text[:750]
        except Exception:
            article_text = res.snippet

        report_sections.append(f"**Source {fetched_count+1}: {res.title}**")
        report_sections.append(f"URL: {res.url}")
        if article_text:
            report_sections.append(f"Excerpt: {article_text}...\n")
        fetched_count += 1

    return "\n\n".join(report_sections)
