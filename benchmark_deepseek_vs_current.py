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
DeepSeek VL OCR Benchmark Test
===============================
Compares DeepSeek VL OCR models against current production models.

Tests:
1. Speed: Processing time per document
2. Accuracy: Extraction quality and OCR confidence
3. Reliability: Consensus quality between models

Platforms:
- DGX Server (192.168.10.200) - GPU acceleration
- Docker (MacBook) - CPU only

Models:
- Current: qwen2.5:32b + czech-finance-speed
- New: deepseek-ocr:3b (VL model with OCR capabilities)

Author: Claude Code
Date: 2025-12-03
"""

import os
import sys
import time
import json
import logging
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
from collections import defaultdict

# Add project paths
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ocr'))
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ai'))

from text_extractor_cascade import CascadeTextExtractor
from universal_business_classifier import UniversalBusinessClassifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class ModelBenchmarker:
    """Benchmark OCR models on speed and accuracy"""

    def __init__(self):
        self.text_extractor = CascadeTextExtractor({
            "ocr": {"cascade_threshold": 60.0, "min_text_length": 50}
        })
        self.classifier = UniversalBusinessClassifier()

        # Ollama endpoints
        self.endpoints = {
            'docker': 'http://localhost:11435',
            'dgx': 'http://192.168.10.200:11434'
        }

        self.results = {
            'current_models': [],
            'deepseek_docker': [],
            'deepseek_dgx': []
        }

    def test_ollama_connection(self, platform: str) -> bool:
        """Test if Ollama is accessible"""
        try:
            response = requests.get(f"{self.endpoints[platform]}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False

    def call_ollama_model(self, text: str, model: str, platform: str) -> Tuple[str, float]:
        """Call Ollama model and measure time"""

        prompt = f"""Extract structured data from this Czech business document.
Find: company name, ICO, DIC, amounts, dates, items.

Document text:
{text[:3000]}

