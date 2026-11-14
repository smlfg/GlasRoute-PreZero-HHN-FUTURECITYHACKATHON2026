# Historical replay and CFO acceptance (2026-11-14)

Verified on hero-ui in an isolated snapshot. No deployment. To repeat with the repository dependencies and Node installed:

1. Rebuild the history and replay as described in docs/KOSTENMODELL.md. Rebuilding the history CSV from raw readings matched the committed table byte for byte.
2. Generate fixtures in the snapshot: `PYTHONPATH=src python3 -m prezero.cli run --date 2026-04-15 --config prezero_config.json`.
3. `PYTHONPATH=src python3 -m pytest -q`: **138 passed**, 5 warnings, 41.57 s. Includes the pre-existing driver GPX and multi-leg Maps regression.
4. `python3 Projek-Management/proof/verify_pitch_numbers.py`: **RESULT: ALL MATCH**. This checks the existing pitch figures. The additional CFO pitch statement is checked separately by tests/test_cfo.py.
5. Local headless Chromium opened the generated UI and clicked Analyse → Kosten & Nutzen. Confirmed visible panel and default headline +169.35 €/day; crew 2 → 3 changed it to +224.50 €/day; then threshold 80 → 90 changed it to +163.24 €/day. These are modeled extra costs.

Local disposable evidence directory: `/private/var/folders/cp/51bmm8v964s4mtd3ydyys65m0000gn/T/glasroute-final.ZHCFongn` (run.log, pytest.log, a3.log, browser.log, browser_check.py and generated UI; temporary, not a release). Benchmarks, walk-forward reference files and price assumptions are inputs, not verified real-world fleet operations.
