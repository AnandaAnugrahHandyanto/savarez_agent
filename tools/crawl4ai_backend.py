"""Crawl4AI backend for Hermes web tools.

Provides extract capabilities via a local Crawl4AI service.
Uses the /md endpoint for single-URL markdown extraction
and /crawl endpoint for batch operations.

Environment variable:
    CRAWL4AI_URL=http://localhost:11235
"""

import os
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_CRAWL4AI_BASE_URL = os.getenv("CRAWL4AI_URL", "http://localhost:11235")


def _crawl4ai_request(endpoint: str, payload: dict, timeout: float = 60.0) -> dict:
    """Send a POST request to the Crawl4AI API."""
    url = f"{_CRAWL4AI_BASE_URL}/{endpoint.lstrip('/')}"
    logger.info("Crawl4AI %s request to %s", endpoint, url)
    response = httpx.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def check_crawl4ai_available() -> bool:
    """Return True when the Crawl4AI service is reachable."""
    try:
        resp = httpx.get(f"{_CRAWL4AI_BASE_URL}/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def crawl4ai_extract_single(url: str, format: str = "markdown") -> Dict[str, Any]:
    """Extract a single URL using Crawl4AI /md endpoint.
    
    Returns a dict matching Firecrawl's scrape response shape:
    {success, data: {markdown, html, metadata}}
    """
    try:
        # Use /md endpoint for clean markdown extraction
        filter_type = "fit" if format == "markdown" else "raw"
        response = _crawl4ai_request("/md", {
            "url": url,
            "f": filter_type,
        }, timeout=60.0)
        
        markdown = response.get("markdown", "")
        success = response.get("success", False)
        
        return {
            "success": success,
            "data": {
                "markdown": markdown,
                "html": "",  # /md doesn't return HTML
                "metadata": {
                    "title": _extract_title_from_markdown(markdown),
                    "sourceURL": url,
                    "url": url,
                },
            },
        }
    except Exception as e:
        logger.warning("Crawl4AI extract failed for %s: %s", url, e)
        return {
            "success": False,
            "data": {},
            "error": str(e),
        }


def crawl4ai_extract_batch(urls: List[str], format: str = "markdown") -> List[Dict[str, Any]]:
    """Extract multiple URLs using Crawl4AI /crawl endpoint.
    
    Returns a list of dicts matching the standard document format:
    [{url, title, content, raw_content, metadata, error}]
    """
    documents: List[Dict[str, Any]] = []
    
    try:
        response = _crawl4ai_request("/crawl", {
            "urls": urls,
            "crawler_config": {
                "cache_mode": "bypass",
                "headless": True,
            },
        }, timeout=120.0)
        
        results = response.get("results", [])
        
        for result in results:
            url = result.get("url", "")
            success = result.get("success", False)
            error = result.get("error_message", "")
            
            if not success and error:
                documents.append({
                    "url": url,
                    "title": "",
                    "content": "",
                    "raw_content": "",
                    "error": error,
                    "metadata": {"sourceURL": url},
                })
                continue
            
            # Try to get markdown first, then cleaned_html, then html
            content = ""
            markdown_data = result.get("markdown")
            if isinstance(markdown_data, dict):
                # Crawl4AI returns markdown as dict with raw_markdown, markdown_with_citations, etc.
                content = markdown_data.get("raw_markdown", "") or markdown_data.get("markdown_with_citations", "")
            elif isinstance(markdown_data, str) and markdown_data:
                content = markdown_data
            
            # Fallback chain if markdown is empty
            if not content:
                if result.get("fit_markdown"):
                    content = result["fit_markdown"]
                elif result.get("cleaned_html"):
                    content = result["cleaned_html"]
                elif result.get("html"):
                    content = result["html"]
            
            metadata = result.get("metadata", {}) or {}
            title = ""
            if isinstance(metadata, dict):
                title = metadata.get("title", "") or ""
            
            documents.append({
                "url": url,
                "title": title or "",
                "content": content or "",
                "raw_content": content or "",
                "metadata": {
                    "sourceURL": url,
                    "title": title or "",
                },
            })
        
        # Handle missing results (URLs that didn't return)
        returned_urls = {r.get("url") for r in results}
        for url in urls:
            if url not in returned_urls:
                documents.append({
                    "url": url,
                    "title": "",
                    "content": "",
                    "raw_content": "",
                    "error": "No response from Crawl4AI",
                    "metadata": {"sourceURL": url},
                })
                
    except Exception as e:
        logger.warning("Crawl4AI batch extract failed: %s", e)
        # Return error for all URLs
        for url in urls:
            documents.append({
                "url": url,
                "title": "",
                "content": "",
                "raw_content": "",
                "error": str(e),
                "metadata": {"sourceURL": url},
            })
    
    return documents


def _extract_title_from_markdown(markdown: str) -> str:
    """Extract title from markdown content (first H1)."""
    if not markdown:
        return ""
    lines = markdown.strip().split("\n")
    for line in lines[:10]:  # Check first 10 lines
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return ""
