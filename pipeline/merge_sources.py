#!/usr/bin/env python3
"""Cross-validate and merge pronunciation data from all sources.

Per (word, region):
1. Source priority: cmu_dict/britfone > wiktionary > espeak > manual
2. Cross-validation: compare sources, adjust confidence
3. Set word-level status: standard, regional, disputed, rare

Input:
  - All data in staging DB

Output:
  - Finalized rows with adjusted confidence and cross-validation

Usage:
    python -m pipeline.merge_sources
"""

import json
import sys

from tqdm import tqdm

from .db import get_db, transaction
from .ipa_utils import normalize_ipa


SOURCE_PRIORITY = {
    "cmu_dict": 1,
    "britfone": 1,
    "wiktionary": 2,
    "espeak": 3,
    "manual": 4,
    "g2p_model": 5,
    "other": 6,
}


def cross_validate_word(conn, word):
    """Cross-validate all sources for a word. Returns cross_validation dict."""
    variants = conn.execute(
        "SELECT region, ipa, source_type FROM variants WHERE word = ?",
        (word,)
    ).fetchall()

    if not variants:
        return {}

    # Get normalized IPAs per region
    region_ipas = {}
    region_sources = {}
    for v in variants:
        region = v["region"]
        ipa = v["ipa"] or ""
        region_ipas[region] = normalize_ipa(ipa)
        region_sources[region] = v["source_type"]

    # Check Wiktextract data
    wikt_rows = conn.execute(
        "SELECT region, ipa FROM wiktextract_cache WHERE word = ?",
        (word,)
    ).fetchall()
    wikt_ipas = {r["region"]: normalize_ipa(r["ipa"] or "") for r in wikt_rows}

    # Cross-validation
    cv = {}

    # CMU match (US)
    us_ipa = region_ipas.get("US", "")
    if us_ipa and region_sources.get("US") == "cmu_dict":
        cv["cmu_match"] = True
    elif us_ipa:
        cv["cmu_match"] = False

    # Britfone match (UK)
    uk_ipa = region_ipas.get("UK", "")
    if uk_ipa and region_sources.get("UK") == "britfone":
        cv["britfone_match"] = True
    elif uk_ipa:
        cv["britfone_match"] = False

    # Wiktionary match
    wikt_match = False
    for region, w_ipa in wikt_ipas.items():
        if region in region_ipas and w_ipa == region_ipas[region]:
            wikt_match = True
            break
    cv["wiktionary_match"] = wikt_match

    return cv


def determine_status(conn, word):
    """Determine word-level status based on variant data."""
    variants = conn.execute(
        "SELECT region, ipa, confidence FROM variants WHERE word = ?",
        (word,)
    ).fetchall()

    if not variants:
        return "standard"

    # Get word frequency
    word_row = conn.execute(
        "SELECT frequency_rank FROM words WHERE word = ?", (word,)
    ).fetchone()
    freq_rank = word_row["frequency_rank"] if word_row else None

    # Check if US and UK differ
    us_ipa = None
    uk_ipa = None
    for v in variants:
        if v["region"] == "US":
            us_ipa = normalize_ipa(v["ipa"] or "")
        elif v["region"] == "UK":
            uk_ipa = normalize_ipa(v["ipa"] or "")

    if us_ipa and uk_ipa and us_ipa != uk_ipa:
        return "regional"

    # Check confidence — low confidence suggests disputed
    avg_confidence = sum(v["confidence"] or 0.5 for v in variants) / len(variants)
    if avg_confidence < 0.65:
        return "disputed"

    # Check frequency — rare words
    if freq_rank and freq_rank > 15000:
        return "rare"

    return "standard"


def adjust_confidence(conn, word, region, cross_validation):
    """Adjust confidence based on cross-validation results."""
    variant = conn.execute(
        "SELECT confidence, source_type FROM variants WHERE word = ? AND region = ?",
        (word, region)
    ).fetchone()

    if not variant:
        return

    current = variant["confidence"] or 0.5

    # Boost if multiple sources agree
    matches = sum(1 for v in cross_validation.values() if v is True)
    total = sum(1 for v in cross_validation.values() if isinstance(v, bool))

    if total > 0:
        agreement_ratio = matches / total
        if agreement_ratio >= 0.75:
            new_confidence = min(0.95, current + 0.05)
        elif agreement_ratio >= 0.5:
            new_confidence = current  # No change
        else:
            new_confidence = max(0.40, current - 0.10)
    else:
        new_confidence = current

    if new_confidence != current:
        conn.execute("""
            UPDATE variants SET confidence = ?
            WHERE word = ? AND region = ?
        """, (round(new_confidence, 2), word, region))


def main(argv=None):
    conn = get_db()

    target_rows = conn.execute(
        "SELECT word FROM target_words WHERE included = 1"
    ).fetchall()
    target_words = [row["word"] for row in target_rows]
    print(f"Words to merge: {len(target_words)}")

    updated = 0
    with transaction(conn):
        for word in tqdm(target_words, desc="Merging"):
            # Cross-validate
            cv = cross_validate_word(conn, word)

            # Adjust confidence for each variant
            variants = conn.execute(
                "SELECT region FROM variants WHERE word = ?", (word,)
            ).fetchall()
            for v in variants:
                adjust_confidence(conn, word, v["region"], cv)

            # Determine status
            status = determine_status(conn, word)
            conn.execute(
                "UPDATE words SET status = ? WHERE word = ?",
                (status, word)
            )

            updated += 1

    # Stats
    status_counts = {}
    for row in conn.execute(
        "SELECT status, COUNT(*) as cnt FROM words w "
        "JOIN target_words tw ON w.word = tw.word "
        "WHERE tw.included = 1 GROUP BY status"
    ).fetchall():
        status_counts[row["status"]] = row["cnt"]

    conn.close()
    print(f"\nMerged: {updated} words")
    print("Status distribution:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
