#!/usr/bin/env python3
"""Generate Canadian English variants from US base.

Applies Canadian raising rules and lexical overrides.

Input:
  - US variant rows from staging DB
  - Wiktextract CA entries (if available)

Output:
  - CA variant rows in staging DB

Usage:
    python -m pipeline.apply_ca_rules
"""

import json
import sys

from tqdm import tqdm

from .config import (
    EXCLUDED_SLUGS, CA_VOICELESS, CA_LEXICAL_OVERRIDES,
)
from .db import get_db, upsert_variant, transaction, slugify
from .ipa_utils import segment_ipa, ipa_to_arpabet, normalize_ipa


def apply_canadian_raising(ipa_string):
    """Apply Canadian raising rules to an IPA string.

    Canadian Raising:
      /aʊ/ → /ʌʊ/ before voiceless consonants
      /aɪ/ → /ʌɪ/ before voiceless consonants

    Returns (modified_ipa, changed: bool).
    """
    segments = segment_ipa(ipa_string)
    changed = False
    new_segments = []

    i = 0
    while i < len(segments):
        seg = segments[i]

        # Check for diphthongs before voiceless consonants
        if seg in ("aʊ", "aɪ"):
            # Look ahead for voiceless consonant
            next_seg = None
            j = i + 1
            while j < len(segments):
                if segments[j] in ("ˈ", "ˌ"):
                    j += 1
                    continue
                next_seg = segments[j]
                break

            if next_seg and next_seg in CA_VOICELESS:
                # Apply raising: a → ʌ
                raised = seg.replace("a", "ʌ")
                new_segments.append(raised)
                changed = True
            else:
                new_segments.append(seg)
        else:
            new_segments.append(seg)

        i += 1

    # Reconstruct IPA string
    result = "".join(new_segments)
    return result, changed


def apply_lexical_override(word, us_ipa):
    """Check if word has a known CA lexical override.

    Returns (ca_ipa, True) if override found, (us_ipa, False) otherwise.
    """
    override = CA_LEXICAL_OVERRIDES.get(word)
    if not override:
        return us_ipa, False

    # Check if the US IPA roughly matches expected
    us_norm = normalize_ipa(us_ipa)
    expected_norm = normalize_ipa(override["us_ipa"])

    # Use the CA override IPA
    return override["ca_ipa"], True


def main(argv=None):
    conn = get_db()

    # Get target words
    target_rows = conn.execute(
        "SELECT word FROM target_words WHERE included = 1"
    ).fetchall()
    target_words = [row["word"] for row in target_rows]
    print(f"Target words: {len(target_words)}")

    # Check Wiktextract for CA entries
    wikt_ca = {}
    for row in conn.execute(
        "SELECT word, ipa FROM wiktextract_cache WHERE region = 'CA'"
    ).fetchall():
        wikt_ca[row["word"]] = row["ipa"]
    print(f"Wiktextract CA entries: {len(wikt_ca)}")

    # Get existing US variants
    us_variants = {}
    for row in conn.execute(
        "SELECT word, ipa, arpabet FROM variants WHERE region = 'US'"
    ).fetchall():
        us_variants[row["word"]] = {
            "ipa": row["ipa"],
            "arpabet": row["arpabet"],
        }
    print(f"US variants available: {len(us_variants)}")

    ca_inserted = 0
    ca_from_wikt = 0
    ca_raised = 0
    ca_lexical = 0
    ca_derived = 0

    with transaction(conn):
        for word in tqdm(target_words, desc="CA variants"):
            slug = slugify(word)
            if slug in EXCLUDED_SLUGS:
                continue

            # Prefer Wiktextract CA entry
            if word in wikt_ca:
                ca_ipa = wikt_ca[word]
                ipa_with_slashes = f"/{ca_ipa}/"
                arpabet = json.dumps(ipa_to_arpabet(ipa_with_slashes))
                upsert_variant(
                    conn, word, "CA",
                    ipa=ipa_with_slashes, arpabet=arpabet,
                    source_type="wiktionary",
                    source_detail="Wiktionary (Wiktextract)",
                    confidence=0.75,
                    confidence_reason="Wiktionary CA-tagged pronunciation",
                )
                ca_from_wikt += 1
                ca_inserted += 1
                continue

            # Need US base to derive CA
            if word not in us_variants:
                continue

            us_ipa = us_variants[word]["ipa"]
            if not us_ipa:
                continue

            us_ipa_clean = us_ipa.strip("/")

            # Check lexical overrides first
            ca_ipa, is_override = apply_lexical_override(word, us_ipa_clean)
            if is_override:
                ipa_with_slashes = f"/{ca_ipa}/"
                arpabet = json.dumps(ipa_to_arpabet(ipa_with_slashes))
                upsert_variant(
                    conn, word, "CA",
                    ipa=ipa_with_slashes, arpabet=arpabet,
                    source_type="manual",
                    source_detail="Canadian lexical override",
                    confidence=0.55,
                    confidence_reason="Known CA-specific pronunciation",
                )
                ca_lexical += 1
                ca_inserted += 1
                continue

            # Apply Canadian raising
            ca_ipa, raised = apply_canadian_raising(us_ipa_clean)

            if raised:
                ipa_with_slashes = f"/{ca_ipa}/"
                arpabet = json.dumps(ipa_to_arpabet(ipa_with_slashes))
                upsert_variant(
                    conn, word, "CA",
                    ipa=ipa_with_slashes, arpabet=arpabet,
                    source_type="manual",
                    source_detail="Canadian raising applied to US",
                    confidence=0.55,
                    confidence_reason="Canadian raising rule applied",
                )
                ca_raised += 1
            else:
                # No changes — derive directly from US
                ipa_with_slashes = us_ipa
                arpabet = us_variants[word]["arpabet"]
                upsert_variant(
                    conn, word, "CA",
                    ipa=ipa_with_slashes, arpabet=arpabet,
                    source_type="manual",
                    source_detail="Derived from US (no CA-specific differences)",
                    confidence=0.60,
                    confidence_reason="Same as US; no known CA difference",
                    derived_from="US",
                )
                ca_derived += 1

            ca_inserted += 1

    conn.close()
    print(f"\nCA variants inserted: {ca_inserted}")
    print(f"  From Wiktextract: {ca_from_wikt}")
    print(f"  Lexical overrides: {ca_lexical}")
    print(f"  Canadian raising: {ca_raised}")
    print(f"  Derived from US: {ca_derived}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
