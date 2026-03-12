#!/usr/bin/env python3
"""Robust audio generation wrapper that processes in batches to avoid memory leaks.

Runs build_audio in chunks of BATCH_SIZE words, restarting the subprocess each batch
to prevent espeak-ng/ffmpeg memory corruption crashes.

Usage:
    python3 pipeline/build_audio_robust.py
"""

import subprocess
import sys
import time
import json
from pathlib import Path

DATA_DIR = Path("/home/solcal/pronounceHow/pronounce-how-data/data/words")
BATCH_SIZE = 200  # words per subprocess run — keeps memory usage low
LOG_FILE = Path("/home/solcal/pronounceHow/audio_generation.log")


def count_cached_audio():
    """Count how many audio files already exist."""
    cache_dir = Path("/home/solcal/pronounceHow/pronounce-how/pipeline/audio_cache")
    if cache_dir.exists():
        return len(list(cache_dir.glob("*.mp3")))
    return 0


def get_all_word_files():
    """Get sorted list of all word JSON files."""
    return sorted(DATA_DIR.rglob("*.json"))


def count_audio_for_word(slug):
    """Check how many audio files exist for a word (max 8: 4 regions × 2 speeds)."""
    audio_dir = DATA_DIR.parent.parent / "audio"
    count = 0
    for region in ("us", "uk", "ca", "au"):
        for speed in ("normal", "slow"):
            path = audio_dir / region / f"{slug}_{speed}.mp3"
            if path.exists():
                count += 1
    return count


def find_incomplete_words(word_files):
    """Find words that don't have all 8 audio files yet."""
    incomplete = []
    for wf in word_files:
        try:
            with open(wf) as f:
                data = json.load(f)
            slug = data.get("slug", "")
            if slug and count_audio_for_word(slug) < 8:
                incomplete.append(wf)
        except Exception:
            incomplete.append(wf)
    return incomplete


def run_batch(word_files, batch_num, total_batches):
    """Run build_audio for a batch of words using a temp word list."""
    if not word_files:
        return True

    # Write temp file list
    tmpfile = Path("/tmp/audio_batch_files.txt")
    tmpfile.write_text("\n".join(str(f) for f in word_files))

    n_words = len(word_files)
    first_word = word_files[0].stem if word_files else "?"
    last_word = word_files[-1].stem if word_files else "?"

    print(f"\n[Batch {batch_num}/{total_batches}] Processing {n_words} words ({first_word} → {last_word})")
    sys.stdout.flush()

    # Run as subprocess so memory is freed after each batch
    result = subprocess.run(
        [
            sys.executable, "-u", "-c",
            f"""
import json, sys, os, subprocess, hashlib
from pathlib import Path

sys.path.insert(0, '/home/solcal/pronounceHow/pronounce-how')
os.chdir('/home/solcal/pronounceHow/pronounce-how')

# Load env
from dotenv import load_dotenv
load_dotenv()

from pipeline.config import TTS_VOICES, AUDIO_CACHE_DIR
from pipeline.build_audio import (
    content_hash, get_google_tts_client, get_azure_tts_config,
    synthesize_google, synthesize_azure, synthesize_espeak
)

AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

files = Path('/tmp/audio_batch_files.txt').read_text().strip().split('\\n')
regions = ['US', 'UK', 'CA', 'AU']
audio_dir = Path('/home/solcal/pronounceHow/pronounce-how-data/audio')

google_client = get_google_tts_client()
azure_config = get_azure_tts_config()

generated = cached = failed = errors = 0

for filepath in files:
    filepath = Path(filepath)
    try:
        with open(filepath) as f:
            entry = json.load(f)
    except Exception:
        errors += 1
        continue

    word = entry.get('word', '')
    slug = entry.get('slug', '')

    for variant in entry.get('variants', []):
        region = variant.get('region', '')
        if region not in regions:
            continue

        ipa = variant.get('ipa', '')
        voice_config = TTS_VOICES.get(region, {{}})
        backend = voice_config.get('backend', 'espeak')
        voice_name = voice_config.get('voice', '')
        lang_code = voice_config.get('language_code', '')

        for speed in ('normal', 'slow'):
            try:
                cache_key = content_hash(word, region, ipa, backend, voice_name)
                cache_path = AUDIO_CACHE_DIR / f'{{cache_key}}_{{speed}}.mp3'

                if cache_path.exists():
                    cached += 1
                    continue

                audio_data = None
                if backend == 'google' and google_client:
                    audio_data = synthesize_google(google_client, word, voice_name, lang_code, rate=speed)
                elif backend == 'azure' and azure_config:
                    audio_data = synthesize_azure(azure_config, word, voice_name, rate=speed)

                if audio_data is None:
                    espeak_voice = {{'US': 'en-us', 'UK': 'en-gb', 'AU': 'en-au', 'CA': 'en-us'}}.get(region, 'en-us')
                    audio_data = synthesize_espeak(word, espeak_voice, speed)

                if audio_data:
                    cache_path.write_bytes(audio_data)
                    region_dir = audio_dir / region.lower()
                    region_dir.mkdir(parents=True, exist_ok=True)
                    out_path = region_dir / f'{{slug}}_{{speed}}.mp3'
                    out_path.write_bytes(audio_data)
                    generated += 1
                else:
                    failed += 1
            except Exception as e:
                print(f'  Error {{word}}/{{region}}/{{speed}}: {{e}}')
                errors += 1

print(f'BATCH_RESULT: generated={{generated}} cached={{cached}} failed={{failed}} errors={{errors}}')
"""
        ],
        timeout=1800,  # 30 minutes per batch max
        cwd="/home/solcal/pronounceHow/pronounce-how",
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    return result.returncode == 0


def main():
    print("=" * 60)
    print("Robust Audio Generation")
    print("=" * 60)

    word_files = get_all_word_files()
    total = len(word_files)
    print(f"Total word files: {total}")

    # Find words that still need audio
    print("Scanning for incomplete words...")
    incomplete = find_incomplete_words(word_files)
    print(f"Words needing audio: {len(incomplete)} / {total}")
    print(f"Already complete: {total - len(incomplete)}")

    if not incomplete:
        print("All words have audio! Nothing to do.")
        return 0

    # Process in batches
    total_batches = (len(incomplete) + BATCH_SIZE - 1) // BATCH_SIZE
    total_processed = total - len(incomplete)

    for i in range(0, len(incomplete), BATCH_SIZE):
        batch = incomplete[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_processed += len(batch)

        pct = total_processed / total * 100
        print(f"\nOverall progress: {total_processed}/{total} ({pct:.1f}%)")

        success = run_batch(batch, batch_num, total_batches)
        if not success:
            print(f"  Batch {batch_num} failed, continuing to next batch...")

        # Brief pause between batches to let OS reclaim memory
        time.sleep(1)

    print(f"\n{'=' * 60}")
    print("Audio generation complete!")

    # Final count
    audio_dir = DATA_DIR.parent.parent / "audio"
    for region in ("us", "uk", "ca", "au"):
        rdir = audio_dir / region
        if rdir.exists():
            count = len(list(rdir.glob("*.mp3")))
            print(f"  {region.upper()}: {count} files")

    return 0


if __name__ == "__main__":
    sys.exit(main())
