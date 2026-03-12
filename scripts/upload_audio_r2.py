#!/usr/bin/env python3
"""Upload audio files to Cloudflare R2 for CDN serving.

Syncs audio files from the data repo to R2, uploading only new or changed files.
Uses multipart upload for large batches and tracks uploads via ETag comparison.

Usage:
    python3 scripts/upload_audio_r2.py                    # Upload all audio
    python3 scripts/upload_audio_r2.py --region us        # Upload US audio only
    python3 scripts/upload_audio_r2.py --dry-run          # Preview without uploading
    python3 scripts/upload_audio_r2.py --workers 16       # Parallel uploads
"""

import argparse
import hashlib
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
from botocore.config import Config
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# R2 configuration
R2_ENDPOINT = os.environ.get("R2_ENDPOINT", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET = os.environ.get("R2_BUCKET", "pronouncehow")
R2_REGION = os.environ.get("R2_REGION", "auto")
R2_UPLOAD_PREFIX = os.environ.get("R2_UPLOAD_PREFIX", "audio")

# Audio source directory
AUDIO_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "pronounce-how-data" / "audio"
)

REGIONS = ["us", "uk", "ca", "au"]


def get_r2_client():
    """Create an S3-compatible client for Cloudflare R2."""
    if not R2_ENDPOINT or not R2_ACCESS_KEY_ID or not R2_SECRET_ACCESS_KEY:
        print("Error: R2 credentials not configured in .env")
        sys.exit(1)

    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name=R2_REGION,
        config=Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
            max_pool_connections=20,
        ),
    )


def list_remote_objects(client, prefix):
    """List all objects under a prefix in R2, returning {key: etag} dict."""
    remote = {}
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=R2_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            # Strip quotes from ETag
            remote[obj["Key"]] = obj["ETag"].strip('"')
    return remote


def md5_file(filepath):
    """Compute MD5 hex digest of a file."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_local_files(regions_filter=None):
    """Collect all local audio files, returning list of (local_path, r2_key)."""
    files = []
    regions = regions_filter if regions_filter else REGIONS

    for region in regions:
        region_dir = AUDIO_DIR / region
        if not region_dir.is_dir():
            print(f"  Warning: {region_dir} not found, skipping")
            continue
        for mp3 in sorted(region_dir.glob("*.mp3")):
            r2_key = f"{R2_UPLOAD_PREFIX}/{region}/{mp3.name}"
            files.append((mp3, r2_key))

    return files


def upload_file(client, local_path, r2_key):
    """Upload a single file to R2. Returns (r2_key, success, error)."""
    try:
        client.upload_file(
            str(local_path),
            R2_BUCKET,
            r2_key,
            ExtraArgs={"ContentType": "audio/mpeg"},
        )
        return (r2_key, True, None)
    except Exception as e:
        return (r2_key, False, str(e))


def main():
    parser = argparse.ArgumentParser(description="Upload audio files to Cloudflare R2.")
    parser.add_argument("--region", type=str, help="Upload only this region (us/uk/ca/au)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without uploading")
    parser.add_argument("--force", action="store_true", help="Re-upload all files (skip ETag check)")
    parser.add_argument("--workers", type=int, default=8, help="Parallel upload threads (default: 8)")
    args = parser.parse_args()

    regions_filter = [args.region.lower()] if args.region else None

    print("=" * 60)
    print("Audio Upload to Cloudflare R2")
    print("=" * 60)
    print(f"  Bucket:   {R2_BUCKET}")
    print(f"  Prefix:   {R2_UPLOAD_PREFIX}/")
    print(f"  Source:   {AUDIO_DIR}")
    print(f"  Workers:  {args.workers}")
    print()

    # Collect local files
    print("Scanning local audio files...")
    local_files = collect_local_files(regions_filter)
    print(f"  Local files: {len(local_files)}")

    if not local_files:
        print("No files to upload.")
        return 0

    client = get_r2_client()

    # Check what's already in R2 (skip in force mode)
    to_upload = []
    if args.force:
        to_upload = local_files
        print(f"  Force mode: uploading all {len(to_upload)} files")
    else:
        print("Listing remote objects...")
        prefix = R2_UPLOAD_PREFIX
        if regions_filter:
            prefix = f"{R2_UPLOAD_PREFIX}/{regions_filter[0]}"
        remote = list_remote_objects(client, prefix)
        print(f"  Remote files: {len(remote)}")

        # Compare MD5s to find new/changed files
        print("Comparing checksums...")
        skipped = 0
        for local_path, r2_key in tqdm(local_files, desc="Checking", unit="file"):
            if r2_key in remote:
                local_md5 = md5_file(local_path)
                if local_md5 == remote[r2_key]:
                    skipped += 1
                    continue
            to_upload.append((local_path, r2_key))

        print(f"  Unchanged (skip): {skipped}")
        print(f"  New/changed:      {len(to_upload)}")

    if not to_upload:
        print("\nAll files are up to date!")
        return 0

    if args.dry_run:
        print(f"\n[DRY RUN] Would upload {len(to_upload)} files:")
        for local_path, r2_key in to_upload[:20]:
            size_kb = local_path.stat().st_size / 1024
            print(f"  {r2_key} ({size_kb:.0f} KB)")
        if len(to_upload) > 20:
            print(f"  ... and {len(to_upload) - 20} more")
        return 0

    # Upload with thread pool
    print(f"\nUploading {len(to_upload)} files with {args.workers} workers...")
    start = time.time()
    uploaded = 0
    failed = 0
    errors = []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(upload_file, client, lp, rk): rk
            for lp, rk in to_upload
        }
        with tqdm(total=len(to_upload), desc="Uploading", unit="file") as pbar:
            for future in as_completed(futures):
                r2_key, success, error = future.result()
                if success:
                    uploaded += 1
                else:
                    failed += 1
                    errors.append((r2_key, error))
                pbar.update(1)

    elapsed = time.time() - start

    # Summary
    print(f"\n{'=' * 60}")
    print("Upload Summary")
    print(f"{'=' * 60}")
    print(f"  Uploaded:  {uploaded}")
    print(f"  Failed:    {failed}")
    print(f"  Time:      {elapsed:.1f}s")
    if uploaded > 0:
        print(f"  Rate:      {uploaded / elapsed:.1f} files/s")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for key, err in errors[:10]:
            print(f"  {key}: {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
