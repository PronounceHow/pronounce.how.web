#!/usr/bin/env python3
"""Ingest Wiktextract pronunciation data into the staging database.

Input:
  - kaikki.org-dictionary-English.jsonl (2.7GB JSONL, stream-parsed)

Output:
  - Rows in wiktextract_cache table
  - POS data updated in words table

Usage:
    python -m pipeline.ingest_wiktextract
"""

import json
import re
import sys

from tqdm import tqdm

from .config import SOURCES_DIR, WIKT_POS_MAP, EXCLUDED_SLUGS
from .db import get_db, upsert_word, slugify, transaction


# Region tag normalization
REGION_TAG_MAP = {
    "US": "US",
    "General-American": "US",
    "GenAm": "US",
    "US-American": "US",
    "American": "US",
    "UK": "UK",
    "Received-Pronunciation": "UK",
    "RP": "UK",
    "British": "UK",
    "Australia": "AU",
    "Australian": "AU",
    "AU": "AU",
    "Canada": "CA",
    "Canadian": "CA",
    "CA": "CA",
}


def normalize_region(tags):
    """Map Wiktextract tags to our region codes."""
    if not tags:
        return None
    for tag in tags:
        region = REGION_TAG_MAP.get(tag)
        if region:
            return region
    return None


def extract_ipa_from_sounds(sounds):
    """Extract (region, ipa) pairs from a Wiktextract sounds array."""
    results = []
    if not sounds:
        return results

    for sound in sounds:
        ipa = sound.get("ipa")
        if not ipa:
            continue

        # Clean IPA string
        ipa = ipa.strip()
        if not ipa:
            continue

        tags = sound.get("tags", [])
        region = normalize_region(tags)

        # If no region tag, check for common patterns
        if region is None:
            # Check for explicit region in other fields
            note = sound.get("note", "")
            if "US" in note or "American" in note:
                region = "US"
            elif "UK" in note or "British" in note or "RP" in note:
                region = "UK"
            elif "Austral" in note:
                region = "AU"
            elif "Canad" in note:
                region = "CA"

        if region:
            results.append((region, ipa))

    return results


def map_pos(wikt_pos):
    """Map Wiktextract POS to our schema enum."""
    if not wikt_pos:
        return None
    return WIKT_POS_MAP.get(wikt_pos.lower(), "other")


def main():
    jsonl_path = SOURCES_DIR / "kaikki.org-dictionary-English.jsonl"
    extracted_path = SOURCES_DIR / "kaikki-en-extracted.jsonl"

    if not jsonl_path.exists():
        print(f"Warning: {jsonl_path} not found. Skipping Wiktextract ingestion.")
        print("  Run download_sources without --skip-kaikki to get this file.")
        return 0

    print(f"Streaming Wiktextract JSONL: {jsonl_path}")
    print(f"  Extracted cache: {extracted_path}")

    conn = get_db()

    total_lines = 0
    ipa_found = 0
    pos_found = 0

    extracted_f = open(extracted_path, "w", encoding="utf-8")

    try:
        with open(jsonl_path, encoding="utf-8") as f:
            for line in tqdm(f, desc="Wiktextract", unit=" entries"):
                total_lines += 1
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                word = entry.get("word", "").lower().strip()
                if not word:
                    continue

                # Filter: only simple English words
                lang = entry.get("lang", "")
                if lang and lang != "English":
                    continue

                if not re.match(r"^[a-z]+(?:-[a-z]+)*$", word):
                    continue

                slug = slugify(word)
                if slug in EXCLUDED_SLUGS:
                    continue

                # Extract POS
                wikt_pos = entry.get("pos", "")
                our_pos = map_pos(wikt_pos)

                if our_pos:
                    upsert_word(conn, word, slug=slug, pos=our_pos)
                    pos_found += 1

                # Extract IPA from sounds
                sounds = entry.get("sounds", [])
                ipa_pairs = extract_ipa_from_sounds(sounds)

                for region, ipa in ipa_pairs:
                    # Normalize IPA: ensure slashes
                    ipa_clean = ipa.strip("/").strip("[").strip("]")

                    conn.execute("""
                        INSERT INTO wiktextract_cache (word, region, ipa, pos)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(word, region) DO UPDATE SET
                            ipa = excluded.ipa,
                            pos = COALESCE(excluded.pos, wiktextract_cache.pos)
                    """, (word, region, ipa_clean, our_pos))
                    ipa_found += 1

                    # Write to extracted file
                    extracted_f.write(json.dumps({
                        "word": word, "region": region,
                        "ipa": ipa_clean, "pos": our_pos
                    }) + "\n")

                # Commit every 10k lines to avoid huge transactions
                if total_lines % 10000 == 0:
                    conn.commit()

        conn.commit()

    finally:
        extracted_f.close()
        conn.close()

    print(f"\nProcessed: {total_lines} entries")
    print(f"IPA entries extracted: {ipa_found}")
    print(f"POS entries found: {pos_found}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
