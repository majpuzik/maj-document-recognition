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
CLI nástroj pro párování dokumentů

Usage:
    python match_documents.py --all              # Spáruje všechny dokumenty
    python match_documents.py --doc-id 123       # Spáruje konkrétní dokument
    python match_documents.py --show-chains      # Zobrazí všechny chains
    python match_documents.py --status completed # Filtruje podle statusu
"""

import argparse
import json
import logging
import sys
import yaml
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.database.db_manager import DatabaseManager
from src.matching.document_matcher import DocumentMatcher


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/document_matching.log')
        ]
    )


def load_config() -> dict:
    """Load configuration from config.yaml"""
    config_path = Path('config/config.yaml')
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def match_all_documents(matcher: DocumentMatcher, limit: Optional[int] = None):
    """Match all documents in database"""
    print("\n🔍 Párování všech dokumentů...\n")

    stats = matcher.match_all_documents(limit=limit)

    print(f"\n✅ Hotovo!\n")
    print(f"📊 Statistiky:")
    print(f"   • Celkem dokumentů: {stats['total_documents']}")
    print(f"   • Extrahovaná metadata: {stats['extracted_metadata']}")
    print(f"   • Vytvořené chains: {stats['matched_chains']}")
    print()


def match_single_document(matcher: DocumentMatcher, doc_id: int):
    """Match single document"""
    print(f"\n🔍 Párování dokumentu #{doc_id}...\n")

    # Extract metadata
    info = matcher.extract_and_store_metadata(doc_id)
    if not info:
        print(f"❌ Dokument #{doc_id} nebyl nalezen")
        return

    print("📄 Extrahovaná metadata:")
    print(f"   • Číslo objednávky: {info.order_number or 'N/A'}")
    print(f"   • Číslo faktury: {info.invoice_number or 'N/A'}")
    print(f"   • Číslo dodacího listu: {info.delivery_note_number or 'N/A'}")
    print(f"   • Variabilní symbol: {info.variable_symbol or 'N/A'}")
    print(f"   • Částka: {info.amount_with_vat or 'N/A'} Kč")
    print(f"   • Vendor: {info.vendor_name or 'N/A'}")
    print()

    # Find matches
    matches = matcher.match_documents(doc_id)
    if not matches:
        print("ℹ️  Žádné spárované dokumenty nenalezeny")
        return

    print("🔗 Spárované dokumenty:")
    if matches['order']:
        print(f"   📋 Objednávka: #{matches['order']['id']} - {matches['order']['file_name']}")
    if matches['invoice']:
        print(f"   📄 Faktura: #{matches['invoice']['id']} - {matches['invoice']['file_name']}")
    if matches['delivery_note']:
        print(f"   📦 Dodací list: #{matches['delivery_note']['id']} - {matches['delivery_note']['file_name']}")
    if matches['payment']:
        print(f"   💰 Platba: #{matches['payment']['id']} - {matches['payment']['file_name']}")
    print()

    # Create chain
    chain_id = matcher.create_or_update_chain(
        order_id=matches['order']['id'] if matches['order'] else None,
        invoice_id=matches['invoice']['id'] if matches['invoice'] else None,
        delivery_id=matches['delivery_note']['id'] if matches['delivery_note'] else None,
        payment_id=matches['payment']['id'] if matches['payment'] else None,
    )

    print(f"✅ Chain vytvořen: {chain_id}\n")


def show_chains(matcher: DocumentMatcher, status: Optional[str] = None):
    """Show all document chains"""
    print("\n📊 Přehled document chains:\n")

    chains = matcher.get_all_chains(status=status)

    if not chains:
        print("ℹ️  Žádné chains nenalezeny")
        return

    # Group by status
    by_status = {}
    for chain in chains:
        chain_status = chain['status']
        if chain_status not in by_status:
            by_status[chain_status] = []
        by_status[chain_status].append(chain)

    # Display
    status_emoji = {
        'ordered': '📋',
        'invoiced': '📄',
        'delivered': '📦',
        'completed': '✅',
        'unknown': '❓',
    }

    for status_name, chains_list in by_status.items():
        emoji = status_emoji.get(status_name, '•')
        print(f"\n{emoji} {status_name.upper()} ({len(chains_list)} chains):")
        print("─" * 80)

        for chain in chains_list[:10]:  # Show first 10
            print(f"  Chain: {chain['chain_id']}")
            print(f"    Vendor: {chain['vendor_name'] or 'N/A'}")
            print(f"    Částka: {chain['total_amount'] or 'N/A'} Kč")
            print(f"    Order: #{chain['order_doc_id'] or 'N/A'}")
            print(f"    Invoice: #{chain['invoice_doc_id'] or 'N/A'}")
            print(f"    Delivery: #{chain['delivery_note_doc_id'] or 'N/A'}")
            print(f"    Payment: #{chain['payment_doc_id'] or 'N/A'}")
            print()

        if len(chains_list) > 10:
            print(f"  ... a dalších {len(chains_list) - 10} chains\n")

    print(f"\n📊 Celkem: {len(chains)} chains\n")


def export_chains(matcher: DocumentMatcher, output_file: str, status: Optional[str] = None):
    """Export chains to JSON file"""
    print(f"\n💾 Export chains do {output_file}...\n")

    chains = matcher.get_all_chains(status=status)

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(chains, f, ensure_ascii=False, indent=2, default=str)

    print(f"✅ Exportováno {len(chains)} chains do {output_file}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Document Matching Tool - Párování objednávek, faktur, dodacích listů a plateb'
    )

    parser.add_argument('--all', action='store_true',
                        help='Spáruje všechny dokumenty v databázi')
    parser.add_argument('--doc-id', type=int,
                        help='Spáruje konkrétní dokument podle ID')
    parser.add_argument('--show-chains', action='store_true',
                        help='Zobrazí všechny document chains')
    parser.add_argument('--status', type=str, choices=['ordered', 'invoiced', 'delivered', 'completed'],
                        help='Filtruje chains podle statusu')
    parser.add_argument('--export', type=str, metavar='FILE',
                        help='Exportuje chains do JSON souboru')
    parser.add_argument('--limit', type=int,
                        help='Omezí počet zpracovaných dokumentů')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose logging')

    args = parser.parse_args()

    # Setup
    setup_logging(args.verbose)
    config = load_config()

    # Initialize
    db = DatabaseManager(config)
    matcher = DocumentMatcher(db)

    # Execute command
    try:
        if args.all:
            match_all_documents(matcher, limit=args.limit)

        elif args.doc_id:
            match_single_document(matcher, args.doc_id)

        elif args.show_chains:
            show_chains(matcher, status=args.status)

        elif args.export:
            export_chains(matcher, args.export, status=args.status)

        else:
            parser.print_help()
            sys.exit(1)

    except Exception as e:
        logging.error(f"Error: {e}", exc_info=True)
        print(f"\n❌ Chyba: {e}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
