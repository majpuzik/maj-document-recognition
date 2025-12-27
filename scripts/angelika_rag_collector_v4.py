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
Angelika RAG Data Collector v4.0
================================
Pure web scraping - NO translation.
Translation handled by distributed_translator.py workers.
"""

import os
import sys
import json
import hashlib
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

RAG_DB_PATH = os.environ.get("RAG_DB_PATH", "/tmp/angelika_rag")
OUTPUT_DIR = Path(RAG_DB_PATH)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PG_CONFIG = {
    "host": "192.168.10.35",
    "port": 5433,
    "database": "almquist_cdb",
    "user": "maj",
    "password": "maj_central_2024"
}


class AngelikaRagCollectorV4:
    """Web scraping only - no translation (uses distributed system)"""

    VERSION = "4.0.0"

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

        # Additional 17th century context
        ("https://en.wikipedia.org/wiki/French_cuisine", "history", ["cuisine", "food"]),
        ("https://en.wikipedia.org/wiki/History_of_medicine", "history", ["medicine", "17th_century"]),
        ("https://en.wikipedia.org/wiki/Absolutism_(European_history)", "history", ["absolutism", "politics"]),
        ("https://en.wikipedia.org/wiki/Atlantic_slave_trade", "history", ["slavery", "trade"]),
        ("https://en.wikipedia.org/wiki/Huguenots", "history", ["huguenots", "protestants"]),
        ("https://en.wikipedia.org/wiki/French_colonial_empire", "history", ["colonies", "empire"]),
    ]

    SEARCH_QUERIES = [
        ("Angelika markýza andělů Anne Golon knihy", "books", ["czech"]),
        ("Michele Mercier Angelika film herečka", "films", ["czech"]),
        ("Anne Golon Angelique author interview biography", "author", ["interview"]),
        ("Angelique novel series fan club community", "fandom", ["fan_club"]),
        ("Angelique Marquise of Angels book review", "books", ["review"]),
        ("Anne Golon écrivain Angélique biographie", "author", ["french"]),
        ("Angélique marquise des anges série complète", "books", ["french"]),
        ("Angelika Roman Anne Golon Buchserie", "books", ["german"]),
        ("Анжелика маркиза ангелов Анн Голон", "books", ["russian"]),
        ("17th century France daily life customs", "history", ["daily_life"]),
        ("Louis XIV Versailles court etiquette", "history", ["versailles"]),
        ("Barbary corsairs European slaves Morocco", "history", ["pirates"]),
        ("17th century French fashion clothing", "history", ["fashion"]),
        ("French perfume history Grasse 17th century", "history", ["perfume"]),
    ]

    def __init__(self, add_to_queue: bool = True):
        self.documents = []
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AngelikaRAG/4.0"
        })
        self.seen_urls = set()
        self.add_to_queue = add_to_queue
        self.pg_conn = None
        self.stats = {"scraped": 0, "failed": 0, "queued": 0}

    def get_pg_connection(self):
        if not self.pg_conn:
            import psycopg2
            self.pg_conn = psycopg2.connect(**PG_CONFIG)
        return self.pg_conn

    def scrape_url(self, url: str) -> Optional[Dict]:
        """Scrape content from URL"""
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

            for selector in ['.mw-editsection', '.reference', '.reflist',
                           '.navbox', '.sistersitebox', '.noprint', '.mw-empty-elt',
                           '#toc', '.toc', '.hatnote', '.mw-indicators']:
                for el in soup.select(selector):
                    el.decompose()

            title = ""
            if soup.title:
                title = soup.title.get_text(strip=True)
            if not title:
                h1 = soup.find('h1')
                if h1:
                    title = h1.get_text(strip=True)

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

            lines = [line.strip() for line in content.split('\n') if line.strip() and len(line.strip()) > 20]
            content = '\n'.join(lines)

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

    def detect_language(self, text: str) -> str:
        """Detect language"""
        sample = text.lower()[:3000]

        if any(c in sample for c in 'áčďéěíňóřšťúůýž'):
            return 'cs'
        if any('\u0400' <= c <= '\u04FF' for c in sample):
            return 'ru'
        if any(c in sample for c in 'äöüß'):
            return 'de'
        if any(c in sample for c in 'ąćęłńóśźż'):
            return 'pl'

        indicators = {
            'fr': [' le ', ' la ', ' les ', ' de ', ' du ', ' des ', ' et ', ' est '],
            'de': [' der ', ' die ', ' das ', ' und ', ' ist ', ' ein ', ' eine '],
            'en': [' the ', ' is ', ' are ', ' was ', ' and ', ' for ', ' with '],
            'cs': [' je ', ' se ', ' na ', ' že ', ' jako ', ' ale ', ' jsou '],
            'pl': [' jest ', ' się ', ' nie ', ' na ', ' do ', ' to ', ' w '],
        }

        scores = {lang: sum(1 for w in words if w in sample) for lang, words in indicators.items()}
        if max(scores.values()) > 3:
            return max(scores, key=scores.get)
        return 'en'

    def search_duckduckgo(self, query: str, max_results: int = 5) -> List[str]:
        """Search DuckDuckGo"""
        urls = []
        try:
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            response = self.session.get(search_url, timeout=30)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                for link in soup.select('a.result__a')[:max_results]:
                    href = link.get('href', '')
                    if href and href.startswith('http'):
                        if not any(skip in href for skip in ['youtube.com', 'facebook.com',
                                  'twitter.com', 'instagram.com', 'amazon.com', 'ebay.com']):
                            urls.append(href)

            time.sleep(3)
        except Exception as e:
            logger.warning(f"Search failed: {e}")

        return urls

    def add_to_translation_queue(self, title: str, content: str, lang: str,
                                  category: str, tags: List[str], url: str):
        """Add document to distributed translation queue"""
        if lang == 'cs':
            # Already Czech - save directly
            self.documents.append({
                'title': title,
                'content': content,
                'content_cs': content,
                'language': lang,
                'category': category,
                'tags': tags,
                'url': url,
                'needs_translation': False
            })
            return

        try:
            conn = self.get_pg_connection()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO translation_queue
                (source_text, source_lang, category, tags, metadata)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                content,
                lang,
                category,
                json.dumps(tags),
                json.dumps({'title': title, 'url': url, 'scraped_at': datetime.now().isoformat()})
            ))

            task_id = cur.fetchone()[0]
            conn.commit()

            self.stats["queued"] += 1
            logger.info(f"Queued for translation: #{task_id} [{lang}] {title[:50]}...")

            # Also save original
            self.documents.append({
                'title': title,
                'content': content,
                'content_cs': None,
                'language': lang,
                'category': category,
                'tags': tags,
                'url': url,
                'needs_translation': True,
                'queue_id': task_id
            })

        except Exception as e:
            logger.error(f"Failed to queue: {e}")
            # Fallback - save without translation
            self.documents.append({
                'title': title,
                'content': content,
                'content_cs': content,
                'language': lang,
                'category': category,
                'tags': tags,
                'url': url,
                'needs_translation': True,
                'error': str(e)
            })

    def scrape_target_urls(self):
        """Scrape all target URLs"""
        logger.info(f"=== Scraping {len(self.TARGET_URLS)} target URLs ===")

        for url, category, tags in self.TARGET_URLS:
            data = self.scrape_url(url)
            if data:
                lang = self.detect_language(data['content'])

                if self.add_to_queue and lang != 'cs':
                    self.add_to_translation_queue(
                        title=data['title'],
                        content=data['content'],
                        lang=lang,
                        category=category,
                        tags=tags,
                        url=data['url']
                    )
                else:
                    self.documents.append({
                        'title': data['title'],
                        'content': data['content'],
                        'content_cs': data['content'] if lang == 'cs' else None,
                        'language': lang,
                        'category': category,
                        'tags': tags,
                        'url': data['url'],
                        'needs_translation': lang != 'cs'
                    })
                    logger.info(f"Scraped: [{lang}] {data['title'][:50]}...")

            time.sleep(1)

    def search_and_scrape(self):
        """Search and scrape additional content"""
        logger.info(f"=== Searching {len(self.SEARCH_QUERIES)} queries ===")

        for query, category, tags in self.SEARCH_QUERIES:
            logger.info(f"Searching: {query[:50]}...")
            urls = self.search_duckduckgo(query, max_results=3)

            for url in urls:
                if url in self.seen_urls:
                    continue

                data = self.scrape_url(url)
                if data:
                    lang = self.detect_language(data['content'])

                    if self.add_to_queue and lang != 'cs':
                        self.add_to_translation_queue(
                            title=data['title'],
                            content=data['content'],
                            lang=lang,
                            category=category,
                            tags=tags + ["search_result"],
                            url=data['url']
                        )
                    else:
                        self.documents.append({
                            'title': data['title'],
                            'content': data['content'],
                            'content_cs': data['content'] if lang == 'cs' else None,
                            'language': lang,
                            'category': category,
                            'tags': tags + ["search_result"],
                            'url': data['url'],
                            'needs_translation': lang != 'cs'
                        })

                time.sleep(1)

    def save_results(self):
        """Save scraped documents"""
        output_file = OUTPUT_DIR / "angelika_scraped.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.documents, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(self.documents)} documents to {output_file}")

        # Index
        index_file = OUTPUT_DIR / "angelika_scraped_index.json"
        index = {
            "version": self.VERSION,
            "total_documents": len(self.documents),
            "stats": self.stats,
            "by_language": {},
            "by_category": {},
            "collected_at": datetime.now().isoformat()
        }

        for doc in self.documents:
            lang = doc.get('language', 'unknown')
            cat = doc.get('category', 'unknown')
            index["by_language"][lang] = index["by_language"].get(lang, 0) + 1
            index["by_category"][cat] = index["by_category"].get(cat, 0) + 1

        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

        return output_file

    def run(self):
        """Run collection"""
        start = datetime.now()
        logger.info("=" * 60)
        logger.info(f"ANGELIKA RAG COLLECTOR v{self.VERSION}")
        logger.info("Scraping only - translations via distributed system")
        logger.info("=" * 60)

        self.scrape_target_urls()
        self.search_and_scrape()
        output = self.save_results()

        duration = (datetime.now() - start).total_seconds()
        logger.info("=" * 60)
        logger.info(f"COMPLETED in {duration:.1f}s")
        logger.info(f"Scraped: {self.stats['scraped']}, Failed: {self.stats['failed']}, Queued: {self.stats['queued']}")
        logger.info("=" * 60)

        if self.pg_conn:
            self.pg_conn.close()

        return {
            "version": self.VERSION,
            "documents": len(self.documents),
            "stats": self.stats,
            "duration": duration,
            "output": str(output)
        }


if __name__ == "__main__":
    collector = AngelikaRagCollectorV4(add_to_queue=True)
    stats = collector.run()
    print(json.dumps(stats, indent=2))
