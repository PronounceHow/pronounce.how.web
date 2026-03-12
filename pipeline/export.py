#!/usr/bin/env python3
"""Export staging DB to JSON files in the data repo.

Output:
  - ~15,990 JSON files in pronounce-how-data/data/words/{letter}/{slug}.json

Usage:
    python -m pipeline.export [--dry-run]
"""

import argparse
import json
import sys
from datetime import date

from tqdm import tqdm

from .config import DATA_WORDS_DIR, EXCLUDED_SLUGS, SCHEMA_PATH
from .db import get_db, slugify


# Region ordering for variants array
REGION_ORDER = {"US": 0, "UK": 1, "CA": 2, "AU": 3}


def build_word_json(conn, word):
    """Build a complete JSON object for a word from staging DB."""
    word_row = conn.execute(
        "SELECT * FROM words WHERE word = ?", (word,)
    ).fetchone()

    if not word_row:
        return None

    slug = word_row["slug"]
    pos = word_row["pos"]
    priority = word_row["priority"] or "medium"
    status = word_row["status"] or "standard"
    frequency_rank = word_row["frequency_rank"]

    # Handle POS as string or array
    if pos:
        try:
            pos_parsed = json.loads(pos)
            if isinstance(pos_parsed, list):
                pos = pos_parsed if len(pos_parsed) > 1 else pos_parsed[0]
            else:
                pos = pos_parsed
        except (json.JSONDecodeError, TypeError):
            pass  # Keep as string
    else:
        pos = "other"

    # Build variants
    variant_rows = conn.execute(
        "SELECT * FROM variants WHERE word = ? ORDER BY region",
        (word,)
    ).fetchall()

    if not variant_rows:
        return None

    variants = []
    for vr in variant_rows:
        ipa = vr["ipa"] or "/TODO/"
        arpabet_json = vr["arpabet"]
        syllables_json = vr["syllables"]

        # Parse ARPAbet
        try:
            phonemes = json.loads(arpabet_json) if arpabet_json else ["TODO"]
        except json.JSONDecodeError:
            phonemes = ["TODO"]

        # Parse syllables
        try:
            syllables = json.loads(syllables_json) if syllables_json else [
                {"text": word, "ipa": ipa.strip("/"), "stress": "primary"}
            ]
        except json.JSONDecodeError:
            syllables = [{"text": word, "ipa": ipa.strip("/"), "stress": "primary"}]

        variant = {
            "region": vr["region"],
            "ipa": ipa,
            "phonemes": phonemes,
            "syllables": syllables,
            "respelling": vr["respelling"] or word.upper(),
            "source_type": vr["source_type"] or "other",
            "source_detail": vr["source_detail"] or "Pipeline-generated",
            "confidence": round(vr["confidence"] or 0.5, 2),
        }

        # Optional fields
        if vr["confidence_reason"]:
            variant["confidence_reason"] = vr["confidence_reason"]
        if vr["derived_from"]:
            variant["derived_from"] = vr["derived_from"]
        if vr["notes"]:
            variant["notes"] = vr["notes"]

        variants.append(variant)

    # Sort variants by region order
    variants.sort(key=lambda v: REGION_ORDER.get(v["region"], 99))

    today = date.today().isoformat()

    entry = {
        "word": word,
        "slug": slug,
        "lang": "en",
        "pos": pos,
        "priority": priority,
        "status": status,
        "variants": variants,
        "updated_at": today,
        "created_at": today,
    }

    # Add cross_validation if available
    cv = {}
    wikt_rows = conn.execute(
        "SELECT region FROM wiktextract_cache WHERE word = ?", (word,)
    ).fetchall()
    if wikt_rows:
        cv["wiktionary_match"] = True

    # Check source types for cross-validation
    source_types = {vr["source_type"] for vr in variant_rows}
    cv["cmu_match"] = "cmu_dict" in source_types
    cv["britfone_match"] = "britfone" in source_types
    cv["espeak_match"] = "espeak" in source_types

    if any(cv.values()):
        entry["cross_validation"] = cv

    return entry


def validate_entry(entry):
    """Basic validation before writing."""
    errors = []

    if not entry.get("slug"):
        errors.append("Missing slug")
    if not entry.get("variants"):
        errors.append("No variants")

    for i, v in enumerate(entry.get("variants", [])):
        if not v.get("ipa", "").startswith("/"):
            errors.append(f"Variant {i}: IPA missing slashes")
        if not v.get("phonemes") or v["phonemes"] == ["TODO"]:
            errors.append(f"Variant {i}: phonemes not set")
        syllables = v.get("syllables", [])
        if not any(s.get("stress") == "primary" for s in syllables):
            errors.append(f"Variant {i}: no primary stress")

    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export staging DB to JSON files.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate but don't write files")
    args = parser.parse_args(argv)

    conn = get_db()

    target_rows = conn.execute(
        "SELECT word FROM target_words WHERE included = 1 ORDER BY word"
    ).fetchall()
    target_words = [row["word"] for row in target_rows]
    print(f"Words to export: {len(target_words)}")

    exported = 0
    skipped = 0
    errors_total = 0
    source_type_counts = {}

    for word in tqdm(target_words, desc="Exporting"):
        slug = slugify(word)

        # Skip hand-crafted samples
        if slug in EXCLUDED_SLUGS:
            skipped += 1
            continue

        entry = build_word_json(conn, word)
        if not entry:
            skipped += 1
            continue

        # Validate
        errors = validate_entry(entry)
        if errors:
            errors_total += len(errors)
            if errors_total <= 20:  # Only show first 20 errors
                print(f"\n  {word}: {'; '.join(errors)}")
            continue

        # Track source types
        for v in entry["variants"]:
            st = v["source_type"]
            source_type_counts[st] = source_type_counts.get(st, 0) + 1

        if args.dry_run:
            exported += 1
            continue

        # Write file
        letter_dir = DATA_WORDS_DIR / slug[0]
        letter_dir.mkdir(parents=True, exist_ok=True)
        filepath = letter_dir / f"{slug}.json"

        json_str = json.dumps(entry, indent=2, ensure_ascii=False) + "\n"
        filepath.write_text(json_str, encoding="utf-8")
        exported += 1

    conn.close()

    # Report
    print(f"\n{'='*60}")
    print(f"Exported: {exported}")
    print(f"Skipped: {skipped}")
    print(f"Validation errors: {errors_total}")
    print(f"\nSource type distribution:")
    for st, count in sorted(source_type_counts.items(), key=lambda x: -x[1]):
        print(f"  {st}: {count}")

    # Average confidence
    if exported > 0:
        print(f"\nTarget directory: {DATA_WORDS_DIR}")

    return 1 if errors_total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
