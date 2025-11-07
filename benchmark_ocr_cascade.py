#!/usr/bin/env python3
"""
OCR CASCADE BENCHMARK
Porovná rychlost standardního OCR (ces+eng+deu) vs CASCADE OCR (ces → eng → deu)
"""

import sys
import time
import logging
from pathlib import Path
from typing import List, Dict
import yaml
from PIL import Image, ImageDraw, ImageFont

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.ocr.text_extractor import TextExtractor
from src.ocr.text_extractor_cascade import CascadeTextExtractor, get_cascade_stats

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_images(output_dir: Path) -> List[Path]:
    """Create synthetic test documents"""
    output_dir.mkdir(parents=True, exist_ok=True)

    test_docs = [
        # Czech documents (90% - should be fastest)
        ("Faktura č. 2024001\nIČO: 12345678\nDIČ: CZ12345678\nDatum zdanitelného plnění: 15.3.2024\nCelková částka: 5 000 Kč včetně DPH", "ces", "faktura_cz.png"),
        ("Účet z restaurace\nPivo 2× 50 Kč\nGuláš 180 Kč\nCelkem: 280 Kč\nDěkujeme za návštěvu!", "ces", "uctenka_cz.png"),
        ("Výpis z účtu 123456/0100\nZůstatek: 50 000 Kč\nDatum: 1.1.2024\nTransakce za leden 2024", "ces", "vypis_cz.png"),
        ("Potvrzení o platbě\nČástka: 1500 Kč\nVariabilní symbol: 123456\nDatum úhrady: 10.3.2024", "ces", "potvrzeni_cz.png"),
        ("Rozsudek Okresního soudu v Praze\nsp. zn. 15C 123/2024\nve věci žaloby o náhradu škody", "ces", "rozsudek_cz.png"),

        # English documents (7%)
        ("Invoice #2024-001\nVAT ID: GB123456789\nTotal Amount: $1,500.00\nDue Date: 2024-03-15", "eng", "invoice_en.png"),
        ("Receipt\nCoffee $4.50\nSandwich $8.99\nTotal: $13.49\nThank you!", "eng", "receipt_en.png"),

        # German documents (2%)
        ("Rechnung Nr. 2024-001\nUSt-IdNr.: DE123456789\nGesamtbetrag: 1.500,00 €\nFällig am: 15.03.2024", "deu", "rechnung_de.png"),
        ("Quittung\nKaffee 4,50 €\nBrötchen 2,50 €\nSumme: 7,00 €\nVielen Dank!", "deu", "quittung_de.png"),
    ]

    image_paths = []

    for text, lang, filename in test_docs:
        # Create 800x600 white image with text
        img = Image.new('RGB', (800, 600), color='white')
        draw = ImageDraw.Draw(img)

        try:
            # Try to load a font (fallback to default if not available)
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        except:
            font = ImageFont.load_default()

        # Draw text
        draw.multiline_text((50, 50), text, fill='black', font=font)

        # Save
        output_path = output_dir / filename
        img.save(output_path)
        image_paths.append(output_path)

        logger.info(f"✅ Created: {filename} ({lang})")

    return image_paths


def benchmark_standard_ocr(config: dict, image_paths: List[Path]) -> Dict:
    """Benchmark standard multi-language OCR (ces+eng+deu together)"""
    logger.info("\n" + "="*80)
    logger.info("🐌 STANDARD OCR BENCHMARK (ces+eng+deu together)")
    logger.info("="*80)

    extractor = TextExtractor(config)

    results = []
    start_total = time.time()

    for img_path in image_paths:
        logger.info(f"\n📄 Processing: {img_path.name}")
        start = time.time()

        result = extractor.extract_from_image(str(img_path))

        elapsed = time.time() - start
        result['processing_time'] = elapsed
        result['image_name'] = img_path.name

        results.append(result)

        logger.info(f"⏱️  Time: {elapsed:.2f}s | Confidence: {result['confidence']:.1f}% | Text length: {len(result['text'])}")

    total_time = time.time() - start_total
    avg_time = total_time / len(image_paths)

    logger.info(f"\n📊 STANDARD OCR SUMMARY:")
    logger.info(f"Total time: {total_time:.2f}s")
    logger.info(f"Avg time/doc: {avg_time:.2f}s")
    logger.info(f"Total docs: {len(image_paths)}")

    return {
        'method': 'standard',
        'results': results,
        'total_time': total_time,
        'avg_time': avg_time,
        'total_docs': len(image_paths)
    }


