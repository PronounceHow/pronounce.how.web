#!/usr/bin/env python3
"""Download raw source files for the pipeline.

Usage:
    python -m pipeline.download_sources [--force] [--skip-kaikki]

Downloads to pipeline/sources/. Skips existing files unless --force.
"""

import argparse
import sys
from pathlib import Path

import requests
from tqdm import tqdm

from .config import SOURCES_DIR, SOURCE_URLS


def download_file(url, dest_path, force=False):
    """Download a file with progress bar. Skip if exists and not --force."""
    if dest_path.exists() and not force:
        size_mb = dest_path.stat().st_size / (1024 * 1024)
        print(f"  Exists: {dest_path.name} ({size_mb:.1f} MB) — skipping")
        return True

    print(f"  Downloading: {dest_path.name}")
    print(f"    URL: {url}")

    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with open(dest_path, "wb") as f:
            with tqdm(total=total, unit="B", unit_scale=True,
                      desc=dest_path.name, disable=total == 0) as pbar:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    pbar.update(len(chunk))

        size_mb = dest_path.stat().st_size / (1024 * 1024)
        print(f"    Done: {size_mb:.1f} MB")
        return True

    except requests.RequestException as e:
        print(f"    FAILED: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description="Download pipeline source files.")
    parser.add_argument("--force", action="store_true",
                        help="Re-download even if files exist")
    parser.add_argument("--skip-kaikki", action="store_true",
                        help="Skip the 2.7GB Wiktextract JSONL file")
    args = parser.parse_args(argv)

    SOURCES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Download directory: {SOURCES_DIR}\n")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for filename, url in SOURCE_URLS.items():
        if args.skip_kaikki and "kaikki" in filename:
            print(f"  Skipping: {filename} (--skip-kaikki)")
            skip_count += 1
            continue

        dest = SOURCES_DIR / filename
        if download_file(url, dest, force=args.force):
            success_count += 1
        else:
            fail_count += 1

    print(f"\nDownloaded: {success_count}, Skipped: {skip_count}, Failed: {fail_count}")
    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
