#!/usr/bin/env python3
"""Syllable boundary detection and stress assignment.

Uses pysle (ISLEdict) for IPA syllable boundaries + pyphen for orthographic splits.

Input:
  - All variant rows in staging DB

Output:
  - syllables JSON column populated for every variant

Usage:
    python -m pipeline.syllabify
"""

import json
import re
import sys

from tqdm import tqdm

from .db import get_db, transaction
from .ipa_utils import is_vowel_token, segment_ipa


def get_pyphen_splitter():
    """Get a pyphen hyphenation dictionary."""
    try:
        import pyphen
        return pyphen.Pyphen(lang="en_US")
    except ImportError:
        print("  Warning: pyphen not installed. Using fallback syllable split.")
        return None


def get_pysle_lookup():
    """Get pysle ISLEdict lookup function."""
    try:
        from pysle import isletool
        isle = isletool.Isle()

        def lookup(word):
            try:
                entries = isle.lookup(word)
                if entries:
                    return entries[0]
            except Exception:
                pass
            return None

        return lookup
    except (ImportError, Exception):
        print("  Warning: pysle not available. Using heuristic syllabification.")
        return None


def split_text_into_syllables(word, n_syllables, pyphen_dict=None):
    """Split a word's orthographic form into n syllables.

    Uses pyphen for hyphenation, then adjusts count to match IPA syllables.
    """
    if n_syllables <= 1:
        return [word]

    if pyphen_dict:
        hyphenated = pyphen_dict.inserted(word)
        parts = hyphenated.split("-")
    else:
        # Fallback: simple vowel-based split
        parts = _heuristic_text_split(word)

    # Adjust to match target count
    while len(parts) > n_syllables and len(parts) > 1:
        # Merge shortest adjacent pair
        min_idx = 0
        min_len = len(parts[0]) + len(parts[1])
        for i in range(len(parts) - 1):
            combined = len(parts[i]) + len(parts[i+1])
            if combined < min_len:
                min_len = combined
                min_idx = i
        parts[min_idx] = parts[min_idx] + parts[min_idx + 1]
        del parts[min_idx + 1]

    while len(parts) < n_syllables:
        # Split longest part
        max_idx = max(range(len(parts)), key=lambda i: len(parts[i]))
        p = parts[max_idx]
        mid = len(p) // 2
        parts[max_idx] = p[:mid]
        parts.insert(max_idx + 1, p[mid:])

    return parts


def _heuristic_text_split(word):
    """Simple heuristic: split before consonant clusters preceding vowels."""
    vowels = set("aeiouy")
    parts = []
    current = ""

    for i, ch in enumerate(word):
        current += ch
        if (ch.lower() in vowels and i < len(word) - 1
                and word[i+1].lower() not in vowels
                and len(current) > 1):
            # Check if next char starts a new syllable
            if i + 2 < len(word) and word[i+2].lower() in vowels:
                parts.append(current)
                current = ""

    if current:
        parts.append(current)

    return parts if parts else [word]


def syllabify_from_arpabet(arpabet_tokens):
    """Split ARPAbet tokens into syllable groups based on vowel nuclei.

    Returns list of (tokens, stress) tuples.
    """
    if not arpabet_tokens:
        return []

    syllables = []
    current = []
    current_stress = "unstressed"

    for token in arpabet_tokens:
        if is_vowel_token(token):
            # If we already have a vowel in current, start new syllable
            has_vowel = any(is_vowel_token(t) for t in current)
            if has_vowel:
                syllables.append((current, current_stress))
                current = []
                current_stress = "unstressed"

            current.append(token)

            # Determine stress from digit
            digit = token[-1] if token[-1] in "012" else "0"
            if digit == "1":
                current_stress = "primary"
            elif digit == "2":
                current_stress = "secondary"
        else:
            current.append(token)

    if current:
        syllables.append((current, current_stress))

    return syllables


