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
Quick DeepSeek Test on DGX
===========================
Fast test of DeepSeek OCR on DGX server while Docker is pulling models.

Author: Claude Code
Date: 2025-12-03
"""

import sys
import time
import json
import logging
import requests
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def test_dgx_deepseek():
    """Quick test of DeepSeek on DGX"""

    logger.info("🚀 Quick DeepSeek OCR Test on DGX")
    logger.info("=" * 80)

    # Get one sample PDF
    pdf_dir = Path(__file__).parent / "production_scan_output"
    pdf_files = sorted(list(pdf_dir.glob("*.pdf")))[:3]  # Just 3 docs for quick test

    if not pdf_files:
        logger.error("❌ No PDFs found")
        return

    # Test connection
    dgx_endpoint = "http://192.168.10.200:11434"
    try:
        response = requests.get(f"{dgx_endpoint}/api/tags", timeout=5)
        if response.status_code == 200:
            logger.info(f"✅ DGX Ollama connected: {dgx_endpoint}")
        else:
            logger.error(f"❌ DGX Ollama not responding")
            return
    except Exception as e:
        logger.error(f"❌ Cannot connect to DGX: {e}")
        return

    # Quick test with sample text
    logger.info("\n📄 Testing with sample Czech invoice text...")

    sample_text = """
FAKTURA č. 2025001

Dodavatel:
Firma ABC s.r.o.
IČO: 12345678
DIČ: CZ12345678

Odběratel:
XYZ a.s.
IČO: 87654321

Položky:
1. Notebook Dell Latitude 5420 - 25 990 Kč
2. Myš Logitech MX Master 3 - 2 490 Kč
3. Klávesnice Logitech MX Keys - 3 290 Kč

Cena celkem bez DPH: 31 770 Kč
DPH 21%: 6 671,70 Kč
Cena celkem s DPH: 38 441,70 Kč

Datum vystavení: 2025-03-15
Datum splatnosti: 2025-04-15
"""

    prompt = f"""Extract structured data from this Czech business document.
Find: company name, ICO, DIC, amounts, dates, items.

Document text:
{sample_text}

Return JSON only with extracted fields."""

    logger.info(f"\n🔬 Testing deepseek-ocr:3b on DGX...")

    start_time = time.time()

    try:
        response = requests.post(
            f"{dgx_endpoint}/api/generate",
            json={
                'model': 'deepseek-ocr:3b',
                'prompt': prompt,
                'stream': False
            },
            timeout=60
        )

        elapsed = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            response_text = result.get('response', '')

            logger.info(f"\n✅ Response received in {elapsed:.2f}s")
            logger.info(f"\n📊 DeepSeek OCR Output:")
            logger.info("=" * 80)
            logger.info(response_text[:500])  # First 500 chars
            logger.info("=" * 80)

            logger.info(f"\n🎯 Speed test result: {elapsed:.2f}s for ~200 chars input")
            logger.info(f"   GPU acceleration: {'Yes (DGX)' if elapsed < 5 else 'Maybe not using GPU?'}")

            return True

        else:
            logger.error(f"❌ Error: {response.status_code}")
            return False

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ Exception after {elapsed:.2f}s: {e}")
        return False


if __name__ == "__main__":
    test_dgx_deepseek()
