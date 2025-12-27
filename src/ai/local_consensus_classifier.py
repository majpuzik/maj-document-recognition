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
Local-Only AI Consensus Classifier for Document Recognition
============================================================
Uses multiple local Ollama models with consensus voting.
No cloud APIs required - 100% local processing.

Features:
- 3 local LLM models with consensus voting
- Extended document classification with recipient extraction
- Paperless-ngx integration (correspondents, tags, document types)
- Email metadata extraction
- Content-based recipient identification (Pan/Paní/Firma)

Version: 2.0.0
"""

import json
import logging
import re
import subprocess
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import requests

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Local Ollama models for consensus voting
LOCAL_MODELS = [
    ("qwen2.5:72b", "primary"),      # Main model - best accuracy
    ("llama3.3:70b", "secondary"),   # Second vote
    ("qwen2.5:32b", "tertiary"),     # Third vote - faster fallback
]

# Document types for classification
DOC_TYPES = [
    "INVOICE", "RECEIPT", "CONTRACT", "INSURANCE", "MEDICAL_REPORT",
    "BANK_STATEMENT", "TAX_DOCUMENT", "LEGAL_DOCUMENT", "CORRESPONDENCE",
    "TECHNICAL_MANUAL", "MARKETING", "ORDER", "DELIVERY_NOTE", "WARRANTY",
    "CERTIFICATE", "APPLICATION_FORM", "REPORT", "MINUTES", "PERSONAL_ID",
    "POWER_OF_ATTORNEY", "DECLARATION", "NOTIFICATION", "EMAIL", "OTHER"
]

# Recipient types for Paperless-ngx tags
RECIPIENT_TYPES = {
    "PERSON_MALE": "Pan",
    "PERSON_FEMALE": "Paní",
    "COMPANY": "Firma",
    "INSTITUTION": "Instituce",
    "UNKNOWN": "Neznámý"
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class EmailMetadata:
    """Email metadata extracted from document"""
    sender: Optional[str] = None
    recipient: Optional[str] = None
    subject: Optional[str] = None
    date: Optional[str] = None
    cc: Optional[List[str]] = None


@dataclass
class RecipientInfo:
    """Recipient information for Paperless-ngx correspondent"""
    name: str
    type: str  # PERSON_MALE, PERSON_FEMALE, COMPANY, INSTITUTION, UNKNOWN
    confidence: float
    source: str  # "email", "content", "filename"


@dataclass
class ClassificationResult:
    """Complete classification result"""
    file_path: str
    file_hash: str

    # Document type classification
    document_type: str
    type_confidence: float
    type_votes: Dict[str, str] = field(default_factory=dict)
    type_consensus: bool = False

    # Recipient/Correspondent
    recipient: Optional[RecipientInfo] = None

    # Subject/Title
    suggested_title: Optional[str] = None

    # Email metadata (if applicable)
    email_metadata: Optional[EmailMetadata] = None

    # Tags for Paperless-ngx
    suggested_tags: List[str] = field(default_factory=list)

    # Processing info
    processing_time: float = 0.0
    models_used: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# =============================================================================
# OLLAMA API CLIENT
# =============================================================================

class OllamaClient:
    """Client for local Ollama API"""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.timeout = 180  # 3 minutes per query

    def query(self, model: str, prompt: str, temperature: float = 0.1) -> Optional[str]:
        """
        Query a model and return the response

        Args:
            model: Model name
            prompt: Prompt text
            temperature: Sampling temperature

        Returns:
            Model response or None on error
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": 200,
                    }
                },
                timeout=self.timeout
            )

            if response.status_code == 200:
                return response.json().get("response", "").strip()
            else:
                logger.warning(f"Ollama error {response.status_code}: {response.text}")
                return None

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout querying {model}")
            return None
        except Exception as e:
            logger.error(f"Error querying {model}: {e}")
            return None

    def is_available(self, model: str) -> bool:
        """Check if model is available"""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=10
            )
            if response.status_code == 200:
                models = [m.get("name", "") for m in response.json().get("models", [])]
                return any(model in m or m in model for m in models)
            return False
        except:
            return False