def syllabify_from_ipa(ipa_string):
    """Split IPA string into syllable groups.

    Returns list of (ipa_segment, stress) tuples.
    """
    segments = segment_ipa(ipa_string)
    if not segments:
        return []

    # IPA vowels for nucleus detection
    ipa_vowels = set("ɑæʌəɔɛɜeɪɪiɒoʊuʉɐɨɘɵɤɯaɝɚ")
    diphthongs = {"aʊ", "aɪ", "eɪ", "oʊ", "əʊ", "ɔɪ", "ʌɪ", "ʌʊ"}

    def is_vowel_seg(seg):
        if seg in diphthongs:
            return True
        return any(c in ipa_vowels for c in seg) and seg not in ("ˈ", "ˌ")

    syllables = []
    current_ipa = ""
    current_stress = "unstressed"

    for seg in segments:
        if seg == "ˈ":
            if current_ipa:
                syllables.append((current_ipa, current_stress))
                current_ipa = ""
            current_stress = "primary"
            continue
        elif seg == "ˌ":
            if current_ipa:
                syllables.append((current_ipa, current_stress))
                current_ipa = ""
            current_stress = "secondary"
            continue

        # Check if adding this segment starts a new syllable
        if is_vowel_seg(seg) and any(
            c in ipa_vowels for c in current_ipa
        ):
            # Current syllable already has a vowel — split here
            syllables.append((current_ipa, current_stress))
            current_ipa = seg
            current_stress = "unstressed"
        else:
            current_ipa += seg

    if current_ipa:
        syllables.append((current_ipa, current_stress))

    return syllables


def build_syllables_json(word, ipa_string, arpabet_tokens):
    """Build the syllables JSON array for a variant.

    Returns JSON string of syllable objects: [{"text": ..., "ipa": ..., "stress": ...}]
    """
    pyphen_dict = get_pyphen_splitter()

    # Try ARPAbet-based syllabification first
    if arpabet_tokens:
        arpa_syls = syllabify_from_arpabet(arpabet_tokens)
        n_syls = len(arpa_syls)
    else:
        # Fall back to IPA-based
        ipa_syls = syllabify_from_ipa(ipa_string or "")
        n_syls = len(ipa_syls)
        arpa_syls = None

    if n_syls == 0:
        return json.dumps([{"text": word, "ipa": (ipa_string or "").strip("/"), "stress": "primary"}])

    # Get orthographic splits
    text_parts = split_text_into_syllables(word, n_syls, pyphen_dict)

    # Build syllable objects
    syllables = []
    if arpa_syls:
        ipa_syls_fallback = syllabify_from_ipa(ipa_string or "")
        for i, (tokens, stress) in enumerate(arpa_syls):
            text = text_parts[i] if i < len(text_parts) else ""
            # Get IPA for this syllable
            if ipa_syls_fallback and i < len(ipa_syls_fallback):
                syl_ipa = ipa_syls_fallback[i][0]
            else:
                syl_ipa = " ".join(tokens)
            syllables.append({
                "text": text,
                "ipa": syl_ipa,
                "stress": stress,
            })
    else:
        ipa_syls = syllabify_from_ipa(ipa_string or "")
        for i, (syl_ipa, stress) in enumerate(ipa_syls):
            text = text_parts[i] if i < len(text_parts) else ""
            syllables.append({
                "text": text,
                "ipa": syl_ipa,
                "stress": stress,
            })

    # Ensure at least one primary stress
    has_primary = any(s["stress"] == "primary" for s in syllables)
    if not has_primary and syllables:
        syllables[0]["stress"] = "primary"

    return json.dumps(syllables)


def main(argv=None):
    conn = get_db()

    # Get all variants that need syllabification
    rows = conn.execute("""
        SELECT v.word, v.region, v.ipa, v.arpabet, v.syllables
        FROM variants v
        JOIN target_words tw ON v.word = tw.word
        WHERE tw.included = 1
    """).fetchall()

    print(f"Variants to syllabify: {len(rows)}")

    pyphen_dict = get_pyphen_splitter()
    updated = 0

    with transaction(conn):
        for row in tqdm(rows, desc="Syllabifying"):
            word = row["word"]
            region = row["region"]
            ipa = row["ipa"]
            arpabet_json = row["arpabet"]

            # Parse ARPAbet tokens
            arpabet_tokens = json.loads(arpabet_json) if arpabet_json else []

            # Build syllables
            syllables_json = build_syllables_json(word, ipa, arpabet_tokens)

            conn.execute("""
                UPDATE variants SET syllables = ?
                WHERE word = ? AND region = ?
            """, (syllables_json, word, region))
            updated += 1

    conn.close()
    print(f"\nSyllabified: {updated} variants")
    return 0


if __name__ == "__main__":
    sys.exit(main())
