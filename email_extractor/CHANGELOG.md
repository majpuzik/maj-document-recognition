# Email Extractor Changelog

## [2.1.0] - 2025-12-17

### Added
- **tqdm progress bar in ALL modules**
  - `phase1_docling.py` - shows success/failed/CPU/RAM
  - `phase2_llm.py` - shows success/failed/skipped/type
  - `phase2_direct.py` - shows success/failed/type
  - `phase2_hierarchical.py` - shows success/failed/escalated-to-32B/type
  - `phase2_macbook.py` - shows success/failed/skipped/type
  - `phase3_gpt4.py` - shows success/failed/tokens/type
  - `phase5_import.py` - shows uploaded/failed/skipped + custom fields progress
  - `phase6_fix_tags.py` - shows success/failed/skipped (pagination-based)
- **Graceful fallback** when tqdm not installed (`HAS_TQDM` flag)
- Real-time ETA and rate display in all progress bars

### Changed
- All modules now have consistent progress bar format:
  `{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]`

---

## [2.0.0] - 2024-12-17

### Added
- **Multi-machine support** in `phase2_llm.py`
  - Auto-detection hostname (spark* = DGX, macbook = MacBook, default = Mac Mini)
  - Appropriate path configuration per machine
- **File-based atomic locking**
  - Prevents duplicate processing across machines
  - `os.O_CREAT | os.O_EXCL` for atomic create
  - Stale lock cleanup after 10 minutes
- **tqdm progress bar**
  - Real-time progress with ETA
  - Shows success/failed/skipped counts
  - Shows current document type
- **Skip already processed**
  - Checks both phase1_results and phase2_results
- **Enhanced field extraction in LLM prompt**
  - direction (příjem/výdaj/neutrální)
  - protistrana_ico
  - castka_celkem
- **CLI arguments**
  - `--workers` for future parallel support

### Changed
- Model upgraded to `qwen2.5:32b` (was 14b)
- Timeout increased to 180s (was 120s)
- Added `num_ctx: 4096` to LLM options

### Documentation
- Added README.md with architecture diagram
- Added this CHANGELOG.md

## [1.0.0] - 2024-12-16

### Initial Release
- Phase 1: Docling extraction (53,357 emails)
- Phase 2: Basic LLM processing (single machine)
- 31 custom fields extraction
