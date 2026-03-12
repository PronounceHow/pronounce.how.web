#!/usr/bin/env python3
"""Ingest Britfone UK pronunciation data into the staging database.

Input:
  - britfone.main.3.0.1.csv (CSV: WORD, space-separated IPA phonemes)

Output:
  - ~16k UK variant rows in staging DB

Usage:
    python -m pipeline.ingest_britfone
"""

import csv
import json
import re
import sys

from tqdm import tqdm

from .config import SOURCES_DIR, EXCLUDED_SLUGS
from .db import get_db, upsert_word, upsert_variant, slugify, transaction
from .ipa_utils import ipa_to_arpabet


def parse_britfone(filepath):
    """Parse Britfone CSV file.

    Format: WORD, space-separated IPA phonemes
    e.g.:  SCHEDULE, ˈʃ ɛ d j uː l

    Returns list of (word, ipa_string, phoneme_list) tuples.
    """
    entries = []

    with open(filepath, encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue

            word = row[0].strip().lower()
            phonemes_str = row[1].strip()

            if not word or not phonemes_str:
                continue

            # Skip header row if present
            if word == "word":
                continue

            # Phonemes are space-separated IPA symbols
            phonemes = phonemes_str.split()

            # Reassemble into IPA string
            ipa_string = "".join(phonemes)

            entries.append((word, ipa_string, phonemes))

    return entries


def main():
    bf_path = SOURCES_DIR / "britfone.main.3.0.1.csv"

    if not bf_path.exists():
        print(f"Error: {bf_path} not found. Run download_sources first.")
        return 1

    print("Parsing Britfone CSV...")
    entries = parse_britfone(bf_path)
    print(f"  {len(entries)} entries parsed")

    print("\nWriting to staging DB...")
    conn = get_db()
    inserted = 0
    skipped = 0

    with transaction(conn):
        for word, ipa_string, phoneme_list in tqdm(entries, desc="Britfone"):
            slug = slugify(word)

            # Skip excluded samples
            if slug in EXCLUDED_SLUGS:
                skipped += 1
                continue

            # Skip words with non-alpha characters
            if not re.match(r"^[a-z]+(?:-[a-z]+)*$", word):
                continue

            # Wrap IPA in slashes
            ipa_with_slashes = f"/{ipa_string}/"

            # Convert to ARPAbet
            arpabet_tokens = ipa_to_arpabet(ipa_with_slashes)
            arpabet_json = json.dumps(arpabet_tokens)

            # Upsert word
            upsert_word(conn, word, slug=slug)

            # Upsert UK variant
            upsert_variant(
                conn, word, "UK",
                ipa=ipa_with_slashes,
                arpabet=arpabet_json,
                source_type="britfone",
                source_detail="Britfone v3.0.1",
                confidence=0.90,
                confidence_reason="Britfone primary pronunciation",
            )
            inserted += 1

    conn.close()
    print(f"\nInserted: {inserted} UK variants")
    print(f"Skipped (excluded samples): {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
