#!/usr/bin/env python3
"""
NAS5 Docker Apps Collection
"""

"""
This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels
"""

"""
This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels
"""

"""
Angelika RAG Data Collector v3.0
================================
Pure web scraping - NO mock data, only real content from the web.

Collects information about:
- Angelique novel series by Anne & Serge Golon
- Film adaptations, actors
- Historical context
- Fan communities

All content scraped from real sources and translated to Czech.
"""

import os
import sys
import json
import hashlib
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/angelika_rag_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
RAG_DB_PATH = os.environ.get("RAG_DB_PATH", "/home/puzik/angelika_rag")
OUTPUT_DIR = Path(RAG_DB_PATH)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# PostgreSQL for CDB logging
PG_CONFIG = {
    "host": "192.168.10.35",
    "port": 5433,
    "database": "almquist_cdb",
    "user": "maj",
    "password": "maj_central_2024"
}

@dataclass
class RagDocument:
    """RAG document structure"""
    id: str
    title: str
    content_cs: str
    source_url: str
    source_type: str
    category: str
    tags: List[str]
    language_original: str
    collected_at: str
    metadata: Dict[str, Any]


class AngelikaRagCollector:
    """Pure web scraping collector - no mock data"""

    VERSION = "3.0.0"

    # Target URLs to scrape - real sources only
    TARGET_URLS = [
        # Wikipedia - main articles
        ("https://en.wikipedia.org/wiki/Ang%C3%A9lique_(novel_series)", "books", ["series", "novels"]),
        ("https://en.wikipedia.org/wiki/Anne_Golon", "author", ["anne_golon", "biography"]),
        ("https://en.wikipedia.org/wiki/Mich%C3%A8le_Mercier", "films", ["michele_mercier", "actress"]),
        ("https://en.wikipedia.org/wiki/Robert_Hossein", "films", ["robert_hossein", "actor"]),
        ("https://fr.wikipedia.org/wiki/Ang%C3%A9lique,_marquise_des_anges", "books", ["series", "french"]),
        ("https://fr.wikipedia.org/wiki/Anne_Golon", "author", ["anne_golon", "french"]),
        ("https://fr.wikipedia.org/wiki/Ang%C3%A9lique_(s%C3%A9rie_de_films)", "films", ["films", "french"]),
        ("https://de.wikipedia.org/wiki/Ang%C3%A9lique_(Roman)", "books", ["series", "german"]),
        ("https://ru.wikipedia.org/wiki/%D0%90%D0%BD%D0%B6%D0%B5%D0%BB%D0%B8%D0%BA%D0%B0_(%D1%80%D0%BE%D0%BC%D0%B0%D0%BD)", "books", ["series", "russian"]),
        ("https://pl.wikipedia.org/wiki/Angelika_(seria_powie%C5%9Bci)", "books", ["series", "polish"]),

        # Historical context
        ("https://en.wikipedia.org/wiki/Louis_XIV", "history", ["louis_xiv", "france"]),
        ("https://en.wikipedia.org/wiki/Palace_of_Versailles", "history", ["versailles", "court"]),
        ("https://en.wikipedia.org/wiki/Fronde", "history", ["fronde", "rebellion"]),
        ("https://en.wikipedia.org/wiki/Affair_of_the_Poisons", "history", ["poisons", "scandal"]),
        ("https://en.wikipedia.org/wiki/Edict_of_Fontainebleau", "history", ["huguenots", "persecution"]),
        ("https://en.wikipedia.org/wiki/Barbary_pirates", "history", ["pirates", "slavery"]),
        ("https://en.wikipedia.org/wiki/Moulay_Ismail_Ibn_Sharif", "history", ["morocco", "sultan"]),
        ("https://en.wikipedia.org/wiki/New_France", "history", ["quebec", "colonies"]),

        # 17th century life
        ("https://en.wikipedia.org/wiki/Fashion_in_the_1660s%E2%80%931700s_in_Western_European_fashion", "history", ["fashion", "costume"]),
        ("https://en.wikipedia.org/wiki/History_of_chocolate_in_France", "history", ["chocolate", "trade"]),
        ("https://en.wikipedia.org/wiki/Grasse", "history", ["perfume", "grasse"]),
        ("https://en.wikipedia.org/wiki/Toulouse", "history", ["toulouse", "languedoc"]),
        ("https://en.wikipedia.org/wiki/Poitou", "history", ["poitou", "region"]),

        # Films
        ("https://en.wikipedia.org/wiki/Ang%C3%A9lique,_Marquise_des_Anges_(1964_film)", "films", ["film_1964"]),
        ("https://en.wikipedia.org/wiki/Merveilleuse_Ang%C3%A9lique", "films", ["film_1965"]),
        ("https://en.wikipedia.org/wiki/Ang%C3%A9lique_and_the_King", "films", ["film_1966"]),
        ("https://en.wikipedia.org/wiki/Untamable_Ang%C3%A9lique", "films", ["film_1967"]),
        ("https://en.wikipedia.org/wiki/Ang%C3%A9lique_and_the_Sultan", "films", ["film_1968"]),
    ]

    # Search queries for additional content
    SEARCH_QUERIES = [
        # Czech
        ("Angelika markýza andělů Anne Golon knihy", "books", ["czech"]),
        ("Michele Mercier Angelika film herečka", "films", ["czech"]),
        # English
        ("Anne Golon Angelique author interview biography", "author", ["interview"]),
        ("Angelique novel series fan club community", "fandom", ["fan_club"]),
        ("Angelique Marquise of Angels book review", "books", ["review"]),
        # French
        ("Anne Golon écrivain Angélique biographie", "author", ["french"]),
        ("Angélique marquise des anges série complète", "books", ["french"]),
        # German
        ("Angelika Roman Anne Golon Buchserie", "books", ["german"]),
        # Russian
        ("Анжелика маркиза ангелов Анн Голон", "books", ["russian"]),
        # Historical
        ("17th century France daily life customs", "history", ["daily_life"]),
        ("Louis XIV Versailles court etiquette", "history", ["versailles"]),
        ("Barbary corsairs European slaves Morocco", "history", ["pirates"]),
    ]

    def __init__(self):
        self.documents: List[RagDocument] = []
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 AngelikaRAG/3.0"
        })
        self.seen_urls: set = set()
        self.stats = {"scraped": 0, "failed": 0, "translated": 0}

    def scrape_url(self, url: str) -> Optional[Dict]:
        """Scrape content from a URL"""
        if url in self.seen_urls:
            return None
        self.seen_urls.add(url)

        try:
            response = self.session.get(url, timeout=30)
            if response.status_code != 200:
                logger.warning(f"HTTP {response.status_code}: {url}")
                self.stats["failed"] += 1
                return None

            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove unwanted elements
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside',
                            'noscript', 'iframe', 'svg', 'img', 'button', 'input']):
                tag.decompose()

            # Remove Wikipedia-specific elements
            for selector in ['.mw-editsection', '.reference', '.reflist',
                           '.navbox', '.sistersitebox', '.noprint', '.mw-empty-elt',
                           '#toc', '.toc', '.hatnote', '.mw-indicators']:
                for el in soup.select(selector):
                    el.decompose()

            # Get title
            title = ""
            if soup.title:
                title = soup.title.get_text(strip=True)
            if not title:
                h1 = soup.find('h1')
                if h1:
                    title = h1.get_text(strip=True)

            # Get main content - prioritize article content
            content = ""
            for selector in ['#mw-content-text', 'article', 'main', '.content', '#content']:
                main = soup.select_one(selector)
                if main:
                    content = main.get_text(separator='\n', strip=True)
                    break

            if not content:
                body = soup.find('body')
                if body:
                    content = body.get_text(separator='\n', strip=True)

            # Clean up content
            lines = []
            for line in content.split('\n'):
                line = line.strip()
                if line and len(line) > 20:  # Skip very short lines
                    lines.append(line)
            content = '\n'.join(lines)

            # Limit length
            if len(content) > 30000:
                content = content[:30000]

            if len(content) < 500:
                logger.warning(f"Content too short ({len(content)} chars): {url}")
                return None

            self.stats["scraped"] += 1
            return {
                "url": url,
                "title": title[:200] if title else urlparse(url).netloc,
                "content": content,
                "scraped_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            self.stats["failed"] += 1
            return None

    def search_duckduckgo(self, query: str, max_results: int = 5) -> List[str]:
        """Search DuckDuckGo and return URLs"""
        urls = []
        try:
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            response = self.session.get(search_url, timeout=30)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                for link in soup.select('a.result__a')[:max_results]:
                    href = link.get('href', '')
                    if href and href.startswith('http'):
                        # Skip unwanted domains
                        if not any(skip in href for skip in ['youtube.com', 'facebook.com',
                                  'twitter.com', 'instagram.com', 'amazon.com', 'ebay.com']):
                            urls.append(href)

            time.sleep(3)  # Rate limiting

        except Exception as e:
            logger.warning(f"Search failed for '{query}': {e}")

        return urls

    def detect_language(self, text: str) -> str:
        """Detect language of text"""
        sample = text.lower()[:3000]

        # Check for specific characters
        if any(c in sample for c in 'áčďéěíňóřšťúůýž'):
            return 'cs'
        if any('\u0400' <= c <= '\u04FF' for c in sample):
            return 'ru'
        if any(c in sample for c in 'äöüß'):
            return 'de'
        if any(c in sample for c in 'ąćęłńóśźż'):
            return 'pl'

        # Check for language-specific words
        indicators = {
            'fr': [' le ', ' la ', ' les ', ' de ', ' du ', ' des ', ' et ', ' est ', " l'", " d'"],
            'de': [' der ', ' die ', ' das ', ' und ', ' ist ', ' ein ', ' eine ', ' auf ', ' mit '],
            'en': [' the ', ' is ', ' are ', ' was ', ' and ', ' for ', ' with ', ' that '],
            'cs': [' je ', ' se ', ' na ', ' že ', ' jako ', ' ale ', ' jsou ', ' byl '],
            'pl': [' jest ', ' się ', ' nie ', ' na ', ' do ', ' to ', ' w '],
        }

        scores = {}
        for lang, words in indicators.items():
            scores[lang] = sum(1 for w in words if w in sample)

        if max(scores.values()) > 3:
            return max(scores, key=scores.get)
        return 'en'

    def translate_to_czech(self, text: str, source_lang: str) -> str:
        """Translate to Czech using Ollama"""
        if source_lang == 'cs' or len(text) < 200:
            return text

        # Truncate for translation
        text = text[:10000]

        lang_names = {
            'en': 'angličtiny', 'fr': 'francouzštiny', 'de': 'němčiny',
            'ru': 'ruštiny', 'pl': 'polštiny', 'es': 'španělštiny'
        }
        lang_name = lang_names.get(source_lang, 'angličtiny')

        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "qwen2.5:14b",
                    "prompt": f"Přelož následující text z {lang_name} do češtiny. Zachovej formátování. Vrať POUZE překlad:\n\n{text}",
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 8000}
                },
                timeout=180
            )
            if response.status_code == 200:
                result = response.json().get("response", "").strip()
                if len(result) > 100:
                    self.stats["translated"] += 1
                    return result
        except Exception as e:
            logger.warning(f"Translation failed: {e}")

        return text

    def add_document(self, title: str, content: str, url: str,
                     category: str, tags: List[str], lang: str, metadata: Dict = None):
        """Add a scraped document"""

        # Translate if needed
        content_cs = self.translate_to_czech(content, lang)

        doc_id = hashlib.md5(f"{url}".encode()).hexdigest()[:16]

        doc = RagDocument(
            id=doc_id,
            title=title,
            content_cs=content_cs,
            source_url=url,
            source_type="web_scrape",
            category=category,
            tags=tags + [f"lang_{lang}"],
            language_original=lang,
            collected_at=datetime.now().isoformat(),
            metadata=metadata or {}
        )

        self.documents.append(doc)
        logger.info(f"Added: {title[:60]}... ({lang}→cs)")

    def scrape_target_urls(self):
        """Scrape all target URLs"""
        logger.info(f"=== Scraping {len(self.TARGET_URLS)} target URLs ===")

        for url, category, tags in self.TARGET_URLS:
            data = self.scrape_url(url)
            if data:
                lang = self.detect_language(data['content'])
                self.add_document(
                    title=data['title'],
                    content=data['content'],
                    url=data['url'],
                    category=category,
                    tags=tags,
                    lang=lang,
                    metadata={"scraped_at": data['scraped_at']}
                )
            time.sleep(1)

    def search_and_scrape(self):
        """Search and scrape additional content"""
        logger.info(f"=== Searching with {len(self.SEARCH_QUERIES)} queries ===")

        for query, category, tags in self.SEARCH_QUERIES:
            logger.info(f"Searching: {query[:50]}...")
            urls = self.search_duckduckgo(query, max_results=3)

            for url in urls:
                if url in self.seen_urls:
                    continue

                data = self.scrape_url(url)
                if data:
                    lang = self.detect_language(data['content'])
                    self.add_document(
                        title=data['title'],
                        content=data['content'],
                        url=data['url'],
                        category=category,
                        tags=tags + ["search_result"],
                        lang=lang,
                        metadata={"query": query, "scraped_at": data['scraped_at']}
                    )
                time.sleep(1)

    def save_to_rag(self) -> Path:
        """Save collected documents to RAG database"""
        output_file = OUTPUT_DIR / "angelika_rag.json"

        docs_dict = [asdict(doc) for doc in self.documents]

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(docs_dict, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(self.documents)} documents to {output_file}")

        # Save index
        index_file = OUTPUT_DIR / "angelika_rag_index.json"
        index = {
            "version": self.VERSION,
            "total_documents": len(self.documents),
            "categories": {},
            "languages": {},
            "stats": self.stats,
            "collected_at": datetime.now().isoformat(),
        }

        for doc in self.documents:
            index["categories"][doc.category] = index["categories"].get(doc.category, 0) + 1
            index["languages"][doc.language_original] = index["languages"].get(doc.language_original, 0) + 1

        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

        return output_file

    def log_to_cdb(self, status: str, stats: Dict):
        """Log collection event to CDB"""
        try:
            import psycopg2

            conn = psycopg2.connect(**PG_CONFIG)
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO events (event_type, component, version, "user", machine, status, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                "rag_collection",
                "angelika_rag_collector",
                self.VERSION,
                "maj",
                os.uname().nodename,
                status,
                json.dumps(stats, ensure_ascii=False)
            ))

            conn.commit()
            conn.close()
            logger.info(f"Logged to CDB: {status}")

        except Exception as e:
            logger.warning(f"CDB logging failed: {e}")

    def run(self):
        """Run the full collection process"""
        start_time = datetime.now()
        logger.info("=" * 60)
        logger.info(f"ANGELIKA RAG COLLECTOR v{self.VERSION}")
        logger.info("Pure web scraping - NO mock data")
        logger.info("=" * 60)

        # Scrape target URLs
        self.scrape_target_urls()

        # Search and scrape additional content
        self.search_and_scrape()

        # Save results
        output_file = self.save_to_rag()

        # Calculate final stats
        duration = (datetime.now() - start_time).total_seconds()
        final_stats = {
            "version": self.VERSION,
            "total_documents": len(self.documents),
            "scraped": self.stats["scraped"],
            "failed": self.stats["failed"],
            "translated": self.stats["translated"],
            "categories": len(set(d.category for d in self.documents)),
            "duration_seconds": round(duration, 1),
            "output_file": str(output_file),
        }

        # Log to CDB
        self.log_to_cdb("completed", final_stats)

        logger.info("=" * 60)
        logger.info(f"COMPLETED in {duration:.1f}s")
        logger.info(f"Documents: {final_stats['total_documents']}")
        logger.info(f"Scraped: {self.stats['scraped']}, Failed: {self.stats['failed']}, Translated: {self.stats['translated']}")
        logger.info("=" * 60)

        return final_stats


if __name__ == "__main__":
    collector = AngelikaRagCollector()
    stats = collector.run()
    print(json.dumps(stats, indent=2))