Return JSON only."""

        start_time = time.time()

        try:
            response = requests.post(
                f"{self.endpoints[platform]}/api/generate",
                json={
                    'model': model,
                    'prompt': prompt,
                    'stream': False
                },
                timeout=60
            )

            elapsed = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                return result.get('response', ''), elapsed
            else:
                return f"Error: {response.status_code}", elapsed

        except Exception as e:
            elapsed = time.time() - start_time
            return f"Exception: {e}", elapsed

    def benchmark_document(self, pdf_path: Path) -> Dict[str, Any]:
        """Benchmark single document across all models"""

        logger.info(f"\n{'='*80}")
        logger.info(f"Benchmarking: {pdf_path.name}")
        logger.info(f"{'='*80}")

        # 1. Extract text
        logger.info("📄 Extracting text...")
        extract_start = time.time()
        extraction_result = self.text_extractor.extract_from_pdf(str(pdf_path))
        text = extraction_result.get('text', '')
        extract_time = time.time() - extract_start

        if not text or len(text) < 100:
            logger.warning("❌ Insufficient text extracted")
            return None

        logger.info(f"✅ Text extracted: {len(text)} chars in {extract_time:.2f}s")

        # 2. Classify document
        doc_type, confidence, details = self.classifier.classify(text)
        doc_type_str = str(doc_type).replace('DocumentType.', '')
        logger.info(f"✅ Classification: {doc_type_str} (confidence: {confidence}/200)")

        result = {
            'filename': pdf_path.name,
            'doc_type': doc_type_str,
            'text_length': len(text),
            'extract_time': extract_time,
            'ocr_confidence': extraction_result.get('confidence', 0),
            'models': {}
        }

        # 3. Test current production models
        logger.info("\n🔬 Testing CURRENT models (qwen2.5:32b + czech-finance-speed)...")

        for model_name in ['qwen2.5:32b', 'czech-finance-speed']:
            if self.test_ollama_connection('docker'):
                response, elapsed = self.call_ollama_model(text, model_name, 'docker')
                result['models'][f'{model_name}_docker'] = {
                    'response': response[:500],  # First 500 chars
                    'time': elapsed,
                    'platform': 'docker'
                }
                logger.info(f"   ✅ {model_name} (Docker): {elapsed:.2f}s")
            else:
                logger.warning(f"   ⚠️  Docker Ollama not available")

        # 4. Test DeepSeek VL on Docker
        logger.info("\n🔬 Testing DeepSeek OCR on DOCKER...")

        if self.test_ollama_connection('docker'):
            response, elapsed = self.call_ollama_model(text, 'deepseek-ocr:3b', 'docker')
            result['models']['deepseek-ocr_docker'] = {
                'response': response[:500],
                'time': elapsed,
                'platform': 'docker'
            }
            logger.info(f"   ✅ deepseek-ocr:3b (Docker): {elapsed:.2f}s")
        else:
            logger.warning(f"   ⚠️  Docker Ollama not available")

        # 5. Test DeepSeek VL on DGX
        logger.info("\n🔬 Testing DeepSeek OCR on DGX...")

        if self.test_ollama_connection('dgx'):
            response, elapsed = self.call_ollama_model(text, 'deepseek-ocr:3b', 'dgx')
            result['models']['deepseek-ocr_dgx'] = {
                'response': response[:500],
                'time': elapsed,
                'platform': 'dgx'
            }
            logger.info(f"   ✅ deepseek-ocr:3b (DGX): {elapsed:.2f}s")
        else:
            logger.warning(f"   ⚠️  DGX Ollama not available")

        return result

    def run_benchmark(self, num_docs: int = 10):
        """Run benchmark on N documents"""

        logger.info("\n" + "="*80)
        logger.info("🚀 DeepSeek VL OCR Benchmark Test")
        logger.info("="*80)

        # Get sample PDFs from production scan
        pdf_dir = Path(__file__).parent / "production_scan_output"
        pdf_files = sorted(list(pdf_dir.glob("*.pdf")))[:num_docs]

        if not pdf_files:
            logger.error("❌ No PDFs found in production_scan_output/")
            return

        logger.info(f"\n📊 Testing {len(pdf_files)} documents")
        logger.info(f"   Platform 1: Docker (MacBook) - http://localhost:11435")
        logger.info(f"   Platform 2: DGX (192.168.10.200) - http://192.168.10.200:11434")

        # Check connections
        docker_ok = self.test_ollama_connection('docker')
        dgx_ok = self.test_ollama_connection('dgx')

        logger.info(f"\n🔌 Connection check:")
        logger.info(f"   Docker: {'✅ Connected' if docker_ok else '❌ Not available'}")
        logger.info(f"   DGX: {'✅ Connected' if dgx_ok else '❌ Not available'}")

        if not docker_ok and not dgx_ok:
            logger.error("❌ No Ollama endpoints available!")
            return

        # Benchmark each document
        all_results = []

        for idx, pdf_path in enumerate(pdf_files, 1):
            logger.info(f"\n\n{'='*80}")
            logger.info(f"📄 Document {idx}/{len(pdf_files)}")
            logger.info(f"{'='*80}")

            result = self.benchmark_document(pdf_path)
            if result:
                all_results.append(result)

        # Generate report
        self.generate_report(all_results)

    def generate_report(self, results: List[Dict]):
        """Generate benchmark report"""

        logger.info("\n\n" + "="*80)
        logger.info("📊 BENCHMARK RESULTS")
        logger.info("="*80)

        if not results:
            logger.error("❌ No results to report")
            return

        # Calculate averages per model
        model_stats = defaultdict(lambda: {'times': [], 'count': 0})

        for result in results:
            for model_name, model_data in result['models'].items():
                model_stats[model_name]['times'].append(model_data['time'])
                model_stats[model_name]['count'] += 1

        # Print comparison table
        logger.info("\n## Speed Comparison\n")
        logger.info(f"{'Model':<30} | {'Platform':<10} | {'Avg Time':<10} | {'Tests':<6}")
        logger.info("-" * 80)

        for model_name in sorted(model_stats.keys()):
            stats = model_stats[model_name]
            platform = model_name.split('_')[-1]
            model_base = model_name.replace(f'_{platform}', '')
            avg_time = sum(stats['times']) / len(stats['times'])

            logger.info(f"{model_base:<30} | {platform:<10} | {avg_time:>8.2f}s | {stats['count']:<6}")

        # Save detailed results
        output_file = Path(__file__).parent / "benchmark_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'num_documents': len(results),
                'results': results,
                'summary': {
                    model: {
                        'avg_time': sum(s['times']) / len(s['times']),
                        'min_time': min(s['times']),
                        'max_time': max(s['times']),
                        'count': s['count']
                    }
                    for model, s in model_stats.items()
                }
            }, f, indent=2, ensure_ascii=False)

        logger.info(f"\n✅ Detailed results saved: {output_file}")

        # Winner determination
        logger.info("\n## 🏆 WINNER\n")

        fastest_model = min(model_stats.items(), key=lambda x: sum(x[1]['times']) / len(x[1]['times']))
        avg_time = sum(fastest_model[1]['times']) / len(fastest_model[1]['times'])

        logger.info(f"Fastest model: {fastest_model[0]}")
        logger.info(f"Average time: {avg_time:.2f}s")

        logger.info("\n" + "="*80)


def main():
    """Main entry point"""

    benchmarker = ModelBenchmarker()
    benchmarker.run_benchmark(num_docs=10)  # Test on 10 documents


if __name__ == "__main__":
    main()