# =============================================================================
# TEXT EXTRACTION
# =============================================================================

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using pdftotext"""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception as e:
        logger.error(f"Error extracting text from {pdf_path}: {e}")
        return ""


# =============================================================================
# PROMPTS
# =============================================================================

CLASSIFICATION_PROMPT = """Analyzuj následující text dokumentu a urči jeho typ.

MOŽNÉ TYPY DOKUMENTŮ:
{types}

TEXT DOKUMENTU (prvních 2500 znaků):
---
{text}
---

ÚKOL: Odpověz POUZE názvem typu dokumentu z výše uvedeného seznamu.
Pokud si nejsi jistý, odpověz "OTHER".

Odpověď (pouze název typu):"""


RECIPIENT_EXTRACTION_PROMPT = """Analyzuj text dokumentu a extrahuj informace o příjemci.

TEXT DOKUMENTU:
---
{text}
---

ÚKOL: Najdi příjemce dokumentu (komu je dokument určen).

Odpověz ve formátu JSON:
{{
    "recipient_name": "Jméno příjemce nebo název firmy",
    "recipient_type": "PERSON_MALE" nebo "PERSON_FEMALE" nebo "COMPANY" nebo "INSTITUTION" nebo "UNKNOWN",
    "confidence": 0.0 až 1.0
}}

PRAVIDLA:
- PERSON_MALE = muž (pan, Ing., Mgr., Dr. + mužské jméno)
- PERSON_FEMALE = žena (paní, Ing., Mgr., Dr. + ženské jméno)
- COMPANY = firma (s.r.o., a.s., spol., GmbH, Ltd., Inc.)
- INSTITUTION = instituce (úřad, soud, pojišťovna, banka, nemocnice)
- Pokud nenajdeš příjemce, vrať "recipient_name": null

JSON odpověď:"""


EMAIL_EXTRACTION_PROMPT = """Analyzuj text emailu a extrahuj metadata.

TEXT:
---
{text}
---

Odpověz ve formátu JSON:
{{
    "sender": "email nebo jméno odesílatele",
    "recipient": "email nebo jméno příjemce",
    "subject": "předmět emailu",
    "date": "datum ve formátu YYYY-MM-DD pokud nalezeno"
}}

JSON odpověď:"""


TITLE_EXTRACTION_PROMPT = """Analyzuj text dokumentu a navrhni krátký titulek (max 60 znaků).

TEXT:
---
{text}
---

PRAVIDLA:
- Titulek by měl být stručný a výstižný
- Pro faktury: "Faktura [firma] [číslo]"
- Pro emaily: "[Předmět]"
- Pro smlouvy: "Smlouva [typ] [strany]"
- Pro lékařské zprávy: "Lékařská zpráva [typ]"

