#!/usr/bin/env python3
"""Add related_words cross-links to word JSON files.

For commonly confused pairs, US/UK spelling variants, and word families,
this script adds a "related_words" field so the front-end can show
"Did you mean …?" or "See also …" links.

Usage:
    cd /home/solcal/pronounceHow/pronounce-how
    python3 pipeline/add_minimal_pairs.py [--dry-run]
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


# ── Data directory ───────────────────────────────────────────────────────────
DATA_WORDS_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "pronounce-how-data" / "data" / "words"
)


# ── Relationship groups ──────────────────────────────────────────────────────

COMMONLY_CONFUSED = [
    ["affect", "effect"],
    ["accept", "except"],
    ["advise", "advice"],
    ["breath", "breathe"],
    ["complement", "compliment"],
    ["desert", "dessert"],
    ["emigrate", "immigrate"],
    ["ensure", "insure"],
    ["farther", "further"],
    ["loose", "lose"],
    ["precede", "proceed"],
    ["principal", "principle"],
    ["stationary", "stationery"],
    ["than", "then"],
    ["their", "there", "they're"],
    ["to", "too", "two"],
    ["weather", "whether"],
    ["your", "you're"],
    ["lead", "led"],
    ["cite", "site", "sight"],
    ["peace", "piece"],
    ["break", "brake"],
    ["hear", "here"],
    ["flour", "flower"],
    ["knew", "new"],
    ["right", "write"],
    ["sole", "soul"],
    ["steal", "steel"],
    ["tail", "tale"],
    ["wait", "weight"],
    ["wear", "where"],
    ["whole", "hole"],
]

US_UK_SPELLING = [
    ["colour", "color"],
    ["favourite", "favorite"],
    ["honour", "honor"],
    ["centre", "center"],
    ["realise", "realize"],
    ["analyse", "analyze"],
    ["defence", "defense"],
    ["licence", "license"],
]

WORD_FAMILIES = [
    ["pronounce", "pronunciation", "pronounced"],
    ["schedule", "scheduled", "scheduling"],
    ["access", "accessible", "accessories"],
    ["accommodate", "accommodation"],
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def slugify(word):
    """Convert a word to a URL-safe slug (mirrors pipeline.db.slugify)."""
    slug = word.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def json_path(slug):
    """Return the Path for a slug's JSON file."""
    if not slug:
        return None
    first_letter = slug[0]
    return DATA_WORDS_DIR / first_letter / f"{slug}.json"


def load_json(path):
    """Load and return parsed JSON from *path*, or None on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_json(path, data):
    """Write *data* as pretty-printed JSON to *path*."""
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ── Core logic ───────────────────────────────────────────────────────────────

def build_link_map(groups, relationship):
    """Return a dict mapping each slug to a set of (other_slug, relationship).

    Only includes entries where both JSON files exist on disk.
    """
    links = defaultdict(set)

    for group in groups:
        slugs = [slugify(w) for w in group]
        # Filter to slugs whose JSON files actually exist
        existing = [s for s in slugs if json_path(s).is_file()]

        # Cross-link every pair among existing slugs
        for i, s1 in enumerate(existing):
            for s2 in existing:
                if s1 != s2:
                    links[s1].add((s2, relationship))

    return links


def merge_links(*link_maps):
    """Merge multiple link maps into one."""
    merged = defaultdict(set)
    for lm in link_maps:
        for slug, targets in lm.items():
            merged[slug].update(targets)
    return merged


def apply_links(all_links, dry_run=False):
    """Read each word's JSON, inject related_words, and write back.

    Returns (updated_count, skipped_count).
    """
    updated = 0
    skipped = 0

    for slug in sorted(all_links):
        path = json_path(slug)
        data = load_json(path)
        if data is None:
            skipped += 1
            continue

        # Build the related_words list
        new_related = sorted(
            [{"slug": target, "relationship": rel}
             for target, rel in all_links[slug]],
            key=lambda r: (r["relationship"], r["slug"]),
        )

        # Merge with any existing related_words already on disk
        existing_related = data.get("related_words", [])
        existing_set = {
            (e["slug"], e["relationship"]) for e in existing_related
        }
        for entry in new_related:
            key = (entry["slug"], entry["relationship"])
            if key not in existing_set:
                existing_related.append(entry)
                existing_set.add(key)

        # Re-sort the combined list
        data["related_words"] = sorted(
            existing_related,
            key=lambda r: (r["relationship"], r["slug"]),
        )

        if dry_run:
            updated += 1
            continue

        save_json(path, data)
        updated += 1

    return updated, skipped


# ── Main ─────────────────────────────────────────────────────────────────────

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Add related_words cross-links to word JSON files.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would change without writing files.",
    )
    args = parser.parse_args(argv)

    if not DATA_WORDS_DIR.is_dir():
        print(f"ERROR: Data directory not found: {DATA_WORDS_DIR}")
        return 1

    # Build link maps for each relationship type
    confused_links = build_link_map(COMMONLY_CONFUSED, "commonly_confused")
    spelling_links = build_link_map(US_UK_SPELLING, "us_uk_spelling")
    family_links = build_link_map(WORD_FAMILIES, "word_family")

    all_links = merge_links(confused_links, spelling_links, family_links)

    total_pairs = sum(len(v) for v in all_links.values())
    print(f"Data directory : {DATA_WORDS_DIR}")
    print(f"Word slugs to update : {len(all_links)}")
    print(f"Total directional links: {total_pairs}")
    print()

    # Breakdown by relationship type
    for label, lm in [
        ("commonly_confused", confused_links),
        ("us_uk_spelling", spelling_links),
        ("word_family", family_links),
    ]:
        slugs = len(lm)
        links = sum(len(v) for v in lm.values())
        print(f"  {label:25s}  {slugs:3d} words, {links:3d} links")

    print()

    if args.dry_run:
        print("[DRY RUN] No files will be modified.")

    updated, skipped = apply_links(all_links, dry_run=args.dry_run)

    print(f"\nResults:")
    print(f"  Words updated: {updated}")
    print(f"  Words skipped (file not found): {skipped}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