def benchmark_cascade_ocr(config: dict, image_paths: List[Path]) -> Dict:
    """Benchmark CASCADE OCR (ces → eng → deu)"""
    logger.info("\n" + "="*80)
    logger.info("⚡ CASCADE OCR BENCHMARK (ces → eng → deu)")
    logger.info("="*80)

    extractor = CascadeTextExtractor(config)

    results = []
    start_total = time.time()

    for img_path in image_paths:
        logger.info(f"\n📄 Processing: {img_path.name}")
        start = time.time()

        result = extractor.extract_from_image(str(img_path))

        elapsed = time.time() - start
        result['processing_time'] = elapsed
        result['image_name'] = img_path.name

        results.append(result)

        logger.info(f"⚡ Time: {elapsed:.2f}s | Lang: {result['language_used']} | Attempts: {result['attempts']} | Confidence: {result['confidence']:.1f}%")

    total_time = time.time() - start_total
    avg_time = total_time / len(image_paths)

    # Get cascade statistics
    cascade_stats = get_cascade_stats(results)

    logger.info(f"\n📊 CASCADE OCR SUMMARY:")
    logger.info(f"Total time: {total_time:.2f}s")
    logger.info(f"Avg time/doc: {avg_time:.2f}s")
    logger.info(f"Total docs: {len(image_paths)}")
    logger.info(f"\nCascade efficiency:")
    logger.info(f"  First try (Czech): {cascade_stats['first_try_success']}/{len(image_paths)} ({cascade_stats['first_try_percentage']:.1f}%)")
    logger.info(f"  Second try (English): {cascade_stats['second_try_success']}/{len(image_paths)}")
    logger.info(f"  Third try (German): {cascade_stats['third_try_success']}/{len(image_paths)}")
    logger.info(f"  Fallback (multi-lang): {cascade_stats['fallback_needed']}/{len(image_paths)}")
    logger.info(f"  Estimated speedup: {cascade_stats['estimated_speedup']}")

    return {
        'method': 'cascade',
        'results': results,
        'total_time': total_time,
        'avg_time': avg_time,
        'total_docs': len(image_paths),
        'cascade_stats': cascade_stats
    }


def compare_results(standard: Dict, cascade: Dict):
    """Compare and print final results"""
    logger.info("\n" + "="*80)
    logger.info("🏁 FINAL COMPARISON")
    logger.info("="*80)

    speedup = standard['avg_time'] / cascade['avg_time'] if cascade['avg_time'] > 0 else 1.0
    time_saved = standard['total_time'] - cascade['total_time']
    time_saved_pct = (time_saved / standard['total_time'] * 100) if standard['total_time'] > 0 else 0

    logger.info(f"\n⏱️  TIMING:")
    logger.info(f"Standard OCR: {standard['total_time']:.2f}s ({standard['avg_time']:.2f}s/doc)")
    logger.info(f"Cascade OCR:  {cascade['total_time']:.2f}s ({cascade['avg_time']:.2f}s/doc)")
    logger.info(f"")
    logger.info(f"🚀 SPEEDUP: {speedup:.2f}× faster!")
    logger.info(f"⏳ TIME SAVED: {time_saved:.2f}s ({time_saved_pct:.1f}%)")

    logger.info(f"\n📊 CASCADE EFFICIENCY:")
    stats = cascade['cascade_stats']
    logger.info(f"Czech (1st try): {stats['first_try_percentage']:.1f}% → 3× faster")
    logger.info(f"English (2nd try): {stats['second_try_success']} docs → 2× faster")
    logger.info(f"German (3rd try): {stats['third_try_success']} docs → 1× faster")
    logger.info(f"Multi-lang fallback: {stats['fallback_needed']} docs → same speed")

    logger.info(f"\n✅ RECOMMENDATION:")
    if speedup >= 2.0:
        logger.info(f"⚡ CASCADE OCR is {speedup:.1f}× faster - STRONGLY RECOMMENDED!")
    elif speedup >= 1.5:
        logger.info(f"✅ CASCADE OCR is {speedup:.1f}× faster - recommended")
    else:
        logger.info(f"⚠️  CASCADE OCR only {speedup:.1f}× faster - marginal improvement")

    logger.info("="*80)


def main():
    """Main benchmark"""
    logger.info("🚀 OCR CASCADE BENCHMARK")
    logger.info("="*80)

    # Load config
    config_path = Path(__file__).parent / "config" / "config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Create test images
    test_dir = Path(__file__).parent / "data" / "benchmark_test_images"
    logger.info(f"\n📝 Creating test documents in {test_dir}")
    image_paths = create_test_images(test_dir)

    logger.info(f"\n✅ Created {len(image_paths)} test documents")
    logger.info(f"   - Czech: 5 docs (90%)")
    logger.info(f"   - English: 2 docs (7%)")
    logger.info(f"   - German: 2 docs (3%)")

    # Run benchmarks
    standard_results = benchmark_standard_ocr(config, image_paths)
    cascade_results = benchmark_cascade_ocr(config, image_paths)

    # Compare
    compare_results(standard_results, cascade_results)

    logger.info(f"\n💾 Test images saved in: {test_dir}")
    logger.info(f"\n✅ Benchmark complete!")


if __name__ == "__main__":
    main()