Navržený titulek (max 60 znaků):"""


# =============================================================================
# LOCAL CONSENSUS CLASSIFIER
# =============================================================================

class LocalConsensusClassifier:
    """
    Document classifier using local Ollama models with consensus voting.

    Uses 3 local models and requires 2+ agreeing for consensus.
    """

    def __init__(
        self,
        models: List[Tuple[str, str]] = None,
        ollama_url: str = "http://localhost:11434",
        consensus_threshold: int = 2
    ):
        """
        Initialize classifier

        Args:
            models: List of (model_name, role) tuples
            ollama_url: Ollama API URL
            consensus_threshold: Minimum agreeing models for consensus
        """
        self.models = models or LOCAL_MODELS
        self.ollama = OllamaClient(ollama_url)
        self.consensus_threshold = consensus_threshold

        # Verify available models
        self.available_models = []
        for model, role in self.models:
            if self.ollama.is_available(model):
                self.available_models.append((model, role))
                logger.info(f"Model available: {model} ({role})")
            else:
                logger.warning(f"Model not available: {model}")

    def classify_document_type(self, text: str) -> Tuple[str, float, Dict[str, str], bool]:
        """
        Classify document type using consensus voting

        Args:
            text: Document text

        Returns:
            (document_type, confidence, votes_dict, has_consensus)
        """
        if len(text) < 50:
            return "OTHER", 0.0, {}, False

        prompt = CLASSIFICATION_PROMPT.format(
            types=", ".join(DOC_TYPES),
            text=text[:2500]
        )

        votes = {}

        for model, role in self.available_models:
            response = self.ollama.query(model, prompt)
            if response:
                # Parse response - find matching document type
                response_upper = response.upper().strip()
                doc_type = "OTHER"

                for dtype in DOC_TYPES:
                    if dtype in response_upper:
                        doc_type = dtype
                        break

                votes[model] = doc_type
                logger.debug(f"{model}: {doc_type}")

        if not votes:
            return "OTHER", 0.0, {}, False

        # Count votes
        vote_counts = {}
        for doc_type in votes.values():
            vote_counts[doc_type] = vote_counts.get(doc_type, 0) + 1

        # Find winner
        best_type = max(vote_counts, key=vote_counts.get)
        best_count = vote_counts[best_type]

        has_consensus = best_count >= self.consensus_threshold
        confidence = best_count / len(votes)

        return best_type, confidence, votes, has_consensus

    def extract_recipient(self, text: str) -> Optional[RecipientInfo]:
        """
        Extract recipient information from document

        Args:
            text: Document text

        Returns:
            RecipientInfo or None
        """
        if len(text) < 50:
            return None

        # Use primary model for extraction
        primary_model = self.available_models[0][0] if self.available_models else None
        if not primary_model:
            return None

        prompt = RECIPIENT_EXTRACTION_PROMPT.format(text=text[:2000])
        response = self.ollama.query(primary_model, prompt, temperature=0.1)

        if not response:
            return None

        try:
            # Parse JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                name = data.get("recipient_name")
                if not name or name.lower() == "null":
                    return None

                return RecipientInfo(
                    name=name,
                    type=data.get("recipient_type", "UNKNOWN"),
                    confidence=float(data.get("confidence", 0.5)),
                    source="content"
                )
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"Failed to parse recipient JSON: {e}")

        return None

    def extract_email_metadata(self, text: str) -> Optional[EmailMetadata]:
        """
        Extract email metadata if document is an email

        Args:
            text: Document text

        Returns:
            EmailMetadata or None
        """
        # Quick check for email indicators
        email_indicators = ["From:", "To:", "Subject:", "Odesílatel:", "Příjemce:", "Předmět:"]
        if not any(ind in text for ind in email_indicators):
            return None

        primary_model = self.available_models[0][0] if self.available_models else None
        if not primary_model:
            return None

        prompt = EMAIL_EXTRACTION_PROMPT.format(text=text[:1500])
        response = self.ollama.query(primary_model, prompt, temperature=0.1)

        if not response:
            return None

        try:
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return EmailMetadata(
                    sender=data.get("sender"),
                    recipient=data.get("recipient"),
                    subject=data.get("subject"),
                    date=data.get("date")
                )
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    def suggest_title(self, text: str, doc_type: str) -> Optional[str]:
        """
        Suggest a title for the document

        Args:
            text: Document text
            doc_type: Document type

        Returns:
            Suggested title or None
        """
        primary_model = self.available_models[0][0] if self.available_models else None
        if not primary_model:
            return None

        prompt = TITLE_EXTRACTION_PROMPT.format(text=text[:1500])
        response = self.ollama.query(primary_model, prompt, temperature=0.2)

        if response:
            # Clean up response
            title = response.strip().strip('"').strip("'")
            if len(title) > 60:
                title = title[:57] + "..."
            return title

        return None

    def generate_tags(
        self,
        doc_type: str,
        recipient: Optional[RecipientInfo],
        email_metadata: Optional[EmailMetadata]
    ) -> List[str]:
        """
        Generate suggested tags for Paperless-ngx

        Args:
            doc_type: Document type
            recipient: Recipient info
            email_metadata: Email metadata

        Returns:
            List of tag names
        """
        tags = []

        # Document type tag
        type_tag_map = {
            "INVOICE": "Faktura",
            "RECEIPT": "Účtenka",
            "CONTRACT": "Smlouva",
            "INSURANCE": "Pojištění",
            "MEDICAL_REPORT": "Lékařská zpráva",
            "BANK_STATEMENT": "Bankovní výpis",
            "TAX_DOCUMENT": "Daňový doklad",
            "LEGAL_DOCUMENT": "Právní dokument",
            "CORRESPONDENCE": "Korespondence",
            "TECHNICAL_MANUAL": "Technická dokumentace",
            "MARKETING": "Marketing",
            "ORDER": "Objednávka",
            "DELIVERY_NOTE": "Dodací list",
            "WARRANTY": "Záruka",
            "CERTIFICATE": "Certifikát",
            "APPLICATION_FORM": "Žádost",
            "REPORT": "Zpráva",
            "MINUTES": "Zápis",
            "PERSONAL_ID": "Osobní doklad",
            "POWER_OF_ATTORNEY": "Plná moc",
            "DECLARATION": "Prohlášení",
            "NOTIFICATION": "Oznámení",
            "EMAIL": "Email",
            "OTHER": "Ostatní"
        }

        tags.append(type_tag_map.get(doc_type, "Ostatní"))

        # Recipient type tag
        if recipient:
            tags.append(RECIPIENT_TYPES.get(recipient.type, "Neznámý"))

        # Year tag from email date
        if email_metadata and email_metadata.date:
            try:
                year = email_metadata.date[:4]
                if year.isdigit() and 2000 <= int(year) <= 2030:
                    tags.append(f"Rok_{year}")
            except:
                pass

        return tags

    def classify(
        self,
        file_path: Path,
        file_hash: str,
        text: Optional[str] = None
    ) -> ClassificationResult:
        """
        Perform complete document classification

        Args:
            file_path: Path to document
            file_hash: Document hash
            text: Pre-extracted text (optional)

        Returns:
            ClassificationResult
        """
        import time
        start_time = time.time()

        # Extract text if not provided
        if text is None:
            text = extract_text_from_pdf(file_path)

        # Classify document type
        doc_type, confidence, votes, has_consensus = self.classify_document_type(text)

        # Extract recipient
        recipient = self.extract_recipient(text)

        # Extract email metadata if it's an email
        email_metadata = None
        if doc_type == "EMAIL":
            email_metadata = self.extract_email_metadata(text)

            # Update recipient from email if not found in content
            if not recipient and email_metadata and email_metadata.recipient:
                recipient = RecipientInfo(
                    name=email_metadata.recipient,
                    type="UNKNOWN",
                    confidence=0.8,
                    source="email"
                )

        # Suggest title
        suggested_title = self.suggest_title(text, doc_type)

        # Generate tags
        suggested_tags = self.generate_tags(doc_type, recipient, email_metadata)

        processing_time = time.time() - start_time

        return ClassificationResult(
            file_path=str(file_path),
            file_hash=file_hash,
            document_type=doc_type,
            type_confidence=confidence,
            type_votes=votes,
            type_consensus=has_consensus,
            recipient=recipient,
            suggested_title=suggested_title,
            email_metadata=email_metadata,
            suggested_tags=suggested_tags,
            processing_time=processing_time,
            models_used=[m[0] for m in self.available_models]
        )


# =============================================================================
# BATCH PROCESSOR
# =============================================================================

class BatchClassifier:
    """Process multiple documents with progress tracking"""

    def __init__(
        self,
        classifier: LocalConsensusClassifier,
        progress_file: Optional[Path] = None
    ):
        self.classifier = classifier
        self.progress_file = progress_file
        self.results = []
        self.processed_hashes = set()

        # Load progress if exists
        if progress_file and progress_file.exists():
            self._load_progress()

    def _load_progress(self):
        """Load progress from file"""
        try:
            with open(self.progress_file) as f:
                data = json.load(f)
            self.results = data.get("results", [])
            self.processed_hashes = set(r.get("file_hash") for r in self.results)
            logger.info(f"Loaded {len(self.processed_hashes)} previously processed documents")
        except Exception as e:
            logger.warning(f"Could not load progress: {e}")

    def _save_progress(self):
        """Save progress to file"""
        if not self.progress_file:
            return

        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "total": len(self.results),
                    "results": [asdict(r) if hasattr(r, '__dataclass_fields__') else r for r in self.results]
                }, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"Could not save progress: {e}")

    def process_batch(
        self,
        documents: List[Dict],
        save_interval: int = 10
    ) -> List[ClassificationResult]:
        """
        Process batch of documents

        Args:
            documents: List of {"path": ..., "hash": ..., "text": ...} dicts
            save_interval: Save progress every N documents

        Returns:
            List of ClassificationResult
        """
        total = len(documents)
        new_results = []

        for idx, doc in enumerate(documents, 1):
            file_hash = doc.get("hash", "")

            # Skip if already processed
            if file_hash in self.processed_hashes:
                logger.debug(f"Skipping already processed: {doc.get('path')}")
                continue

            file_path = Path(doc.get("path", ""))
            text = doc.get("text")

            logger.info(f"[{idx}/{total}] Processing: {file_path.name}")

            try:
                result = self.classifier.classify(file_path, file_hash, text)
                self.results.append(result)
                new_results.append(result)
                self.processed_hashes.add(file_hash)

                logger.info(
                    f"  -> {result.document_type} "
                    f"(consensus: {result.type_consensus}, "
                    f"recipient: {result.recipient.name if result.recipient else 'N/A'})"
                )

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")

            # Save progress periodically
            if idx % save_interval == 0:
                self._save_progress()

        # Final save
        self._save_progress()

        return new_results

    def get_statistics(self) -> Dict:
        """Get processing statistics"""
        stats = {
            "total": len(self.results),
            "with_consensus": 0,
            "without_consensus": 0,
            "by_type": {},
            "by_recipient_type": {},
        }

        for r in self.results:
            result = r if isinstance(r, dict) else asdict(r)

            if result.get("type_consensus"):
                stats["with_consensus"] += 1
            else:
                stats["without_consensus"] += 1

            doc_type = result.get("document_type", "OTHER")
            stats["by_type"][doc_type] = stats["by_type"].get(doc_type, 0) + 1

            recipient = result.get("recipient")
            if recipient:
                rtype = recipient.get("type", "UNKNOWN") if isinstance(recipient, dict) else recipient.type
                stats["by_recipient_type"][rtype] = stats["by_recipient_type"].get(rtype, 0) + 1

        return stats


# =============================================================================
# CLI / MAIN
# =============================================================================

def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Local AI Document Classifier")
    parser.add_argument("--input", "-i", required=True, help="Input JSON with documents or PDF file")
    parser.add_argument("--output", "-o", help="Output JSON file")
    parser.add_argument("--models", nargs="+", default=["qwen2.5:72b", "llama3.3:70b", "qwen2.5:32b"],
                       help="Ollama models to use")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama API URL")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Initialize classifier
    models = [(m, f"model_{i}") for i, m in enumerate(args.models)]
    classifier = LocalConsensusClassifier(models=models, ollama_url=args.ollama_url)

    input_path = Path(args.input)

    if input_path.suffix == ".pdf":
        # Single file mode
        import hashlib
        with open(input_path, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()

        result = classifier.classify(input_path, file_hash)
        print(json.dumps(asdict(result), indent=2, ensure_ascii=False, default=str))

    elif input_path.suffix == ".json":
        # Batch mode
        with open(input_path) as f:
            data = json.load(f)

        documents = data if isinstance(data, list) else data.get("documents", data.get("results", []))

        output_path = Path(args.output) if args.output else input_path.with_suffix(".classified.json")
        batch = BatchClassifier(classifier, progress_file=output_path)

        results = batch.process_batch(documents)
        stats = batch.get_statistics()

        print("\n" + "="*60)
        print("CLASSIFICATION COMPLETE")
        print("="*60)
        print(f"Total processed: {stats['total']}")
        print(f"With consensus: {stats['with_consensus']}")
        print(f"Without consensus: {stats['without_consensus']}")
        print("\nBy type:")
        for t, c in sorted(stats["by_type"].items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")
        print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
