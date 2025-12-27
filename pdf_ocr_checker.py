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
PDF OCR Checker & Auto-OCR v1.0
================================

Kontroluje zda PDF má OCR vrstvu, pokud ne - automaticky přidá pomocí OCRmyPDF.
"""

import subprocess
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def has_ocr_layer(pdf_path: str) -> tuple[bool, str]:
    """
    Zkontroluje zda PDF má OCR vrstvu pomocí pdftotext.

    Returns:
        tuple: (has_ocr: bool, reason: str)
    """
    try:
        # Pokusí se extrahovat text pomocí pdftotext
        result = subprocess.run(
            ['pdftotext', pdf_path, '-'],
            capture_output=True,
            text=True,
            timeout=30
        )

        extracted_text = result.stdout.strip()

        if len(extracted_text) > 100:  # Alespoň 100 znaků = má OCR
            return True, f"OCR vrstva OK ({len(extracted_text)} znaků)"
        elif len(extracted_text) > 0:
            return False, f"Málo textu ({len(extracted_text)} znaků) - možná chybí OCR"
        else:
            return False, "Žádný text - PDF nemá OCR vrstvu"

    except subprocess.TimeoutExpired:
        return False, "Timeout při kontrole OCR"
    except FileNotFoundError:
        return False, "pdftotext není nainstalován (brew install poppler)"
    except Exception as e:
        return False, f"Chyba při kontrole: {str(e)}"


def add_ocr_to_pdf(pdf_path: str, output_path: str = None, language: str = "ces+eng") -> tuple[bool, str]:
    """
    Přidá OCR vrstvu do PDF pomocí OCRmyPDF.

    Args:
        pdf_path: Cesta k vstupnímu PDF
        output_path: Cesta k výstupnímu PDF (None = přepíše vstupní)
        language: OCR jazyk (ces+eng, ces, eng, deu)

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        if output_path is None:
            output_path = pdf_path + ".ocr.pdf"

        # OCRmyPDF s optimalizovanými parametry
        cmd = [
            'ocrmypdf',
            '--language', language,
            '--deskew',  # Narovná naskenované stránky
            '--rotate-pages',  # Automaticky otočí stránky
            '--remove-background',  # Odstraní šedé pozadí
            '--optimize', '1',  # Základní optimalizace (rychlá)
            '--force-ocr',  # Vždy přidá OCR, i když už nějaký text je
            pdf_path,
            output_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minut timeout
        )

        if result.returncode == 0:
            # Přepíše původní soubor
            if output_path != pdf_path:
                os.replace(output_path, pdf_path)

            # Ověří že OCR bylo přidáno
            has_ocr, reason = has_ocr_layer(pdf_path)
            if has_ocr:
                return True, f"OCR úspěšně přidáno: {reason}"
            else:
                return False, f"OCR přidáno, ale stále málo textu: {reason}"
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            return False, f"OCRmyPDF selhalo: {error_msg[:200]}"

    except subprocess.TimeoutExpired:
        return False, "Timeout při OCR (>5 minut)"
    except FileNotFoundError:
        return False, "ocrmypdf není nainstalován (brew install ocrmypdf)"
    except Exception as e:
        return False, f"Chyba při OCR: {str(e)}"


def check_and_fix_pdf(pdf_path: str, auto_fix: bool = True) -> dict:
    """
    Zkontroluje PDF a případně přidá OCR vrstvu.

    Args:
        pdf_path: Cesta k PDF souboru
        auto_fix: Automaticky přidat OCR pokud chybí

    Returns:
        dict: {
            'has_ocr': bool,
            'fixed': bool,
            'message': str,
            'status': 'ok' | 'fixed' | 'error'
        }
    """
    result = {
        'has_ocr': False,
        'fixed': False,
        'message': '',
        'status': 'error'
    }

    # 1. Kontrola OCR
    has_ocr, check_msg = has_ocr_layer(pdf_path)
    result['has_ocr'] = has_ocr

    if has_ocr:
        result['status'] = 'ok'
        result['message'] = check_msg
        return result

    # 2. Nemá OCR - přidat?
    if not auto_fix:
        result['status'] = 'error'
        result['message'] = f"⚠️ {check_msg}"
        return result

    # 3. Přidat OCR
    logger.info(f"Přidávám OCR do: {Path(pdf_path).name}")
    success, fix_msg = add_ocr_to_pdf(pdf_path)

    if success:
        result['fixed'] = True
        result['has_ocr'] = True
        result['status'] = 'fixed'
        result['message'] = f"✅ {fix_msg}"
    else:
        result['status'] = 'error'
        result['message'] = f"❌ {fix_msg}"

    return result


def is_supported_format(file_path: str) -> tuple[bool, str, str]:
    """
    Zkontroluje zda je formát souboru podporován.

    Returns:
        tuple: (is_supported: bool, format: str, message: str)
    """
    ext = Path(file_path).suffix.lower()

    # Podporované formáty
    SUPPORTED = {
        '.pdf': 'PDF Document',
        '.jpg': 'JPEG Image',
        '.jpeg': 'JPEG Image',
        '.png': 'PNG Image',
        '.tif': 'TIFF Image',
        '.tiff': 'TIFF Image',
        '.xml': 'XML Bank Statement',
        '.txt': 'Text Document'
    }

    if ext in SUPPORTED:
        return True, SUPPORTED[ext], f"Podporovaný formát: {SUPPORTED[ext]}"
    else:
        return False, f"Unknown ({ext})", f"⚠️ Neznámý formát: {ext}"


# Testování
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python3 pdf_ocr_checker.py <pdf_file>")
        sys.exit(1)

    pdf_file = sys.argv[1]

    print(f"\n{'='*60}")
    print(f"PDF OCR Checker - Testing: {Path(pdf_file).name}")
    print(f"{'='*60}\n")

    # Test format check
    is_supported, fmt, msg = is_supported_format(pdf_file)
    print(f"Format: {fmt}")
    print(f"Status: {msg}\n")

    if not is_supported:
        print("⚠️ Unsupported format!")
        sys.exit(1)

    if fmt == 'PDF Document':
        # Test OCR check
        result = check_and_fix_pdf(pdf_file, auto_fix=True)

        print(f"Has OCR: {result['has_ocr']}")
        print(f"Fixed: {result['fixed']}")
        print(f"Status: {result['status']}")
        print(f"Message: {result['message']}")
