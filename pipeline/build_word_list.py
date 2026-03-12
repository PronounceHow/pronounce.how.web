#!/usr/bin/env python3
"""Build the target word list for the pipeline.

Sources (in priority order):
  1. Britfone baseline (~16k words with UK pronunciation)
  2. Brown Corpus frequency words that exist in CMU Dict (~20k additional)

Usage:
    python -m pipeline.build_word_list [--limit N]
"""

import argparse
import re
import sys

from .config import EXCLUDED_SLUGS
from .db import get_db, slugify, transaction


def _is_valid_word(word):
    """Filter out function words, abbreviations, and non-alpha entries."""
    if len(word) <= 1 and word not in ("a", "i"):
        return False
    if not re.match(r'^[a-zA-Z]+$', word):
        return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build target word list.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit to N words (0 = no limit)")
    args = parser.parse_args(argv)

    conn = get_db()

    # ── Source 1: Britfone baseline (UK pronunciations) ──────────────────
    print("Building target word list...")
    print("\n  Source 1: Britfone baseline")

    britfone_words = conn.execute("""
        SELECT DISTINCT word FROM variants
        WHERE region = 'UK' AND source_type = 'britfone'
    """).fetchall()
    britfone_set = {row["word"] for row in britfone_words}
    print(f"    Britfone words: {len(britfone_set)}")

    # ── Source 2: CMU Dict words from Brown frequency list ───────────────
    print("\n  Source 2: Brown frequency list (CMU Dict)")

    cmu_words = conn.execute("""
        SELECT DISTINCT word FROM variants
        WHERE region = 'US' AND source_type = 'cmu_dict'
    """).fetchall()
    cmu_set = {row["word"] for row in cmu_words}
    print(f"    CMU Dict words: {len(cmu_set)}")

    # Get frequency data for priority assignment
    freq_data = {}
    rows = conn.execute(
        "SELECT word, frequency_rank FROM words WHERE frequency_rank IS NOT NULL"
    ).fetchall()
    for row in rows:
        freq_data[row["word"]] = row["frequency_rank"]
    print(f"    Words with frequency data: {len(freq_data)}")

    # Brown frequency words in CMU Dict but not in Britfone
    brown_words = {w for w in cmu_set if w in freq_data}
    brown_additions = brown_words - britfone_set
    # Filter to valid words only
    brown_additions = {w for w in brown_additions if _is_valid_word(w)}
    print(f"    Brown words in CMU (not in Britfone): {len(brown_additions)}")

    # ── Merge and assign priorities ──────────────────────────────────────
    print("\n  Merging sources...")

    combined = britfone_set | brown_additions
    overlap = britfone_set & cmu_set
    print(f"    Britfone ∩ CMU (both sources): {len(overlap)}")
    print(f"    Britfone-only (need eSpeak US): {len(britfone_set - cmu_set)}")
    print(f"    CMU-only additions: {len(brown_additions)}")

    target_words = []
    for word in combined:
        slug = slugify(word)

        # Exclude hand-crafted samples
        if slug in EXCLUDED_SLUGS:
            continue

        # Assign priority based on Brown frequency
        rank = freq_data.get(word)
        if rank and rank <= 5000:
            priority = "high"
        elif rank and rank <= 12000:
            priority = "medium"
        else:
            priority = "low"

        target_words.append((word, priority))

    # Sort by priority then alphabetically
    priority_order = {"high": 0, "medium": 1, "low": 2}
    target_words.sort(key=lambda x: (priority_order[x[1]], x[0]))

    if args.limit > 0:
        target_words = target_words[:args.limit]

    # ── Write to DB ──────────────────────────────────────────────────────
    print(f"\n  Writing {len(target_words)} target words to DB...")
    with transaction(conn):
        conn.execute("DELETE FROM target_words")
        for word, priority in target_words:
            conn.execute("""
                INSERT INTO target_words (word, included, priority)
                VALUES (?, 1, ?)
            """, (word, priority))

    # Stats
    high = sum(1 for _, p in target_words if p == "high")
    medium = sum(1 for _, p in target_words if p == "medium")
    low = sum(1 for _, p in target_words if p == "low")
    print(f"\n  High priority: {high}")
    print(f"  Medium priority: {medium}")
    print(f"  Low priority: {low}")
    print(f"  Total: {len(target_words)}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
