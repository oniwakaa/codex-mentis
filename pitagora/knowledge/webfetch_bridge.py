"""Webfetch bridge — integrates firish/webfetch as the free web search + crawl engine.

webfetch provides:
- Multi-engine search fusion (DDG, Brave, Serper, Tavily) — DDG works with zero config
- Local page fetching + extraction (trafilatura, readability, Playwright)
- Sentence-level compression (50% fewer tokens, zero recall loss)
- Semantic caching with volatility-aware TTLs
- MCP server (web_search, fetch_url, save_finding, status, savings_report)

Install: pip install webfetch-llm
"""
import json
import os
import subprocess
from typing import Any, Dict, List, Optional


class WebfetchBridge:
    """Bridge to webfetch's local search→fetch→rank pipeline."""

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """Check if webfetch-llm is installed."""
        if self._available is not None:
            return self._available
        try:
            result = subprocess.run(
                ["python3", "-c", "import webfetch; print('ok')"],
                capture_output=True, text=True, timeout=10
            )
            self._available = result.returncode == 0
        except Exception:
            self._available = False
        return self._available

    def search(self, query: str, max_results: int = 5, force_fresh: bool = False) -> List[Dict[str, Any]]:
        """Search the web using webfetch's multi-engine fusion.

        Returns list of results with: title, url, snippet, score
        DDG works with zero config; add Brave/Serper/Tavily keys for fusion.
        """
        if not self.is_available():
            return self._fallback_search(query, max_results)

        try:
            import webfetch
            pipeline = webfetch.get_default_pipeline()
            results = pipeline.search(
                query=query,
                max_results=max_results,
                force_fresh=force_fresh,
            )
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("snippet", ""),
                    "score": r.get("score", 0.0),
                    "source": r.get("source", "webfetch"),
                }
                for r in results
            ]
        except Exception as e:
            return self._fallback_search(query, max_results)

    def fetch_url(self, url: str, extract_mode: str = "readable") -> Dict[str, Any]:
        """Fetch and extract content from a URL.

        extract_mode: 'readable' (default), 'structured', 'full', 'minimal'
        Returns: {title, text, url, cached, metadata}
        """
        if not self.is_available():
            return self._fallback_fetch(url)

        try:
            import webfetch
            pipeline = webfetch.get_default_pipeline()
            result = pipeline.fetch(url=url, mode=extract_mode)
            return {
                "title": result.get("title", ""),
                "text": result.get("text", ""),
                "url": result.get("url", url),
                "cached": result.get("cached", False),
                "metadata": result.get("metadata", {}),
            }
        except Exception as e:
            return self._fallback_fetch(url)

    def search_and_fetch(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """Search then fetch full content for top results — the full pipeline."""
        results = self.search(query, max_results=max_results)
        for result in results:
            if result.get("url"):
                fetched = self.fetch_url(result["url"])
                result["full_text"] = fetched.get("text", "")
                result["page_title"] = fetched.get("title", "")
                result["cached"] = fetched.get("cached", False)
        return results

    def _fallback_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Fallback search using DuckDuckGo HTML when webfetch isn't installed."""
        try:
            import httpx
            import re
            headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"}
            url = f"https://html.duckduckgo.com/html/?q={query}"
            with httpx.Client(timeout=15.0) as client:
                r = client.get(url, headers=headers)
            if r.status_code == 200:
                results = []
                # Simple regex extraction
                for match in re.finditer(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</(?:a|span|div)', r.text, re.DOTALL):
                    href, title_raw, snippet_raw = match.groups()
                    title = re.sub(r'<[^>]+>', '', title_raw).strip()
                    snippet = re.sub(r'<[^>]+>', '', snippet_raw).strip()
                    if title and href:
                        results.append({
                            "title": title,
                            "url": href,
                            "snippet": snippet,
                            "score": 1.0 - (len(results) * 0.1),
                            "source": "duckduckgo_fallback",
                        })
                    if len(results) >= max_results:
                        break
                return results
        except Exception:
            pass
        return []

    def _fallback_fetch(self, url: str) -> Dict[str, Any]:
        """Fallback URL fetch using httpx + basic extraction."""
        try:
            import httpx
            import re
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                r = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                text = r.text
                # Extract title
                title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.DOTALL | re.IGNORECASE)
                title = title_match.group(1).strip() if title_match else ""
                # Strip HTML
                text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
                return {"title": title, "text": text, "url": url, "cached": False, "metadata": {}}
        except Exception:
            pass
        return {"title": "", "text": "", "url": url, "cached": False, "metadata": {}}
