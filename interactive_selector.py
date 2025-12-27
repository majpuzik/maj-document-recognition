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
MAJ Document Recognition - Interactive Document Selector
Interaktivní výběr dokumentů s filtry pro import do Paperless
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class DocumentSelector:
    """Interaktivní selektor dokumentů"""

    def __init__(self, results_file: str):
        """
        Initialize selector

        Args:
            results_file: Cesta k JSON souboru s výsledky
        """
        self.results_file = Path(results_file)

        if not self.results_file.exists():
            raise FileNotFoundError(f"Soubor neexistuje: {results_file}")

        # Load results
        with open(self.results_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.all_documents = data.get('documents', [])
        self.filtered_documents = self.all_documents.copy()

        # Filters
        self.filters = {
            'document_type': None,
            'min_confidence': None,
            'max_confidence': None,
            'date_from': None,
            'date_to': None,
            'selected_only': False,
        }

    def apply_filters(self):
        """Aplikovat aktivní filtry"""
        filtered = self.all_documents.copy()

        # Filter by document type
        if self.filters['document_type']:
            filtered = [d for d in filtered
                       if d.get('document_type') == self.filters['document_type']]

        # Filter by confidence
        if self.filters['min_confidence'] is not None:
            filtered = [d for d in filtered
                       if d.get('confidence', 0) >= self.filters['min_confidence']]

        if self.filters['max_confidence'] is not None:
            filtered = [d for d in filtered
                       if d.get('confidence', 0) <= self.filters['max_confidence']]

        # Filter by date
        if self.filters['date_from']:
            date_from = datetime.fromisoformat(self.filters['date_from'])
            filtered = [d for d in filtered
                       if datetime.fromisoformat(d.get('file_date', '')) >= date_from]

        if self.filters['date_to']:
            date_to = datetime.fromisoformat(self.filters['date_to'])
            filtered = [d for d in filtered
                       if datetime.fromisoformat(d.get('file_date', '')) <= date_to]

        # Filter selected only
        if self.filters['selected_only']:
            filtered = [d for d in filtered if d.get('selected', False)]

        self.filtered_documents = filtered

    def get_unique_document_types(self) -> List[str]:
        """Získat seznam unikátních typů dokumentů"""
        types = set()
        for doc in self.all_documents:
            if doc.get('success'):
                types.add(doc.get('document_type', 'unknown'))
        return sorted(types)

    def toggle_selection(self, index: int):
        """
        Přepnout výběr dokumentu

        Args:
            index: Index dokumentu ve filtrovaném seznamu
        """
        if 0 <= index < len(self.filtered_documents):
            doc = self.filtered_documents[index]
            doc['selected'] = not doc.get('selected', False)

    def select_all(self):
        """Vybrat všechny (filtrované) dokumenty"""
        for doc in self.filtered_documents:
            doc['selected'] = True

    def deselect_all(self):
        """Zrušit výběr všech (filtrovaných) dokumentů"""
        for doc in self.filtered_documents:
            doc['selected'] = False

    def get_selected_documents(self) -> List[Dict]:
        """Získat vybrané dokumenty"""
        return [d for d in self.all_documents if d.get('selected', False)]

    def print_documents(self, page: int = 0, per_page: int = 20):
        """
        Vypsat dokumenty (stránkování)

        Args:
            page: Číslo stránky (0-based)
            per_page: Dokumentů na stránku
        """
        start = page * per_page
        end = start + per_page

        docs_page = self.filtered_documents[start:end]

        if not docs_page:
            print("\n❌ Žádné dokumenty k zobrazení")
            return

        print("\n" + "=" * 120)
        print(f"📄 DOKUMENTY (stránka {page + 1}, zobrazeno {len(docs_page)} z {len(self.filtered_documents)})")
        print("=" * 120)

        print(f"{'#':>3} {'✓':^3} {'Typ':20} {'Confidence':>10} {'Datum':12} {'Velikost':>8} {'Název':40}")
        print("-" * 120)

        for i, doc in enumerate(docs_page, start=start + 1):
            selected = "✓" if doc.get('selected', False) else " "
            doc_type = doc.get('document_type', 'unknown')[:20]
            confidence = doc.get('confidence', 0)
            file_date = doc.get('file_date_formatted', '')[:12]
            file_size = f"{doc.get('file_size_mb', 0):.1f}MB"
            file_name = doc.get('file_name', '')[:40]

            # Color coding by confidence
            if confidence >= 0.9:
                conf_str = f"\033[92m{confidence:.2f}\033[0m"  # Green
            elif confidence >= 0.7:
                conf_str = f"\033[93m{confidence:.2f}\033[0m"  # Yellow
            else:
                conf_str = f"\033[91m{confidence:.2f}\033[0m"  # Red

            print(f"{i:3d} [{selected}] {doc_type:20} {conf_str:>10} {file_date:12} {file_size:>8} {file_name:40}")

        print("=" * 120)
        print()

    def print_filters(self):
        """Vypsat aktivní filtry"""
        print("\n📊 AKTIVNÍ FILTRY:")
        print("-" * 80)

        active_filters = []
        if self.filters['document_type']:
            active_filters.append(f"Typ: {self.filters['document_type']}")
        if self.filters['min_confidence'] is not None:
            active_filters.append(f"Min confidence: {self.filters['min_confidence']}")
        if self.filters['max_confidence'] is not None:
            active_filters.append(f"Max confidence: {self.filters['max_confidence']}")
        if self.filters['date_from']:
            active_filters.append(f"Od: {self.filters['date_from']}")
        if self.filters['date_to']:
            active_filters.append(f"Do: {self.filters['date_to']}")
        if self.filters['selected_only']:
            active_filters.append("Pouze vybrané")

        if active_filters:
            for f in active_filters:
                print(f"  • {f}")
        else:
            print("  Žádné aktivní filtry")

        print("-" * 80)

    def print_statistics(self):
        """Vypsat statistiky"""
        total = len(self.all_documents)
        filtered = len(self.filtered_documents)
        selected = len(self.get_selected_documents())

        print("\n" + "=" * 80)
        print("📊 STATISTIKY")
        print("=" * 80)
        print(f"  Celkem dokumentů:      {total}")
        print(f"  Po filtrování:         {filtered} ({filtered/total*100:.1f}%)")
        print(f"  Vybrané:               {selected} ({selected/total*100:.1f}%)")
        print("=" * 80)

    def export_selected(self, output_file: str):
        """
        Exportovat vybrané dokumenty pro Paperless

        Args:
            output_file: Výstupní JSON soubor
        """
        selected = self.get_selected_documents()

        if not selected:
            print("\n❌ Žádné dokumenty k exportu (žádný není vybrán)")
            return

        # Prepare for Paperless
        paperless_data = {
            'export_date': datetime.now().isoformat(),
            'total_documents': len(selected),
            'documents': []
        }

        for doc in selected:
            paperless_doc = {
                'file_path': doc.get('file_path'),
                'file_name': doc.get('file_name'),
                'title': doc.get('paperless_title'),
                'document_type': doc.get('document_type'),
                'tags': doc.get('paperless_tags', []),
                'correspondent': doc.get('paperless_correspondent'),
                'confidence': doc.get('confidence'),
                'ocr_text': doc.get('text', '')[:1000],  # First 1000 chars
            }
            paperless_data['documents'].append(paperless_doc)

        # Save
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(paperless_data, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Exportováno {len(selected)} dokumentů do: {output_path}")

    def interactive_menu(self):
        """Interaktivní menu"""
        page = 0
        per_page = 20

        while True:
            # Apply filters
            self.apply_filters()

            # Show documents
            self.print_documents(page, per_page)
            self.print_filters()
            self.print_statistics()

            print("\n" + "=" * 80)
            print("📋 MENU")
            print("=" * 80)
            print("  [n] Další stránka   [p] Předchozí stránka   [g] Jít na stránku")
            print("  [t] Toggle výběr    [a] Vybrat vše          [d] Zrušit vše")
            print("  [f] Filtry          [r] Reset filtrů        [s] Statistiky")
            print("  [e] Export          [q] Konec")
            print("=" * 80)

            choice = input("\nVolba: ").strip().lower()

            if choice == 'q':
                print("\n👋 Ukončuji...")
                break

            elif choice == 'n':
                if (page + 1) * per_page < len(self.filtered_documents):
                    page += 1
                else:
                    print("❌ Již jste na poslední stránce")

            elif choice == 'p':
                if page > 0:
                    page -= 1
                else:
                    print("❌ Již jste na první stránce")

            elif choice == 'g':
                try:
                    page_num = int(input("Číslo stránky: ")) - 1
                    if 0 <= page_num < (len(self.filtered_documents) + per_page - 1) // per_page:
                        page = page_num
                    else:
                        print("❌ Neplatné číslo stránky")
                except ValueError:
                    print("❌ Neplatný vstup")

            elif choice == 't':
                try:
                    index = int(input("Číslo dokumentu: ")) - 1
                    self.toggle_selection(index)
                except ValueError:
                    print("❌ Neplatný vstup")

            elif choice == 'a':
                self.select_all()
                print(f"✅ Vybráno {len(self.filtered_documents)} dokumentů")

            elif choice == 'd':
                self.deselect_all()
                print("✅ Zrušen výběr všech dokumentů")

            elif choice == 'f':
                self._filter_menu()
                page = 0  # Reset to first page after filtering

            elif choice == 'r':
                self.filters = {k: None if k != 'selected_only' else False
                              for k in self.filters}
                page = 0
                print("✅ Filtry resetovány")

            elif choice == 's':
                self.print_statistics()
                input("\nStiskni Enter...")

            elif choice == 'e':
                output_file = input("Výstupní soubor [data/paperless_import.json]: ").strip()
                if not output_file:
                    output_file = "data/paperless_import.json"
                self.export_selected(output_file)
                input("\nStiskni Enter...")

    def _filter_menu(self):
        """Menu pro nastavení filtrů"""
        while True:
            print("\n" + "=" * 80)
            print("🔍 FILTRY")
            print("=" * 80)
            print("  [1] Typ dokumentu")
            print("  [2] Min confidence")
            print("  [3] Max confidence")
            print("  [4] Datum od")
            print("  [5] Datum do")
            print("  [6] Pouze vybrané")
            print("  [r] Reset")
            print("  [b] Zpět")
            print("=" * 80)

            choice = input("\nVolba: ").strip().lower()

            if choice == 'b':
                break

            elif choice == 'r':
                self.filters = {k: None if k != 'selected_only' else False
                              for k in self.filters}
                print("✅ Filtry resetovány")

            elif choice == '1':
                types = self.get_unique_document_types()
                print("\nDostupné typy:")
                for i, t in enumerate(types, 1):
                    print(f"  [{i}] {t}")
                print("  [0] Zrušit filtr")

                try:
                    type_choice = int(input("\nVolba: "))
                    if type_choice == 0:
                        self.filters['document_type'] = None
                        print("✅ Filtr zrušen")
                    elif 1 <= type_choice <= len(types):
                        self.filters['document_type'] = types[type_choice - 1]
                        print(f"✅ Filtr nastaven: {self.filters['document_type']}")
                except ValueError:
                    print("❌ Neplatný vstup")

            elif choice == '2':
                try:
                    val = input("Min confidence (0.0-1.0, Enter = zrušit): ").strip()
                    if val:
                        self.filters['min_confidence'] = float(val)
                        print(f"✅ Min confidence: {self.filters['min_confidence']}")
                    else:
                        self.filters['min_confidence'] = None
                        print("✅ Filtr zrušen")
                except ValueError:
                    print("❌ Neplatný vstup")

            elif choice == '3':
                try:
                    val = input("Max confidence (0.0-1.0, Enter = zrušit): ").strip()
                    if val:
                        self.filters['max_confidence'] = float(val)
                        print(f"✅ Max confidence: {self.filters['max_confidence']}")
                    else:
                        self.filters['max_confidence'] = None
                        print("✅ Filtr zrušen")
                except ValueError:
                    print("❌ Neplatný vstup")

            elif choice == '4':
                val = input("Datum od (YYYY-MM-DD, Enter = zrušit): ").strip()
                if val:
                    try:
                        datetime.strptime(val, "%Y-%m-%d")
                        self.filters['date_from'] = val
                        print(f"✅ Datum od: {self.filters['date_from']}")
                    except ValueError:
                        print("❌ Neplatný formát data")
                else:
                    self.filters['date_from'] = None
                    print("✅ Filtr zrušen")

            elif choice == '5':
                val = input("Datum do (YYYY-MM-DD, Enter = zrušit): ").strip()
                if val:
                    try:
                        datetime.strptime(val, "%Y-%m-%d")
                        self.filters['date_to'] = val
                        print(f"✅ Datum do: {self.filters['date_to']}")
                    except ValueError:
                        print("❌ Neplatný formát data")
                else:
                    self.filters['date_to'] = None
                    print("✅ Filtr zrušen")

            elif choice == '6':
                self.filters['selected_only'] = not self.filters['selected_only']
                status = "zapnuto" if self.filters['selected_only'] else "vypnuto"
                print(f"✅ Pouze vybrané: {status}")


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='MAJ Document Recognition - Interactive Selector')
    parser.add_argument('--results', '-r',
                       default='data/mbw_processed.json',
                       help='JSON soubor s výsledky zpracování')

    args = parser.parse_args()

    try:
        selector = DocumentSelector(args.results)
        selector.interactive_menu()

    except FileNotFoundError as e:
        print(f"\n❌ Chyba: {e}")
        print("\n💡 Nejprve spusť: python process_mbw_documents.py")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n👋 Přerušeno uživatelem")
        sys.exit(0)


if __name__ == "__main__":
    main()
