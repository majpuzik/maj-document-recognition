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
Angelika RAG Data Collector v1.0
================================
Comprehensive data collection about:
- Angelika (novel character by Anne & Serge Golon)
- Authors Anne Golon (Simone Changeux) and Serge Golon (Vsevolod Goloubinoff)
- Film adaptations and actors (Michèle Mercier, Robert Hossein)
- Historical figures and connections
- Fan clubs and communities
- Unpublished works (Prague storyline)

Collects from web, translates to Czech, stores in RAG database.
"""

import os
import sys
import json
import hashlib
import logging
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from urllib.parse import quote_plus, urlparse

import requests

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
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
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
    content: str
    content_cs: str  # Czech translation
    source_url: str
    source_type: str  # web, book, interview, etc.
    category: str  # character, author, film, history, fanclub
    tags: List[str]
    language_original: str
    collected_at: str
    metadata: Dict[str, Any]


class AngelikaRagCollector:
    """Collector for Angelika-related information"""

    # Search topics organized by category
    SEARCH_TOPICS = {
        "author": [
            "Anne Golon writer biography",
            "Anne Golon Simone Changeux life",
            "Serge Golon Vsevolod Goloubinoff biography",
            "Anne Golon interview",
            "Anne Golon death 2017",
            "Golon family history",
            "Anne Golon writing process Angelique",
            "Anne Golon unpublished manuscripts",
            "Serge Golon historian researcher",
        ],
        "character": [
            "Angelique Marquise des Anges character analysis",
            "Angelique de Sancé de Monteloup biography fictional",
            "Joffrey de Peyrac character",
            "Angelique novel series plot summary",
            "Angelique books chronology",
            "Angelique character development",
            "Angelique feminist heroine 17th century",
        ],
        "books": [
            "Angelique Marquise des Anges book series complete",
            "Angelique novels publication history",
            "Angelique book Prague unpublished",
            "Angelique tome 14 Prague",
            "Angelique series new editions",
            "Angelique books translations",
            "Angelique original vs revised editions",
        ],
        "films": [
            "Angelique film series 1964 Michele Mercier",
            "Michele Mercier Angelique actress biography",
            "Robert Hossein Joffrey de Peyrac actor",
            "Angelique films Bernard Borderie director",
            "Angelique movie cast complete",
            "Angelique film locations",
            "Angelique film costumes",
            "Angelique movie soundtrack Michel Magne",
            "Angelique films box office success",
        ],
        "history": [
            "Louis XIV court historical Angelique",
            "17th century France Angelique historical accuracy",
            "Joffrey de Peyrac historical inspiration",
            "Angelique real historical figures",
            "Comte de Peyrac Toulouse alchemy",
            "Marquise de Montespan Angelique",
            "Nicolas Fouquet Angelique novels",
        ],
        "fanclub": [
            "Angelique fan club international",
            "Angelique fans community",
            "Angelique Marquise des Anges forum",
            "Angelique collectors editions",
            "Angelique merchandise memorabilia",
            "Anne Golon fan sites",
        ],
        "legacy": [
            "Angelique novels influence literature",
            "Angelique TV series adaptation plans",
            "Angelique remake 2013",
            "Angelique cultural impact France",
            "Angelique translations worldwide sales",
        ],
    }

    # Czech search topics
    SEARCH_TOPICS_CS = {
        "czech": [
            "Angelika Markýza andělů česky",
            "Anne Golon knihy česky",
            "Angelika romány český překlad",
            "Angelika filmy česká televize",
            "Michele Mercier Angelika",
            "Angelika Praha pokračování",
        ]
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AngelikaRAG/1.0"
        })
        self.collected_docs: List[RagDocument] = []
        self.seen_urls = set()

    def search_web(self, query: str, num_results: int = 10) -> List[Dict]:
        """Search web using DuckDuckGo HTML"""
        results = []
        try:
            # DuckDuckGo HTML search
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                # Parse results from HTML
                from html.parser import HTMLParser

                class DDGParser(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.results = []
                        self.in_result = False
                        self.current = {}

                    def handle_starttag(self, tag, attrs):
                        attrs_dict = dict(attrs)
                        if tag == 'a' and 'result__a' in attrs_dict.get('class', ''):
                            self.in_result = True
                            self.current = {'url': attrs_dict.get('href', '')}
                        if tag == 'a' and 'result__snippet' in attrs_dict.get('class', ''):
                            self.current['snippet_start'] = True

                    def handle_data(self, data):
                        if self.in_result and 'title' not in self.current:
                            self.current['title'] = data.strip()
                        if self.current.get('snippet_start'):
                            self.current['snippet'] = self.current.get('snippet', '') + data

                    def handle_endtag(self, tag):
                        if tag == 'a' and self.in_result and self.current.get('url'):
                            if self.current.get('title'):
                                self.results.append(self.current)
                            self.in_result = False
                            self.current = {}

                parser = DDGParser()
                parser.feed(response.text)
                results = parser.results[:num_results]

        except Exception as e:
            logger.warning(f"Search failed for '{query}': {e}")

        return results

    def fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch and extract text content from URL"""
        if url in self.seen_urls:
            return None
        self.seen_urls.add(url)

        try:
            response = self.session.get(url, timeout=30)
            if response.status_code != 200:
                return None

            # Simple HTML to text extraction
            html = response.text

            # Remove scripts and styles
            html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)

            # Extract text
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()

            # Limit length
            if len(text) > 50000:
                text = text[:50000]

            return text if len(text) > 200 else None

        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None

    def detect_language(self, text: str) -> str:
        """Simple language detection"""
        # Czech indicators
        czech_chars = set('áčďéěíňóřšťúůýž')
        czech_words = {'a', 'je', 'se', 'na', 'to', 'že', 'jako', 'ale', 'jsou', 'byl', 'byla'}

        # French indicators
        french_words = {'le', 'la', 'les', 'de', 'du', 'des', 'et', 'est', 'un', 'une', 'que', 'qui'}

        # German indicators
        german_words = {'der', 'die', 'das', 'und', 'ist', 'ein', 'eine', 'auf', 'mit', 'für'}

        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))

        # Check Czech characters
        if any(c in czech_chars for c in text_lower):
            return 'cs'

        # Count word matches
        cs_count = len(words & czech_words)
        fr_count = len(words & french_words)
        de_count = len(words & german_words)

        if fr_count > max(cs_count, de_count, 3):
            return 'fr'
        if de_count > max(cs_count, fr_count, 3):
            return 'de'
        if cs_count > 3:
            return 'cs'

        return 'en'

    def translate_to_czech(self, text: str, source_lang: str) -> str:
        """Translate text to Czech using Ollama"""
        if source_lang == 'cs':
            return text

        if len(text) > 8000:
            text = text[:8000]

        lang_names = {
            'en': 'angličtiny',
            'fr': 'francouzštiny',
            'de': 'němčiny',
            'es': 'španělštiny',
            'it': 'italštiny',
        }

        lang_name = lang_names.get(source_lang, 'angličtiny')

        prompt = f"""Přelož následující text z {lang_name} do češtiny. Zachovej význam a styl originálu.
Vrať POUZE překlad, nic jiného.

Text k překladu:
{text}

Český překlad:"""

        try:
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": "qwen2.5:32b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3}
                },
                timeout=120
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", text).strip()

        except Exception as e:
            logger.warning(f"Translation failed: {e}")

        return text

    def create_document(
        self,
        title: str,
        content: str,
        source_url: str,
        source_type: str,
        category: str,
        tags: List[str],
        metadata: Dict = None
    ) -> RagDocument:
        """Create a RAG document with translation"""

        # Detect language and translate
        lang = self.detect_language(content)
        content_cs = self.translate_to_czech(content, lang) if lang != 'cs' else content

        # Generate ID
        doc_id = hashlib.md5(f"{source_url}{title}".encode()).hexdigest()[:16]

        doc = RagDocument(
            id=doc_id,
            title=title,
            content=content,
            content_cs=content_cs,
            source_url=source_url,
            source_type=source_type,
            category=category,
            tags=tags,
            language_original=lang,
            collected_at=datetime.now().isoformat(),
            metadata=metadata or {}
        )

        return doc

    def collect_category(self, category: str, topics: List[str]):
        """Collect documents for a category"""
        logger.info(f"=== Collecting category: {category} ===")

        for topic in topics:
            logger.info(f"Searching: {topic}")
            results = self.search_web(topic, num_results=8)

            for result in results:
                url = result.get('url', '')
                title = result.get('title', '')

                if not url or not title:
                    continue

                # Skip already seen
                if url in self.seen_urls:
                    continue

                logger.info(f"  Fetching: {title[:50]}...")
                content = self.fetch_page_content(url)

                if content and len(content) > 500:
                    # Determine tags based on content
                    tags = [category]
                    content_lower = content.lower()

                    if 'mercier' in content_lower or 'michele' in content_lower:
                        tags.append('michele_mercier')
                    if 'hossein' in content_lower or 'robert' in content_lower:
                        tags.append('robert_hossein')
                    if 'golon' in content_lower or 'anne' in content_lower:
                        tags.append('anne_golon')
                    if 'peyrac' in content_lower or 'joffrey' in content_lower:
                        tags.append('joffrey_peyrac')
                    if 'prague' in content_lower or 'praha' in content_lower:
                        tags.append('prague_story')
                    if 'louis' in content_lower and 'xiv' in content_lower:
                        tags.append('louis_xiv')
                    if 'film' in content_lower or 'movie' in content_lower:
                        tags.append('film')

                    doc = self.create_document(
                        title=title,
                        content=content,
                        source_url=url,
                        source_type='web',
                        category=category,
                        tags=list(set(tags)),
                        metadata={'search_query': topic}
                    )

                    self.collected_docs.append(doc)
                    logger.info(f"  Collected: {doc.id} ({doc.language_original}→cs)")

            # Rate limiting
            time.sleep(2)

    def add_static_knowledge(self):
        """Add curated static knowledge about Angelika"""

        static_docs = [
            {
                "title": "Angelika - Přehled románové série",
                "content": """
Angelika, markýza andělů (Angélique, Marquise des Anges) je série třinácti historických románů
od autorské dvojice Anne a Serge Golon. Série vypráví příběh krásné a odvážné Angeliky de Sancé
de Monteloup v 17. století za vlády Ludvíka XIV.

SEZNAM KNIH:
1. Angelika, markýza andělů (1957)
2. Cesta do Versailles (1958)
3. Angelika a král (1959)
4. Nezkrotná Angelika (1960)
5. Angelika a její láska (1961)
6. Angelika a Nový svět (1964)
7. Angelika v pokušení (1964)
8. Angelika a démon (1965)
9. Angelika a její vítězství (1965)
10. Angelika a spiknutí stínů (1976)
11. Angelika v Quebecu (1980)
12. Cesta naděje (1984)
13. Vítězství Angeliky (1985)

NEVYDANÝ DÍL:
Anne Golon pracovala na 14. dílu, který se měl odehrávat v Praze. Rukopis zůstal nedokončen
po její smrti v roce 2017.

HLAVNÍ POSTAVY:
- Angelika de Sancé de Monteloup - hlavní hrdinka, dcera zchudlého barona z Poitou
- Joffrey de Peyrac - hrabě z Toulouse, alchymista a učenec, Angelin manžel
- Ludvík XIV. - francouzský král, Slunečný král
- Madame de Montespan - králova milenka, Angelina rivalka
- Nicolas Fouquet - superintendent financí, Angelin obdivovatel
                """,
                "category": "books",
                "tags": ["books", "series", "overview"],
            },
            {
                "title": "Anne Golon - Životopis autorky",
                "content": """
Anne Golon (vlastním jménem Simone Changeux, 1921-2017) byla francouzská spisovatelka,
která společně se svým manželem Sergejem Golonem vytvořila románovou sérii o Angelice.

ŽIVOTOPIS:
- Narozena 17. prosince 1921 ve Versailles
- Studovala chemii a historii
- 1947 se provdala za Vsevoloda Sergejeviče Goloubinoffa (Serge Golon)
- Manželé měli čtyři děti
- Serge Golon zemřel v roce 1972
- Anne pokračovala v psaní sama až do své smrti 14. července 2017

TVORBA:
Anne prováděla rozsáhlý historický výzkum pro romány. Serge, původem ruský emigrant
a geolog, přispíval vědeckými a historickými detaily. Po jeho smrti Anne přepsala
celou sérii a vydala rozšířené "definitivní" verze.

AUTORSKÁ PRÁVA:
Anne vedla dlouhé právní spory s vydavateli o autorská práva k sérii.
Teprve v 90. letech získala plnou kontrolu nad svým dílem.

NEDOKONČENÉ DÍLO:
V době smrti pracovala na pokračování série - 14. díl se měl odehrávat v Praze
během třicetileté války. Rukopis zůstal nedokončen.
                """,
                "category": "author",
                "tags": ["anne_golon", "biography", "author"],
            },
            {
                "title": "Filmové adaptace Angeliky",
                "content": """
V letech 1964-1968 vzniklo pět francouzských filmů podle románů o Angelice.

FILMY:
1. Angelika, markýza andělů (1964) - režie Bernard Borderie
2. Báječná Angelika (1965) - Angelika u dvora Ludvíka XIV.
3. Nezkrotná Angelika (1967) - Angelika na Středozemním moři
4. Angelika a sultán (1968) - Angelika v Orientu
5. Angelika a král (1966) - Angelika a Ludvík XIV.

HERCI:
Michèle Mercier (1939-) - Angelika
- Francouzská herečka italského původu
- Ikonická role, která ji proslavila celosvětově
- Natočila více než 60 filmů

Robert Hossein (1927-2020) - Joffrey de Peyrac
- Francouzský herec, režisér a producent
- Narozen jako Robert Hosseinoff v Paříži
- Režíroval spektakulární divadelní inscenace

DALŠÍ OBSAZENÍ:
- Jean Rochefort - Desgrez
- Claude Giraud - Philippe du Plessis
- Jacques Toja - Nicolas Fouquet
- Giuliano Gemma - Nicolas

LOKACE NATÁČENÍ:
Filmy se natáčely ve Francii (zámky v údolí Loiry), Itálii a Tunisku.

REMAKE 2013:
V roce 2013 vznikl remake prvního filmu s Norой Arnezeder v hlavní roli.
Film nebyl komerčně úspěšný.
                """,
                "category": "films",
                "tags": ["films", "michele_mercier", "robert_hossein"],
            },
            {
                "title": "Joffrey de Peyrac - Historické inspirace",
                "content": """
Postava Joffreye de Peyrac je fiktivní, ale inspirovaná několika historickými osobnostmi.

CHARAKTERISTIKA:
- Hrabě z Toulouse
- Alchymista, vědec, básník a hudebník
- Zjizvený v obličeji, ale charismatický
- Bohatý díky dolům na zlato a stříbro
- Obviněn z čarodějnictví a upálen (přežil)

HISTORICKÉ INSPIRACE:
1. Cyrano de Bergerac - básník a šermíř
2. Nicolas Flamel - alchymista
3. Hrabata z Toulouse - historický rod

HISTORICKÝ KONTEXT:
Příběh se odehrává v období:
- Frondy (1648-1653)
- Vlády Ludvíka XIV. (1643-1715)
- Pronásledování hugenotů
- Koloniální expanze do Ameriky

ALCHYMIE V ROMÁNECH:
Peyrac je vylíčen jako osvícený vědec předběhnuvší svou dobu.
Jeho "alchymie" je ve skutečnosti raná chemie a metalurgie.
Jeho továrny na výrobu čokolády a parfémů představují raný kapitalismus.
                """,
                "category": "history",
                "tags": ["joffrey_peyrac", "history", "character"],
            },
            {
                "title": "Angelika v Praze - Nedokončený román",
                "content": """
Anne Golon pracovala před svou smrtí na 14. dílu série, který se měl odehrávat v Praze.

ZNÁMÉ INFORMACE:
- Děj se měl odehrávat během třicetileté války (1618-1648)
- Angelika měla navštívit Prahu a český královský dvůr
- Pravděpodobná návaznost na události z předchozích dílů

HISTORICKÝ KONTEXT PRO ROMÁN:
- Pražská defenestrace (1618) - začátek třicetileté války
- Bitva na Bílé hoře (1620)
- Rudolfinská Praha - alchymie a věda
- Židovské město a Rabbi Löw (golem)
- Císař Rudolf II. a jeho sbírky

SPEKULACE FANOUŠKŮ:
- Peyrac mohl mít kontakty s pražskými alchymisty
- Možné setkání s potomky Rudolfa II.
- Angelika jako špionka nebo diplomatka

STAV RUKOPISU:
Rukopis zůstal nedokončen. Dědicové Anne Golon (její děti)
dosud neoznámili plány na jeho dokončení či vydání.
                """,
                "category": "books",
                "tags": ["prague_story", "unpublished", "books"],
            },
        ]

        for doc_data in static_docs:
            doc = RagDocument(
                id=hashlib.md5(doc_data["title"].encode()).hexdigest()[:16],
                title=doc_data["title"],
                content=doc_data["content"],
                content_cs=doc_data["content"],  # Already in Czech
                source_url="internal://static_knowledge",
                source_type="curated",
                category=doc_data["category"],
                tags=doc_data["tags"],
                language_original="cs",
                collected_at=datetime.now().isoformat(),
                metadata={"source": "curated_knowledge"}
            )
            self.collected_docs.append(doc)
            logger.info(f"Added static: {doc.title}")

    def save_to_rag(self):
        """Save collected documents to RAG database"""

        # Save as JSON
        output_file = OUTPUT_DIR / "angelika_rag_documents.json"

        docs_dict = [asdict(doc) for doc in self.collected_docs]

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(docs_dict, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(self.collected_docs)} documents to {output_file}")

        # Save index
        index_file = OUTPUT_DIR / "angelika_rag_index.json"
        index = {
            "total_documents": len(self.collected_docs),
            "categories": {},
            "tags": {},
            "languages": {},
            "collected_at": datetime.now().isoformat(),
        }

        for doc in self.collected_docs:
            # Count categories
            index["categories"][doc.category] = index["categories"].get(doc.category, 0) + 1
            # Count tags
            for tag in doc.tags:
                index["tags"][tag] = index["tags"].get(tag, 0) + 1
            # Count languages
            index["languages"][doc.language_original] = index["languages"].get(doc.language_original, 0) + 1

        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved index to {index_file}")

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
                "1.0.0",
                "maj",
                "dgx",
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
        logger.info("ANGELIKA RAG COLLECTOR - Starting")
        logger.info("=" * 60)

        # Add static knowledge first
        self.add_static_knowledge()

        # Collect from web by category
        for category, topics in self.SEARCH_TOPICS.items():
            self.collect_category(category, topics)

        # Collect Czech sources
        for category, topics in self.SEARCH_TOPICS_CS.items():
            self.collect_category(category, topics)

        # Save results
        output_file = self.save_to_rag()

        # Calculate stats
        duration = (datetime.now() - start_time).total_seconds()
        stats = {
            "total_documents": len(self.collected_docs),
            "categories": len(set(d.category for d in self.collected_docs)),
            "unique_urls": len(self.seen_urls),
            "duration_seconds": duration,
            "output_file": str(output_file),
        }

        # Log to CDB
        self.log_to_cdb("completed", stats)

        logger.info("=" * 60)
        logger.info(f"COMPLETED: {stats['total_documents']} documents in {duration:.1f}s")
        logger.info(f"Output: {output_file}")
        logger.info("=" * 60)

        return stats


if __name__ == "__main__":
    collector = AngelikaRagCollector()
    stats = collector.run()
    print(json.dumps(stats, indent=2))
