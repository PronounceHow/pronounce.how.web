#!/usr/bin/env python3
"""Generate AU variants and US/UK gap-fill via eSpeak NG.

Uses the phonemizer library for batch efficiency.

Input:
  - Target word list from staging DB
  - eSpeak NG installed on system

Output:
  - AU variant rows in staging DB
  - US/UK gap-fill rows for words missing dictionary sources

Usage:
    python -m pipeline.ingest_espeak [--limit N]
"""

import argparse
import json
import re
import sys

from tqdm import tqdm

from .config import EXCLUDED_SLUGS
from .db import get_db, upsert_variant, transaction, slugify
from .ipa_utils import ipa_to_arpabet


def espeak_ipa(words, voice="en-us", batch_size=500):
    """Get IPA for a list of words using phonemizer/eSpeak.

    Returns dict: word -> ipa_string.
    """
    try:
        from phonemizer import phonemize
        from phonemizer.backend import EspeakBackend
    except ImportError:
        print("  Warning: phonemizer not installed. Using fallback.")
        return _espeak_fallback(words, voice)

    results = {}
    for i in range(0, len(words), batch_size):
        batch = words[i:i+batch_size]
        try:
            ipas = phonemize(
                batch,
                language=voice,
                backend="espeak",
                strip=True,
                preserve_punctuation=False,
                with_stress=True,
            )
            for word, ipa in zip(batch, ipas):
                if ipa and ipa.strip():
                    results[word] = ipa.strip()
        except Exception as e:
            print(f"  Warning: phonemizer batch failed: {e}")
            # Fall back to individual processing
            for word in batch:
                try:
                    ipa_list = phonemize(
                        [word],
                        language=voice,
                        backend="espeak",
                        strip=True,
                        with_stress=True,
                    )
                    if ipa_list and ipa_list[0].strip():
                        results[word] = ipa_list[0].strip()
                except Exception:
                    pass

    return results


