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
Paperless-NGX Full Import with Hierarchical Metadata
=====================================================
Imports documents with:
- Hierarchical Document Types (Faktura > Došlá/Odeslaná)
- Correspondents (extracted via LLM from document text)
- Tags/Labels (IČO, rok, měna, stav...)
- Custom Fields (invoice_number, total_amount, due_date...)

Ready for RAG integration.

Author: Claude Code
Date: 2025-12-05
"""

import os
import sys
import json
import sqlite3
import requests
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import re

# Configuration
PAPERLESS_URL = "http://localhost:8011"
PAPERLESS_USER = "admin"
PAPERLESS_PASSWORD = "admin123"
DB_PATH = "/Volumes/ACASIS/parallel_scan_1124_1205/documents.db"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:14b"  # Fast model for extraction

# Hierarchical Document Type Structure
DOCUMENT_TYPE_HIERARCHY = {
    "Dokument": {
        "Faktura": {
            "Došlá faktura": None,
            "Odeslaná faktura": None,
            "Zálohová faktura": None,
            "Dobropis": None
        },
        "Účtenka": {
            "Pohonné hmoty": None,
            "Restaurace": None,
            "Nákupy": None,
            "Služby": None,
            "Doprava": None,
            "Potvrzení platby": None  # PayPal, platební brány
        },
        "IT zpráva": {
            "Systémová notifikace": None,  # NAS, Docker, servery
            "Monitoring alert": None,
            "Backup report": None,
            "Security alert": None
        },
        "Bankovní výpis": {
            "Běžný účet": None,
            "Spořící účet": None,
            "Firemní účet": None
        },
        "Smlouva": {
            "Pracovní smlouva": None,
            "Nájemní smlouva": None,
            "Obchodní smlouva": None,
            "Pojistná smlouva": None
        },
        "Dopis": {
            "Úřední dopis": None,
            "Obchodní korespondence": None,
            "Osobní korespondence": None
        },
        "Daňový doklad": {
            "Daňové přiznání": None,
            "DPH přiznání": None,
            "Daňový doklad": None
        },
        "Právní dokument": {
            "Soudní rozhodnutí": None,
            "Exekuce": None,
            "Plná moc": None
        }
    }
}

# Tag Categories for RAG
TAG_CATEGORIES = {
    # Metadata tags
    "year": ["2020", "2021", "2022", "2023", "2024", "2025"],
    "currency": ["CZK", "EUR", "USD"],
    "status": ["Zaplaceno", "Nezaplaceno", "Částečně zaplaceno", "Storno"],
    "priority": ["Důležité", "Běžné", "Archiv"],
    "source": ["Email", "Sken", "Upload", "Auto-import"],
    # Business tags
    "vat": ["S DPH", "Bez DPH", "Osvobozeno"],
    "payment_method": ["Hotově", "Převodem", "Kartou", "PayPal"],
    # Content category tags
    "kategorie": ["Reklama", "Newsletter", "IT zpráva", "Obchodní", "Osobní", "Upomínka"],
}

# Custom Fields for structured data (RAG-ready)
CUSTOM_FIELDS = [
    {"name": "invoice_number", "data_type": "string"},
    {"name": "total_amount", "data_type": "monetary"},
    {"name": "currency", "data_type": "string"},
    {"name": "vat_amount", "data_type": "monetary"},
    {"name": "due_date", "data_type": "date"},
    {"name": "issue_date", "data_type": "date"},
    {"name": "ico", "data_type": "string"},
    {"name": "dic", "data_type": "string"},
    {"name": "bank_account", "data_type": "string"},
    {"name": "variable_symbol", "data_type": "string"},
    {"name": "payment_status", "data_type": "string"},
]


class PaperlessAPI:
    """Paperless-NGX API Client"""

    def __init__(self, url: str, username: str, password: str):
        self.url = url.rstrip('/')
        self.session = requests.Session()
        self.token = self._get_token(username, password)
        self.session.headers['Authorization'] = f'Token {self.token}'

        # Cache for created entities
        self.correspondents_cache: Dict[str, int] = {}
        self.document_types_cache: Dict[str, int] = {}
        self.tags_cache: Dict[str, int] = {}
        self.custom_fields_cache: Dict[str, int] = {}

    def _get_token(self, username: str, password: str) -> str:
        """Get API token"""
        resp = self.session.post(
            f"{self.url}/api/token/",
            json={"username": username, "password": password}
        )
        resp.raise_for_status()
        return resp.json()['token']

    # === CORRESPONDENTS ===
    def get_or_create_correspondent(self, name: str) -> int:
        """Get or create correspondent, return ID"""
        if name in self.correspondents_cache:
            return self.correspondents_cache[name]

        # Search existing
        resp = self.session.get(
            f"{self.url}/api/correspondents/",
            params={"name__iexact": name}
        )
        data = resp.json()
        if data['count'] > 0:
            corr_id = data['results'][0]['id']
            self.correspondents_cache[name] = corr_id
            return corr_id

        # Create new
        resp = self.session.post(
            f"{self.url}/api/correspondents/",
            json={"name": name}
        )
        if resp.status_code == 201:
            corr_id = resp.json()['id']
            self.correspondents_cache[name] = corr_id
            return corr_id
        else:
            print(f"  Warning: Failed to create correspondent '{name}': {resp.text}")
            return None

    # === DOCUMENT TYPES ===
    def create_document_type_hierarchy(self) -> Dict[str, int]:
        """Create hierarchical document types"""
        print("Creating document type hierarchy...")

        def create_types(hierarchy: dict, parent_name: str = None, level: int = 0):
            for name, children in hierarchy.items():
                full_name = f"{parent_name} > {name}" if parent_name else name

                # Check if exists
                resp = self.session.get(
                    f"{self.url}/api/document_types/",
                    params={"name__iexact": full_name}
                )
                data = resp.json()

                if data['count'] > 0:
                    type_id = data['results'][0]['id']
                else:
                    # Create
                    resp = self.session.post(
                        f"{self.url}/api/document_types/",
                        json={"name": full_name}
                    )
                    if resp.status_code == 201:
                        type_id = resp.json()['id']
                        print(f"  {'  ' * level}+ {full_name}")
                    else:
                        print(f"  Warning: Failed to create type '{full_name}'")
                        continue

                self.document_types_cache[full_name] = type_id

                # Recurse for children
                if children:
                    create_types(children, full_name, level + 1)

        create_types(DOCUMENT_TYPE_HIERARCHY)
        return self.document_types_cache

    def get_document_type_id(self, type_path: str) -> Optional[int]:
        """Get document type ID by hierarchical path"""
        return self.document_types_cache.get(type_path)

    # === TAGS ===
    def create_tag_categories(self) -> Dict[str, int]:
        """Create tag categories"""
        print("Creating tags...")

        for category, tags in TAG_CATEGORIES.items():
            for tag_name in tags:
                full_name = f"{category}:{tag_name}"

                # Check if exists
                resp = self.session.get(
                    f"{self.url}/api/tags/",
                    params={"name__iexact": full_name}
                )
                data = resp.json()

                if data['count'] > 0:
                    tag_id = data['results'][0]['id']
                else:
                    resp = self.session.post(
                        f"{self.url}/api/tags/",
                        json={"name": full_name}
                    )
                    if resp.status_code == 201:
                        tag_id = resp.json()['id']
                        print(f"  + {full_name}")
                    else:
                        continue

                self.tags_cache[full_name] = tag_id

        return self.tags_cache

    def get_or_create_tag(self, name: str) -> Optional[int]:
        """Get or create a tag"""
        if name in self.tags_cache:
            return self.tags_cache[name]

        resp = self.session.get(
            f"{self.url}/api/tags/",
            params={"name__iexact": name}
        )
        data = resp.json()

        if data['count'] > 0:
            tag_id = data['results'][0]['id']
        else:
            resp = self.session.post(
                f"{self.url}/api/tags/",
                json={"name": name}
            )
            if resp.status_code == 201:
                tag_id = resp.json()['id']
            else:
                return None

        self.tags_cache[name] = tag_id
        return tag_id

    # === CUSTOM FIELDS ===
    def create_custom_fields(self) -> Dict[str, int]:
        """Create custom fields for structured data"""
        print("Creating custom fields...")

        for field in CUSTOM_FIELDS:
            name = field['name']

            # Check if exists
            resp = self.session.get(
                f"{self.url}/api/custom_fields/",
                params={"name__iexact": name}
            )
            data = resp.json()

            if data['count'] > 0:
                field_id = data['results'][0]['id']
            else:
                resp = self.session.post(
                    f"{self.url}/api/custom_fields/",
                    json={"name": name, "data_type": field['data_type']}
                )
                if resp.status_code == 201:
                    field_id = resp.json()['id']
                    print(f"  + {name} ({field['data_type']})")
                else:
                    print(f"  Warning: Failed to create field '{name}': {resp.text}")
                    continue

            self.custom_fields_cache[name] = field_id

        return self.custom_fields_cache

    # === DOCUMENT UPLOAD ===
    def upload_document(
        self,
        file_path: str,
        title: str,
        correspondent_id: Optional[int] = None,
        document_type_id: Optional[int] = None,
        tag_ids: List[int] = None,
        custom_fields: Dict[str, Any] = None,
        created_date: str = None
    ) -> Optional[str]:
        """
        Upload document with full metadata

        Returns task ID for tracking
        """
        if not Path(file_path).exists():
            print(f"  File not found: {file_path}")
            return None

        # Prepare form data
        files = {
            'document': (Path(file_path).name, open(file_path, 'rb'), 'application/pdf')
        }

        data = {'title': title}

        if correspondent_id:
            data['correspondent'] = correspondent_id

        if document_type_id:
            data['document_type'] = document_type_id

        if tag_ids:
            # Tags need to be sent as multiple values
            for tag_id in tag_ids:
                if 'tags' not in data:
                    data['tags'] = []
                data['tags'].append(tag_id)

        if created_date:
            data['created'] = created_date

        if custom_fields:
            # Custom fields as dict mapping ID to value: {1: "value1", 2: "value2"}
            cf_data = {}
            for field_name, value in custom_fields.items():
                if field_name in self.custom_fields_cache and value:
                    field_id = self.custom_fields_cache[field_name]
                    cf_data[field_id] = str(value) if value else None
            if cf_data:
                data['custom_fields'] = json.dumps(cf_data)

        try:
            resp = self.session.post(
                f"{self.url}/api/documents/post_document/",
                files=files,
                data=data
            )

            if resp.status_code == 200:
                return resp.text  # Task ID
            else:
                print(f"  Upload failed: {resp.status_code} - {resp.text}")
                return None
        finally:
            files['document'][1].close()


class OllamaExtractor:
    """Extract metadata from document text using Ollama LLM"""

    def __init__(self, url: str = OLLAMA_URL, model: str = OLLAMA_MODEL):
        self.url = url
        self.model = model

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF using pdftotext"""
        try:
            result = subprocess.run(
                ['pdftotext', '-layout', pdf_path, '-'],
                capture_output=True, text=True, timeout=30
            )
            return result.stdout[:4000]  # Limit for LLM
        except Exception as e:
            print(f"  PDF text extraction failed: {e}")
            return ""

    def extract_metadata(self, text: str, doc_type: str = None) -> Dict[str, Any]:
        """
        Extract structured metadata using LLM

        Returns:
            {
                "correspondent": "Firma s.r.o.",
                "document_type_path": "Dokument > Faktura > Došlá faktura",
                "tags": ["year:2024", "currency:CZK", "status:Nezaplaceno"],
                "custom_fields": {
                    "invoice_number": "FV2024001",
                    "total_amount": "12500.00",
                    "currency": "CZK",
                    ...
                }
            }
        """
        if not text.strip():
            return self._default_metadata(doc_type)

        prompt = f"""Analyzuj tento dokument a extrahuj metadata ve formátu JSON.

DOKUMENT:
{text[:3000]}

Vrať POUZE validní JSON (bez markdown) s těmito poli:
{{
    "correspondent": "název firmy nebo odesílatele (pokud je faktura, uveď dodavatele)",
    "document_type_path": "hierarchická cesta typu dokumentu, např. 'Dokument > Faktura > Došlá faktura'",
    "tags": ["year:YYYY", "currency:XXX", "status:Zaplaceno/Nezaplaceno", "kategorie:XXX"],
    "custom_fields": {{
        "invoice_number": "číslo faktury",
        "total_amount": "celková částka jako číslo",
        "currency": "měna (CZK/EUR/USD)",
        "vat_amount": "DPH částka",
        "due_date": "datum splatnosti YYYY-MM-DD",
        "issue_date": "datum vystavení YYYY-MM-DD",
        "ico": "IČO dodavatele",
        "dic": "DIČ dodavatele",
        "variable_symbol": "variabilní symbol"
    }}
}}

Použij pouze existující hierarchie:
- Dokument > Faktura > Došlá faktura / Odeslaná faktura / Zálohová faktura / Dobropis
- Dokument > Účtenka > Pohonné hmoty / Restaurace / Nákupy / Služby / Doprava / Potvrzení platby (PayPal)
- Dokument > IT zpráva > Systémová notifikace (NAS, Docker, servery) / Monitoring alert / Backup report / Security alert
- Dokument > Bankovní výpis > Běžný účet / Spořící účet / Firemní účet
- Dokument > Smlouva > Pracovní / Nájemní / Obchodní / Pojistná
- Dokument > Dopis > Úřední / Obchodní korespondence / Osobní
- Dokument > Daňový doklad > Daňové přiznání / DPH přiznání
- Dokument > Právní dokument > Soudní rozhodnutí / Exekuce / Plná moc

DŮLEŽITÉ - přidej tag kategorie:
- "kategorie:Reklama" - pro reklamní, marketingové emaily, newslettery s nabídkami
- "kategorie:Newsletter" - pro informační newslettery bez prodejního zaměření
- "kategorie:IT zpráva" - pro systémové notifikace (NAS, Docker, monitoring, backup)
- "kategorie:Obchodní" - pro faktury, objednávky, smlouvy
- "kategorie:Osobní" - pro osobní korespondenci
- "kategorie:Upomínka" - pro upomínky k platbě

Pokud pole není v dokumentu, nastav null."""

        try:
            resp = requests.post(
                f"{self.url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1}
                },
                timeout=60
            )

            if resp.status_code == 200:
                response_text = resp.json().get('response', '')
                # Parse JSON from response
                return self._parse_llm_response(response_text, doc_type)
            else:
                return self._default_metadata(doc_type)

        except Exception as e:
            print(f"  LLM extraction failed: {e}")
            return self._default_metadata(doc_type)

    def _parse_llm_response(self, response: str, doc_type: str) -> Dict[str, Any]:
        """Parse JSON from LLM response"""
        try:
            # Try to find JSON in response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return data
        except json.JSONDecodeError:
            pass

        return self._default_metadata(doc_type)

    def _default_metadata(self, doc_type: str = None) -> Dict[str, Any]:
        """Return default metadata when extraction fails"""
        type_mapping = {
            'Invoice': 'Dokument > Faktura > Došlá faktura',
            'Receipt': 'Dokument > Účtenka > Nákupy',
            'Bank Statement': 'Dokument > Bankovní výpis > Běžný účet',
            'Contract': 'Dokument > Smlouva > Obchodní smlouva',
            'Letter': 'Dokument > Dopis > Obchodní korespondence',
            'Tax Document': 'Dokument > Daňový doklad > Daňový doklad',
        }

        return {
            "correspondent": "Neznámý",
            "document_type_path": type_mapping.get(doc_type, "Dokument"),
            "tags": [f"year:{datetime.now().year}"],
            "custom_fields": {}
        }


