#!/usr/bin/env python3
"""
MAJ Document Recognition - Paperless Import
Import vybraných dokumentů do Paperless-NGX
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List

import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.integrations.paperless_api import PaperlessAPI


class PaperlessImporter:
    """Importer dokumentů do Paperless-NGX"""

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize importer"""
        # Load config
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

        # Initialize Paperless API
        self.paperless = PaperlessAPI(self.config)

        # Test connection
        if not self.paperless.test_connection():
            raise ConnectionError("Nelze se připojit k Paperless-NGX! Zkontroluj config.")

        self.logger.info("✅ Připojeno k Paperless-NGX")

    def import_documents(self, export_file: str, dry_run: bool = False) -> Dict:
        """
        Import dokumentů do Paperless

        Args:
            export_file: JSON soubor s exportovanými dokumenty
            dry_run: Pokud True, pouze simulace bez uploadu

        Returns:
            Statistiky importu
        """
        export_path = Path(export_file)

        if not export_path.exists():
            raise FileNotFoundError(f"Export soubor neexistuje: {export_file}")

        # Load export
        with open(export_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        documents = data.get('documents', [])
        total = len(documents)

        if total == 0:
            self.logger.warning("❌ Žádné dokumenty k importu")
            return {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0}

        self.logger.info(f"📦 Zahajuji import {total} dokumentů...")
        if dry_run:
            self.logger.info("🔍 DRY RUN MODE - žádné změny nebudou provedeny")

        results = {
            'total': total,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'duplicates': 0,
            'errors': []
        }

        for i, doc in enumerate(documents, 1):
            file_path = doc.get('file_path')
            file_name = doc.get('file_name')

            self.logger.info(f"\n[{i}/{total}] Importuji: {file_name}")

            if not Path(file_path).exists():
                self.logger.error(f"❌ Soubor neexistuje: {file_path}")
                results['failed'] += 1
                results['errors'].append({
                    'file': file_name,
                    'error': 'File not found'
                })
                continue

            if dry_run:
                self.logger.info(f"  🔍 DRY RUN: Byl by nahrán s:")
                self.logger.info(f"     Title: {doc.get('title')}")
                self.logger.info(f"     Type: {doc.get('document_type')}")
                self.logger.info(f"     Tags: {', '.join(doc.get('tags', []))}")
                if doc.get('correspondent'):
                    self.logger.info(f"     Correspondent: {doc.get('correspondent')}")
                results['success'] += 1
                continue

            # Upload to Paperless
            try:
                upload_result = self.paperless.upload_document(
                    file_path=file_path,
                    title=doc.get('title'),
                    document_type=doc.get('document_type'),
                    correspondent=doc.get('correspondent'),
                    tags=doc.get('tags', [])
                )

                if upload_result.get('success'):
                    if upload_result.get('duplicate'):
                        self.logger.info(f"  ⚠️  Duplikát (ID: {upload_result.get('paperless_id')})")
                        results['duplicates'] += 1
                        results['skipped'] += 1
                    else:
                        self.logger.info(f"  ✅ Úspěšně nahráno (ID: {upload_result.get('paperless_id')})")
                        results['success'] += 1
                else:
                    error_msg = upload_result.get('error', 'Unknown error')
                    self.logger.error(f"  ❌ Chyba: {error_msg}")
                    results['failed'] += 1
                    results['errors'].append({
                        'file': file_name,
                        'error': error_msg
                    })

            except Exception as e:
                self.logger.error(f"  ❌ Chyba při uploadu: {e}", exc_info=True)
                results['failed'] += 1
                results['errors'].append({
                    'file': file_name,
                    'error': str(e)
                })

        return results

    def print_summary(self, results: Dict):
        """Vypsat souhrn importu"""
        print("\n" + "=" * 80)
        print("📊 SOUHRN IMPORTU DO PAPERLESS-NGX")
        print("=" * 80)
        print(f"  Celkem:            {results['total']}")
        print(f"  Úspěšně nahrané:   {results['success']} ({results['success']/results['total']*100:.1f}%)")
        print(f"  Duplikáty:         {results['duplicates']}")
        print(f"  Přeskočené:        {results['skipped']}")
        print(f"  Chyby:             {results['failed']}")

        if results['errors']:
            print("\n📋 CHYBY:")
            for error in results['errors'][:10]:  # Max 10 errors
                print(f"  • {error['file']}: {error['error']}")
            if len(results['errors']) > 10:
                print(f"  ... a dalších {len(results['errors']) - 10} chyb")

        print("=" * 80)


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='MAJ Document Recognition - Paperless Import')
    parser.add_argument('--export', '-e',
                       default='data/paperless_import.json',
                       help='JSON soubor s exportovanými dokumenty')
    parser.add_argument('--config', '-c',
                       default='config/config.yaml',
                       help='Cesta ke konfiguraci')
    parser.add_argument('--dry-run', '-d',
                       action='store_true',
                       help='Pouze simulace bez reálného uploadu')

    args = parser.parse_args()

    try:
        # Create importer
        importer = PaperlessImporter(args.config)

        # Import documents
        print("🚀 Zahajuji import do Paperless-NGX...")
        print(f"   Export: {args.export}")
        if args.dry_run:
            print("   🔍 DRY RUN MODE")
        print()

        results = importer.import_documents(args.export, dry_run=args.dry_run)

        # Print summary
        importer.print_summary(results)

        print("\n✅ Import dokončen!")

    except FileNotFoundError as e:
        print(f"\n❌ Chyba: {e}")
        print("\n💡 Nejprve spusť:")
        print("   1. python process_mbw_documents.py")
        print("   2. python interactive_selector.py")
        print("   3. python import_to_paperless.py")
        sys.exit(1)

    except ConnectionError as e:
        print(f"\n❌ Chyba připojení: {e}")
        print("\n💡 Zkontroluj Paperless-NGX konfiguraci v config/config.yaml:")
        print("   - url: http://localhost:8000")
        print("   - api_token: <tvůj-token>")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n👋 Přerušeno uživatelem")
        sys.exit(0)


if __name__ == "__main__":
    main()
