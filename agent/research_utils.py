import json
import logging
import xml.etree.ElementTree as ET
import urllib.parse
import urllib.robotparser
import requests
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def check_robots_txt(url: str, user_agent: str = \"*\") -> bool:
    \"\"\"
    Basic check for robots.txt 'Disallow' rules for the given URL.
    Returns True if allowed, False if disallowed.
    \"\"\"
    try:
        parsed_url = urllib.parse.urlparse(url)
        if not parsed_url.netloc:
            return True
        robots_url = f\"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt\"
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        # RobotFileParser.read() has no timeout param in older Python versions
        # but we can set the default socket timeout globally for this call
        import socket
        original_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(3.0)
        try:
            rp.read()
        finally:
            socket.setdefaulttimeout(original_timeout)
        return rp.can_fetch(user_agent, url)
    except Exception as e:
        # Fail open if robots.txt is missing or unreadable
        logger.debug(\"Could not check robots.txt for %s: %s\", url, e)
        return True

def safe_parse_arxiv(xml_content: str) -> List[Dict[str, Any]]:
    \"\"\"
    Safely parse arXiv Atom XML content into a list of paper dictionaries.
    Handles missing fields and malformed XML gracefully.
    \"\"\"
    papers = []
    try:
        ns = {'a': 'http://www.w3.org/2005/Atom'}
        root = ET.fromstring(xml_content)
        
        for entry in root.findall('a:entry', ns):
            paper = {}
            
            # Title
            title_elem = entry.find('a:title', ns)
            paper['title'] = title_elem.text.strip().replace('\n', ' ') if title_elem is not None and title_elem.text else \"No Title\"
            
            # ID
            id_elem = entry.find('a:id', ns)
            if id_elem is not None and id_elem.text:
                paper['id'] = id_elem.text.strip().split('/abs/')[-1]
                paper['url'] = id_elem.text.strip()
            else:
                paper['id'] = \"unknown\"
                paper['url'] = \"\"
            
            # Published Date
            pub_elem = entry.find('a:published', ns)
            paper['published'] = pub_elem.text[:10] if pub_elem is not None and pub_elem.text else \"Unknown\"
            
            # Authors
            authors = []
            for author in entry.findall('a:author', ns):
                name_elem = author.find('a:name', ns)
                if name_elem is not None and name_elem.text:
                    authors.append(name_elem.text.strip())
            paper['authors'] = authors
            
            # Summary/Abstract
            summary_elem = entry.find('a:summary', ns)
            paper['summary'] = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else \"No abstract available.\"
            
            # Categories
            categories = []
            for cat in entry.findall('a:category', ns):
                term = cat.get('term')
                if term:
                    categories.append(term)
            paper['categories'] = categories
            
            # PDF Link
            pdf_link = \"\"
            for link in entry.findall('a:link', ns):
                if link.get('title') == 'pdf':
                    pdf_link = link.get('href', '')
                    break
            if not pdf_link and paper['id'] != \"unknown\":
                pdf_link = f\"https://arxiv.org/pdf/{paper['id']}\"
            paper['pdf_url'] = pdf_link
            
            papers.append(paper)
            
    except ET.ParseError as e:
        logger.error(\"Failed to parse arXiv XML: %s\", e)
    except Exception as e:
        logger.error(\"Unexpected error parsing arXiv XML: %s\", e)
        
    return papers

def safe_parse_polymarket(market_json: Dict[str, Any]) -> Dict[str, Any]:
    \"\"\"
    Safely parse Polymarket Gamma API market data.
    Handles double-encoded JSON fields (outcomePrices, clobTokenIds, etc.)
    \"\"\"
    parsed = market_json.copy()
    
    # Fields that are often double-encoded strings in Gamma API
    double_encoded_fields = ['outcomePrices', 'outcomes', 'clobTokenIds']
    
    for field in double_encoded_fields:
        val = parsed.get(field)
        if isinstance(val, str):
            try:
                parsed[field] = json.loads(val)
            except json.JSONDecodeError:
                logger.debug(\"Could not parse double-encoded field %s: %s\", field, val)
                
    # Probability formatting helper
    if 'outcomePrices' in parsed and isinstance(parsed['outcomePrices'], list):
        try:
            prices = [float(p) for p in parsed['outcomePrices']]
            parsed['probabilities'] = [f\"{p*100:.1f}%\" for p in prices]
        except (ValueError, TypeError):
            parsed['probabilities'] = []
            
    return parsed

class CitationVerifier:
    \"\"\"
    Federated Citation Verifier using arXiv (for Tech/AI) and OpenAlex (for everything else).
    Validates LLM-generated citations to prevent hallucinations from entering the Knowledge Graph.
    \"\"\"
    def __init__(self, email: str = \"hermes-agent@example.com\"):
        self.email = email
        
    def verify(self, query: str, context: str = \"\") -> Optional[Dict[str, Any]]:
        \"\"\"Verify a citation query. Returns structured metadata if found, None if hallucinated.\"\"\"
        if not query or len(query) < 5:
            return None
            
        if self._is_tech_topic(query + \" \" + context):
            res = self._check_arxiv(query)
            if res:
                return res
                
        # Fallback to OpenAlex
        return self._check_openalex(query)
            
    def _is_tech_topic(self, text: str) -> bool:
        tech_keywords = [
            'ai', 'machine learning', 'deep learning', 'neural network', 'llm', 
            'computer science', 'physics', 'quantum', 'algorithm', 'transformers'
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in tech_keywords)

    def _check_arxiv(self, query: str) -> Optional[Dict[str, Any]]:
        # arXiv search API
        url = f\"http://export.arxiv.org/api/query?search_query=all:{urllib.parse.quote(query)}&max_results=1\"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                papers = safe_parse_arxiv(resp.text)
                if papers:
                    p = papers[0]
                    # basic sanity check to avoid wildly irrelevant matches
                    # e.g., if query is \"Attention is all you need\", we expect \"Attention\" to be in the title
                    first_word = query.split()[0].lower()
                    if first_word in p['title'].lower() or first_word in p['summary'].lower():
                        return {
                            \"source\": \"arxiv\",
                            \"title\": p['title'],
                            \"authors\": p['authors'][:5], # Up to 5 authors
                            \"url\": p.get('pdf_url', p['url']),
                            \"year\": p['published'][:4]
                        }
        except Exception as e:
            logger.debug(\"ArXiv verification failed: %s\", e)
        return None

    def _check_openalex(self, query: str) -> Optional[Dict[str, Any]]:
        # OpenAlex API
        url = f\"https://api.openalex.org/works?search={urllib.parse.quote(query)}&mailto={self.email}&per-page=1\"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get(\"results\"):
                    res = data[\"results\"][0]
                    title = res.get(\"title\")
                    if title:
                        first_word = query.split()[0].lower()
                        if first_word in title.lower():
                            authors = [a.get(\"author\", {}).get(\"display_name\") for a in res.get(\"authorships\", [])]
                            return {
                                \"source\": \"openalex\",
                                \"title\": title,
                                \"authors\": authors[:5],
                                \"url\": res.get(\"doi\") or res.get(\"id\"),
                                \"year\": str(res.get(\"publication_year\"))
                            }
        except Exception as e:
            logger.debug(\"OpenAlex verification failed: %s\", e)
        return None
