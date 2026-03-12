#!/usr/bin/env python3
"""Pipeline orchestrator.

Usage:
    python -m pipeline.run_pipeline [--step N] [--from-step N] [--skip-kaikki]
"""

import argparse
import sys
import time


STEPS = {
    0: ("download_sources", "Download raw data files"),
    1: ("ingest_cmudict", "Ingest CMU Pronouncing Dictionary"),
    2: ("ingest_britfone", "Ingest Britfone UK data"),
    3: ("ingest_wiktextract", "Ingest Wiktextract data"),
    4: ("build_word_list", "Build target word list"),
    5: ("ingest_espeak", "Generate AU + gap-fill via eSpeak"),
    6: ("apply_ca_rules", "Generate CA variants from US"),
    7: ("syllabify", "Syllable boundaries and stress"),
    8: ("generate_respelling", "Generate respellings"),
    9: ("merge_sources", "Cross-validate and merge"),
    10: ("export", "Export to JSON files"),
}


def run_step(step_num, skip_kaikki=False):
    """Run a single pipeline step by number."""
    if step_num not in STEPS:
        print(f"Unknown step: {step_num}")
        return False

    module_name, description = STEPS[step_num]
    print(f"\n{'='*60}")
    print(f"Step {step_num}: {description}")
    print(f"{'='*60}\n")

    start = time.time()

    try:
        if module_name == "download_sources":
            from . import download_sources
            step_args = ["--skip-kaikki"] if skip_kaikki else []
            download_sources.main(step_args)
        elif module_name == "ingest_cmudict":
            from . import ingest_cmudict
            ingest_cmudict.main([])
        elif module_name == "ingest_britfone":
            from . import ingest_britfone
            ingest_britfone.main([])
        elif module_name == "ingest_wiktextract":
            from . import ingest_wiktextract
            ingest_wiktextract.main([])
        elif module_name == "build_word_list":
            from . import build_word_list
            build_word_list.main([])
        elif module_name == "ingest_espeak":
            from . import ingest_espeak
            ingest_espeak.main([])
        elif module_name == "apply_ca_rules":
            from . import apply_ca_rules
            apply_ca_rules.main([])
        elif module_name == "syllabify":
            from . import syllabify
            syllabify.main([])
        elif module_name == "generate_respelling":
            from . import generate_respelling
            generate_respelling.main([])
        elif module_name == "merge_sources":
            from . import merge_sources
            merge_sources.main([])
        elif module_name == "export":
            from . import export
            export.main([])
    except Exception as e:
        print(f"\nStep {step_num} FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    elapsed = time.time() - start
    print(f"\nStep {step_num} completed in {elapsed:.1f}s")
    return True


def main():
    parser = argparse.ArgumentParser(description="Run the pronounceHow data pipeline.")
    parser.add_argument("--step", type=int, help="Run only this step number")
    parser.add_argument("--from-step", type=int, default=0,
                        help="Start from this step number (default: 0)")
    parser.add_argument("--skip-kaikki", action="store_true",
                        help="Skip downloading the 2.7GB Wiktextract file")
    args = parser.parse_args()

    total_start = time.time()

    if args.step is not None:
        success = run_step(args.step, skip_kaikki=args.skip_kaikki)
        return 0 if success else 1

    for step_num in sorted(STEPS.keys()):
        if step_num < args.from_step:
            continue
        if step_num == 3 and args.skip_kaikki:
            print(f"\nSkipping step 3 (Wiktextract) — --skip-kaikki")
            continue
        success = run_step(step_num, skip_kaikki=args.skip_kaikki)
        if not success:
            print(f"\nPipeline aborted at step {step_num}.")
            return 1

    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"Pipeline completed in {total_elapsed:.1f}s")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