def import_documents_with_metadata(limit: int = 100):
    """
    Main import function

    1. Setup Paperless hierarchy (types, tags, custom fields)
    2. Load documents from ACASIS database
    3. Extract metadata via LLM
    4. Upload to Paperless with full metadata
    """
    print("=" * 70)
    print("PAPERLESS-NGX FULL IMPORT WITH HIERARCHICAL METADATA")
    print("=" * 70)
    print()

    # Initialize APIs
    print("Connecting to Paperless-NGX...")
    api = PaperlessAPI(PAPERLESS_URL, PAPERLESS_USER, PAPERLESS_PASSWORD)

    print("Connecting to Ollama...")
    extractor = OllamaExtractor()

    # Setup Paperless structure
    print()
    api.create_document_type_hierarchy()
    print()
    api.create_tag_categories()
    print()
    api.create_custom_fields()
    print()

    # Load documents from database
    print("Loading documents from ACASIS database...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT d.id, d.title, d.source_path, dt.name as type_name
        FROM documents d
        LEFT JOIN document_types dt ON d.document_type_id = dt.id
        WHERE d.source = 'acasis'
        AND d.source_path LIKE '%.pdf'
        AND d.document_type_id IN (1, 2, 3, 4, 5, 7)
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit * 2,))  # Get more to handle missing files

    docs = cursor.fetchall()
    conn.close()

    print(f"Found {len(docs)} candidate documents")
    print()

    # Process documents
    print("=" * 70)
    print("PROCESSING DOCUMENTS")
    print("=" * 70)

    imported = 0
    results = []

    for doc in docs:
        if imported >= limit:
            break

        source_path = doc['source_path']
        if not Path(source_path).exists():
            continue

        file_size = Path(source_path).stat().st_size
        if file_size < 1000:
            continue

        imported += 1
        print(f"\n[{imported}/{limit}] {doc['type_name']}: {Path(source_path).name}")

        # Extract text
        print("  Extracting text...")
        text = extractor.extract_text_from_pdf(source_path)

        # Extract metadata via LLM
        print("  Extracting metadata via LLM...")
        metadata = extractor.extract_metadata(text, doc['type_name'])

        # Handle None metadata
        if metadata is None:
            metadata = {}

        # Get/create correspondent
        correspondent_name = metadata.get('correspondent') or 'Neznámý'
        correspondent_id = api.get_or_create_correspondent(correspondent_name)
        print(f"  Correspondent: {correspondent_name} (ID: {correspondent_id})")

        # Get document type
        type_path = metadata.get('document_type_path') or 'Dokument'
        document_type_id = api.get_document_type_id(type_path)
        print(f"  Type: {type_path} (ID: {document_type_id})")

        # Get tags
        tag_ids = []
        tags_list = metadata.get('tags') or []
        for tag_name in tags_list:
            tag_id = api.get_or_create_tag(tag_name)
            if tag_id:
                tag_ids.append(tag_id)
        print(f"  Tags: {tags_list}")

        # Custom fields
        custom_fields = metadata.get('custom_fields') or {}
        if custom_fields:
            print(f"  Custom fields: {list(custom_fields.keys())}")

        # Upload document
        print("  Uploading to Paperless...")
        task_id = api.upload_document(
            file_path=source_path,
            title=doc['title'] or Path(source_path).stem,
            correspondent_id=correspondent_id,
            document_type_id=document_type_id,
            tag_ids=tag_ids,
            custom_fields=custom_fields
        )

        if task_id:
            print(f"  SUCCESS: Task {task_id[:20]}...")
            results.append({
                'id': doc['id'],
                'title': doc['title'],
                'correspondent': correspondent_name,
                'type': type_path,
                'tags': metadata.get('tags', []),
                'custom_fields': custom_fields,
                'task_id': task_id
            })
        else:
            print("  FAILED")

    # Summary
    print()
    print("=" * 70)
    print("IMPORT COMPLETE")
    print("=" * 70)
    print(f"Successfully imported: {len(results)}/{limit}")
    print()

    # Save results for RAG
    results_path = Path(__file__).parent / 'import_results.json'
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'total_imported': len(results),
            'documents': results
        }, f, indent=2, ensure_ascii=False)

    print(f"Results saved: {results_path}")
    print()
    print("Open Paperless-NGX: http://localhost:8011")
    print("Login: admin / admin123")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Import documents to Paperless-NGX with full metadata')
    parser.add_argument('--limit', type=int, default=100, help='Number of documents to import')
    args = parser.parse_args()

    import_documents_with_metadata(limit=args.limit)