def _espeak_fallback(words, voice):
    """Fallback: call espeak-ng directly via subprocess."""
    import subprocess
    results = {}
    for word in words:
        try:
            result = subprocess.run(
                ["espeak-ng", "-v", voice, "-q", "--ipa", word],
                capture_output=True, text=True, timeout=5
            )
            ipa = result.stdout.strip()
            if ipa:
                results[word] = ipa
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate AU + gap-fill via eSpeak.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit to N words (0 = no limit)")
    args = parser.parse_args(argv)

    conn = get_db()

    # Get target words
    query = "SELECT word FROM target_words WHERE included = 1"
    if args.limit > 0:
        query += f" LIMIT {args.limit}"
    target_rows = conn.execute(query).fetchall()
    target_words = [row["word"] for row in target_rows]
    print(f"Target words: {len(target_words)}")

    # Check existing coverage
    existing_au = set()
    existing_us = set()
    existing_uk = set()
    for row in conn.execute("SELECT word, region FROM variants").fetchall():
        if row["region"] == "AU":
            existing_au.add(row["word"])
        elif row["region"] == "US":
            existing_us.add(row["word"])
        elif row["region"] == "UK":
            existing_uk.add(row["word"])

    # Words needing AU variants
    need_au = [w for w in target_words if w not in existing_au]
    # Words needing US gap-fill (in Britfone but not CMU Dict)
    need_us = [w for w in target_words if w not in existing_us]
    # Words needing UK gap-fill
    need_uk = [w for w in target_words if w not in existing_uk]

    print(f"  Need AU: {len(need_au)}")
    print(f"  Need US gap-fill: {len(need_us)}")
    print(f"  Need UK gap-fill: {len(need_uk)}")

    # Check Wiktextract for AU entries first
    wikt_au = {}
    for row in conn.execute(
        "SELECT word, ipa FROM wiktextract_cache WHERE region = 'AU'"
    ).fetchall():
        wikt_au[row["word"]] = row["ipa"]
    print(f"  Wiktextract AU entries available: {len(wikt_au)}")

    # Generate AU via eSpeak
    all_au_words = [w for w in need_au if w not in wikt_au]
    print(f"\nGenerating AU IPA via eSpeak for {len(all_au_words)} words...")
    espeak_au = espeak_ipa(all_au_words, voice="en-au")
    espeak_gb = espeak_ipa(all_au_words, voice="en-gb")

    # Write AU variants
    au_inserted = 0
    with transaction(conn):
        for word in tqdm(need_au, desc="AU variants"):
            slug = slugify(word)
            if slug in EXCLUDED_SLUGS:
                continue

            # Prefer Wiktextract
            if word in wikt_au:
                ipa = wikt_au[word]
                ipa_with_slashes = f"/{ipa}/"
                arpabet = json.dumps(ipa_to_arpabet(ipa_with_slashes))
                upsert_variant(
                    conn, word, "AU",
                    ipa=ipa_with_slashes, arpabet=arpabet,
                    source_type="wiktionary",
                    source_detail="Wiktionary (Wiktextract)",
                    confidence=0.75,
                    confidence_reason="Wiktionary AU-tagged pronunciation",
                )
            elif word in espeak_au:
                au_ipa = espeak_au[word]
                gb_ipa = espeak_gb.get(word, "")

                ipa_with_slashes = f"/{au_ipa}/"
                arpabet = json.dumps(ipa_to_arpabet(ipa_with_slashes))

                if au_ipa != gb_ipa:
                    upsert_variant(
                        conn, word, "AU",
                        ipa=ipa_with_slashes, arpabet=arpabet,
                        source_type="espeak",
                        source_detail="eSpeak NG en-au",
                        confidence=0.50,
                        confidence_reason="eSpeak AU differs from UK",
                    )
                else:
                    upsert_variant(
                        conn, word, "AU",
                        ipa=ipa_with_slashes, arpabet=arpabet,
                        source_type="espeak",
                        source_detail="eSpeak NG en-au",
                        confidence=0.55,
                        confidence_reason="eSpeak AU matches UK",
                        derived_from="UK",
                    )
            au_inserted += 1

    # US gap-fill
    us_inserted = 0
    if need_us:
        print(f"\nGenerating US gap-fill via eSpeak for {len(need_us)} words...")
        espeak_us = espeak_ipa(need_us, voice="en-us")

        with transaction(conn):
            for word in tqdm(need_us, desc="US gap-fill"):
                slug = slugify(word)
                if slug in EXCLUDED_SLUGS:
                    continue
                if word in espeak_us:
                    ipa = espeak_us[word]
                    ipa_with_slashes = f"/{ipa}/"
                    arpabet = json.dumps(ipa_to_arpabet(ipa_with_slashes))
                    upsert_variant(
                        conn, word, "US",
                        ipa=ipa_with_slashes, arpabet=arpabet,
                        source_type="espeak",
                        source_detail="eSpeak NG en-us",
                        confidence=0.60,
                        confidence_reason="eSpeak gap-fill (no CMU Dict entry)",
                    )
                    us_inserted += 1

    # UK gap-fill
    uk_inserted = 0
    if need_uk:
        print(f"\nGenerating UK gap-fill via eSpeak for {len(need_uk)} words...")
        espeak_uk = espeak_ipa(need_uk, voice="en-gb")

        with transaction(conn):
            for word in tqdm(need_uk, desc="UK gap-fill"):
                slug = slugify(word)
                if slug in EXCLUDED_SLUGS:
                    continue
                if word in espeak_uk:
                    ipa = espeak_uk[word]
                    ipa_with_slashes = f"/{ipa}/"
                    arpabet = json.dumps(ipa_to_arpabet(ipa_with_slashes))
                    upsert_variant(
                        conn, word, "UK",
                        ipa=ipa_with_slashes, arpabet=arpabet,
                        source_type="espeak",
                        source_detail="eSpeak NG en-gb",
                        confidence=0.60,
                        confidence_reason="eSpeak gap-fill (no Britfone entry)",
                    )
                    uk_inserted += 1

    conn.close()
    print(f"\nAU inserted: {au_inserted}")
    print(f"US gap-fill: {us_inserted}")
    print(f"UK gap-fill: {uk_inserted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
