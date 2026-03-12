#!/usr/bin/env python3
"""Generate human-readable respellings from IPA and syllable data.

Convention: primary-stressed syllables UPPERCASE, others lowercase,
hyphens between syllables.

Input:
  - Variant rows with IPA and syllable data

Output:
  - respelling column populated

Usage:
    python -m pipeline.generate_respelling
"""

import json
import sys

from tqdm import tqdm

from .db import get_db, transaction
from .ipa_utils import ipa_to_respelling


def respelling_from_syllables(syllables):
    """Generate respelling from syllable data.

    Each syllable has ipa and stress. Primary-stressed → UPPERCASE.
    """
    if not syllables:
        return ""

    parts = []
    for syl in syllables:
        syl_ipa = syl.get("ipa", "")
        stress = syl.get("stress", "unstressed")

        # Convert syllable IPA to respelling
        text = ipa_to_respelling(syl_ipa)

        if stress == "primary":
            text = text.upper()

        parts.append(text)

    return "-".join(parts)


def main(argv=None):
    conn = get_db()

    rows = conn.execute("""
        SELECT v.word, v.region, v.ipa, v.syllables
        FROM variants v
        JOIN target_words tw ON v.word = tw.word
        WHERE tw.included = 1
    """).fetchall()

    print(f"Variants to generate respellings for: {len(rows)}")

    updated = 0
    with transaction(conn):
        for row in tqdm(rows, desc="Respelling"):
            word = row["word"]
            region = row["region"]
            ipa = row["ipa"]
            syllables_json = row["syllables"]

            respelling = ""

            # Try syllable-based respelling first
            if syllables_json:
                try:
                    syllables = json.loads(syllables_json)
                    respelling = respelling_from_syllables(syllables)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Fallback to IPA-based respelling
            if not respelling and ipa:
                respelling = ipa_to_respelling(ipa)

            if not respelling:
                respelling = word.upper()

            conn.execute("""
                UPDATE variants SET respelling = ?
                WHERE word = ? AND region = ?
            """, (respelling, word, region))
            updated += 1

    conn.close()
    print(f"\nRespellings generated: {updated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
