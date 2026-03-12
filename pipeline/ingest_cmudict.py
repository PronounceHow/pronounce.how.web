#!/usr/bin/env python3
"""Ingest CMU Pronouncing Dictionary into the staging database.

Input:
  - cmudict.dict (native ARPAbet)
  - cmudict-0.7b-ipa.txt (IPA version)
  - brown-frequency-list-with-ipa.txt (frequency data)

Output:
  - ~134k US variant rows in staging DB

Usage:
    python -m pipeline.ingest_cmudict
"""

import json
import re
import sys

from tqdm import tqdm

from .config import SOURCES_DIR, EXCLUDED_SLUGS
from .db import get_db, upsert_word, upsert_variant, slugify, transaction


def parse_cmudict_dict(filepath):
    """Parse cmudict.dict (ARPAbet format).

    Lines look like:
      SCHEDULE  S K EH1 JH UW0 L
      SCHEDULE(2)  S K EH1 JH AH0 L

    Returns dict: word -> list of ARPAbet token lists (first = primary).
    """
    entries = {}
    with open(filepath, encoding="latin-1") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(";;;"):
                continue

            parts = line.split(None, 1)
            if len(parts) < 2:
                continue

            raw_word = parts[0]
            arpabet_str = parts[1]

            # Handle alternates: WORD(2), WORD(3), etc.
            alt_match = re.match(r"^(.+)\((\d+)\)$", raw_word)
            if alt_match:
                word = alt_match.group(1).lower()
                alt_num = int(alt_match.group(2))
            else:
                word = raw_word.lower()
                alt_num = 1

            tokens = arpabet_str.strip().split()

            if word not in entries:
                entries[word] = []
            # Ensure correct ordering
            while len(entries[word]) < alt_num:
                entries[word].append(None)
            entries[word][alt_num - 1] = tokens

    # Clean up None entries
    for word in entries:
        entries[word] = [t for t in entries[word] if t is not None]

    return entries


def parse_cmudict_ipa(filepath):
    """Parse cmudict-0.7b-ipa.txt (IPA format).

    Lines look like:
      SCHEDULE  ˈskɛdʒul
      SCHEDULE(2)  ˈskɛdʒəl

    Returns dict: word -> list of IPA strings.
    """
    entries = {}
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(";;;"):
                continue

            # Split on tab or multiple spaces
            parts = re.split(r"\t+|\s{2,}", line, maxsplit=1)
            if len(parts) < 2:
                # Try single space split with comma-separated IPA
                parts = line.split(None, 1)
                if len(parts) < 2:
                    continue

            raw_word = parts[0]
            ipa_str = parts[1].strip()

            alt_match = re.match(r"^(.+)\((\d+)\)$", raw_word)
            if alt_match:
                word = alt_match.group(1).lower()
            else:
                word = raw_word.lower()

            if word not in entries:
                entries[word] = []

            # Some entries have comma-separated alternates
            for ipa in ipa_str.split(","):
                ipa = ipa.strip()
                if ipa:
                    entries[word].append(ipa)

    return entries


def parse_brown_frequency(filepath):
    """Parse Brown Corpus frequency list.

    Returns dict: word -> frequency_rank (1-based).
    """
    freq = {}
    rank = 0
    try:
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    try:
                        rank = int(parts[0])
                    except ValueError:
                        continue
                    word = parts[1].lower()
                    if word not in freq:
                        freq[word] = rank
    except FileNotFoundError:
        print("  Warning: Brown frequency list not found, skipping frequency data")
    return freq


def main():
    dict_path = SOURCES_DIR / "cmudict.dict"
    ipa_path = SOURCES_DIR / "cmudict-0.7b-ipa.txt"
    brown_path = SOURCES_DIR / "brown-frequency-list-with-ipa.txt"

    if not dict_path.exists():
        print(f"Error: {dict_path} not found. Run download_sources first.")
        return 1

    print("Parsing cmudict.dict (ARPAbet)...")
    arpa_entries = parse_cmudict_dict(dict_path)
    print(f"  {len(arpa_entries)} words parsed")

    print("Parsing cmudict-0.7b-ipa.txt (IPA)...")
    ipa_entries = {}
    if ipa_path.exists():
        ipa_entries = parse_cmudict_ipa(ipa_path)
        print(f"  {len(ipa_entries)} words parsed")
    else:
        print("  Warning: IPA file not found, will skip IPA data")

    print("Parsing Brown Corpus frequency list...")
    freq_data = parse_brown_frequency(brown_path)
    print(f"  {len(freq_data)} words with frequency data")

    print("\nWriting to staging DB...")
    conn = get_db()
    inserted = 0
    skipped = 0

    with transaction(conn):
        for word, arpa_list in tqdm(arpa_entries.items(), desc="CMU Dict"):
            slug = slugify(word)

            # Skip excluded samples
            if slug in EXCLUDED_SLUGS:
                skipped += 1
                continue

            # Skip words with non-alpha characters (punctuation, numbers)
            if not re.match(r"^[a-z]+(?:-[a-z]+)*$", word):
                continue

            # Take primary pronunciation
            arpabet_tokens = arpa_list[0]
            arpabet_json = json.dumps(arpabet_tokens)

            # Get IPA if available
            ipa_str = None
            if word in ipa_entries and ipa_entries[word]:
                raw_ipa = ipa_entries[word][0]
                ipa_str = f"/{raw_ipa}/" if not raw_ipa.startswith("/") else raw_ipa

            # Frequency rank
            freq_rank = freq_data.get(word)

            # Upsert word
            upsert_word(conn, word, slug=slug, frequency_rank=freq_rank)

            # Upsert US variant
            upsert_variant(
                conn, word, "US",
                ipa=ipa_str,
                arpabet=arpabet_json,
                source_type="cmu_dict",
                source_detail="CMU Pronouncing Dictionary v0.7b",
                confidence=0.90,
                confidence_reason="CMU Dict primary pronunciation",
            )
            inserted += 1

    conn.close()
    print(f"\nInserted: {inserted} US variants")
    print(f"Skipped (excluded samples): {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
