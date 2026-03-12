#!/usr/bin/env python3
"""Generate a scaffold JSON file for a new word.

Usage:
    python scripts/add_word.py <word> [--output-dir <path>] [--stdout]

Examples:
    python scripts/add_word.py hello --stdout
    python scripts/add_word.py "ice cream" --output-dir ../pronounce-how-data/data/words
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path


def slugify(word):
    """Convert a word to a URL-safe slug."""
    slug = word.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def get_ipa(word):
    """Try to get IPA using eng_to_ipa, fall back to TODO placeholder."""
    try:
        import eng_to_ipa
        ipa = eng_to_ipa.convert(word)
        if ipa and "*" not in ipa:
            return f"/{ipa}/"
    except ImportError:
        pass
    return "/TODO/"


def make_variant(region, ipa, derived_from=None):
    """Create a variant scaffold for a region."""
    variant = {
        "region": region,
        "ipa": ipa,
        "phonemes": ["TODO"],
        "syllables": [
            {
                "text": "TODO",
                "ipa": "TODO",
                "stress": "primary"
            }
        ],
        "respelling": "TODO",
        "source_type": "g2p_model" if ipa != "/TODO/" else "manual",
        "source_detail": "eng-to-ipa scaffold" if ipa != "/TODO/" else "TODO",
        "confidence": 0.50 if derived_from else 0.60,
        "confidence_reason": "Auto-generated scaffold, needs verification"
    }
    if derived_from:
        variant["derived_from"] = derived_from
    return variant


def generate_word(word):
    """Generate a full word entry scaffold."""
    slug = slugify(word)
    ipa = get_ipa(word)
    today = date.today().isoformat()

    entry = {
        "word": word,
        "slug": slug,
        "lang": "en",
        "pos": "noun",
        "priority": "medium",
        "status": "standard",
        "variants": [
            make_variant("US", ipa),
            make_variant("UK", ipa),
            make_variant("CA", ipa, derived_from="US"),
            make_variant("AU", ipa, derived_from="UK"),
        ],
        "updated_at": today,
        "created_at": today
    }
    return entry


def main():
    parser = argparse.ArgumentParser(
        description="Generate a scaffold JSON file for a new pronounceHow word entry."
    )
    parser.add_argument("word", help="The word to add")
    parser.add_argument(
        "--output-dir",
        help="Output directory (data/words). File is placed in the correct letter subdirectory.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print JSON to stdout instead of writing a file",
    )
    args = parser.parse_args()

    entry = generate_word(args.word)
    json_str = json.dumps(entry, indent=2, ensure_ascii=False) + "\n"

    if args.stdout:
        print(json_str, end="")
        return 0

    if not args.output_dir:
        print("Error: specify --output-dir or --stdout", file=sys.stderr)
        return 1

    slug = entry["slug"]
    letter_dir = Path(args.output_dir) / slug[0]
    letter_dir.mkdir(parents=True, exist_ok=True)
    output_path = letter_dir / f"{slug}.json"

    if output_path.exists():
        print(f"Error: {output_path} already exists", file=sys.stderr)
        return 1

    output_path.write_text(json_str, encoding="utf-8")
    print(f"Created: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
