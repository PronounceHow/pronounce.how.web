#!/usr/bin/env python3
"""
fix_todos.py - Find JSON word files with TODO and fix them via eSpeak NG.
"""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "pronounce-how-data" / "data" / "words"

VOICE_MAP = {
    "US": "en-us",
    "UK": "en-gb",
    "CA": "en-us",
    "AU": "en-au",
}

ESPEAK_CONFIDENCE = 0.50
ESPEAK_SOURCE_TYPE = "espeak"


def espeak_ipa(word, voice):
    """Run eSpeak NG and return raw IPA string."""
    try:
        result = subprocess.run(
            ["espeak-ng", "--ipa", "-v", voice, "-q", word],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None
        raw = result.stdout.strip()
        if raw:
            return raw.split("\n")[0].strip()
        return None
    except Exception as exc:
        print(f"  [ERROR] eSpeak failed for {word!r} ({voice}): {exc}", file=sys.stderr)
        return None


def has_todo(value):
    """Recursively check whether a value contains TODO."""
    if isinstance(value, str):
        return "TODO" in value
    if isinstance(value, list):
        return any(has_todo(item) for item in value)
    if isinstance(value, dict):
        return any(has_todo(v) for v in value.values())
    return False


def fix_variant(variant, word):
    """Fix TODO fields in a variant using eSpeak. Returns True if changed."""
    region = variant.get("region", "")
    voice = VOICE_MAP.get(region)
    if voice is None:
        print(f"  [WARN] No voice mapping for region {region!r}, skipping")
        return False

    todo_fields = []
    for key, val in variant.items():
        if has_todo(val):
            todo_fields.append(key)

    if not todo_fields:
        return False

    ipa_raw = espeak_ipa(word, voice)
    if ipa_raw is None:
        print(f"  [WARN] eSpeak returned no IPA for {word!r} ({voice})")
        return False

    ipa_with_slashes = f"/{ipa_raw}/"
    changed = False

    for field in todo_fields:
        if field == "ipa":
            variant["ipa"] = ipa_with_slashes
            changed = True
        elif field == "respelling":
            variant["respelling"] = ipa_raw
            changed = True
        elif isinstance(variant[field], str) and "TODO" in variant[field]:
            variant[field] = variant[field].replace("TODO", ipa_raw)
            changed = True

    if changed:
        variant["source_type"] = ESPEAK_SOURCE_TYPE
        variant["source_detail"] = f"eSpeak NG {voice}"
        variant["confidence"] = ESPEAK_CONFIDENCE
        variant["confidence_reason"] = f"eSpeak-generated IPA for {region}"

    return changed


def main():
    if not DATA_DIR.is_dir():
        print(f"ERROR: Data directory not found: {DATA_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning {DATA_DIR} for TODO entries ...")

    json_files = sorted(DATA_DIR.rglob("*.json"))
    print(f"Found {len(json_files)} total JSON files.")

    fixed_count = 0
    error_count = 0
    skipped_count = 0
    variant_fixes = 0
    today = date.today().isoformat()

    for fpath in json_files:
        try:
            raw_text = fpath.read_text(encoding="utf-8")
        except Exception as exc:
            print(f"  [ERROR] Cannot read {fpath}: {exc}", file=sys.stderr)
            error_count += 1
            continue

        if "TODO" not in raw_text:
            continue

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            print(f"  [ERROR] Bad JSON in {fpath}: {exc}", file=sys.stderr)
            error_count += 1
            continue

        word = data.get("word", fpath.stem)
        file_changed = False

        for variant in data.get("variants", []):
            if fix_variant(variant, word):
                file_changed = True
                variant_fixes += 1

        if file_changed:
            data["updated_at"] = today
            try:
                out = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
                fpath.write_text(out, encoding="utf-8")
                fixed_count += 1
                print(f"  FIXED: {fpath.relative_to(DATA_DIR)}  ({word})")
            except Exception as exc:
                print(f"  [ERROR] Cannot write {fpath}: {exc}", file=sys.stderr)
                error_count += 1
        else:
            skipped_count += 1
            print(f"  SKIPPED: {fpath.relative_to(DATA_DIR)}  ({word})")

    print()
    print("=" * 60)
    print(f"  Files fixed:    {fixed_count}")
    print(f"  Variants fixed: {variant_fixes}")
    print(f"  Skipped:        {skipped_count}")
    print(f"  Errors:         {error_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
