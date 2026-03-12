#!/usr/bin/env python3
"""Upload pronunciation videos to YouTube via Data API v3.

Uploads videos in YouTube Shorts format (1080x1920 vertical) with SEO-optimized
metadata generated from word JSON files. Supports playlists by first letter,
dry-run mode, rate limiting, and upload tracking to avoid duplicates.

YouTube API quota: 10,000 units/day; each upload costs 1,600 units (~6/day).

Usage:
    python -m pipeline.upload_youtube --video-dir video/ --data-dir ../pronounce-how-data/data/words
    python -m pipeline.upload_youtube --video-dir video/ --limit 5 --dry-run
    python -m pipeline.upload_youtube --video-dir video/ --playlist-prefix "Pronounce:"
    python -m pipeline.upload_youtube --video-dir video/ --words tomato schedule gyrfalcon
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from tqdm import tqdm

from .config import DATA_WORDS_DIR

# ── Logging ──────────────────────────────────────────────────────────────────

logger = logging.getLogger("upload_youtube")

# ── Constants ────────────────────────────────────────────────────────────────

PIPELINE_DIR = Path(__file__).resolve().parent
TOKEN_PATH = PIPELINE_DIR / "youtube_token.json"
UPLOADS_TRACKER_PATH = PIPELINE_DIR / "youtube_uploads.json"

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# YouTube API quota costs
QUOTA_PER_UPLOAD = 1600  # videos.insert = 1600 units
QUOTA_DAILY_LIMIT = 10_000
MAX_UPLOADS_PER_DAY = QUOTA_DAILY_LIMIT // QUOTA_PER_UPLOAD  # 6

# Rate limiting: minimum seconds between uploads to stay well within quota
MIN_UPLOAD_INTERVAL_SECONDS = 30

# YouTube Shorts: max 60 seconds, vertical 9:16, #Shorts in title/description
YOUTUBE_CATEGORY_EDUCATION = "27"

# Scopes needed for uploading videos and managing playlists
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

# Regions in display order
REGION_ORDER = ["US", "UK", "CA", "AU"]
REGION_LABELS = {
    "US": "American English",
    "UK": "British English",
    "CA": "Canadian English",
    "AU": "Australian English",
}
REGION_FLAGS = {
    "US": "\U0001f1fa\U0001f1f8",
    "UK": "\U0001f1ec\U0001f1e7",
    "CA": "\U0001f1e8\U0001f1e6",
    "AU": "\U0001f1e6\U0001f1fa",
}


# ── SEO metadata generation ─────────────────────────────────────────────────

def generate_title(word_data: dict) -> str:
    """Generate YouTube title from word data.

    Template:
        How to Pronounce "{word}" -- US, UK, CA, AU English | pronounce.how
    """
    word = word_data["word"]
    title = (
        f'How to Pronounce "{word}" '
        f"\u2014 US, UK, CA, AU English | pronounce.how"
    )
    # YouTube title limit is 100 characters
    if len(title) > 100:
        title = f'How to Pronounce "{word}" | pronounce.how'
    if len(title) > 100:
        title = f'Pronounce "{word}" | pronounce.how'
    return title


def _get_variant(word_data: dict, region: str) -> dict | None:
    """Get the variant for a specific region, or None."""
    for v in word_data.get("variants", []):
        if v.get("region") == region:
            return v
    return None


def generate_description(word_data: dict) -> str:
    """Generate YouTube description from word data.

    Follows the SEO template from the project plan with IPA, respelling,
    context sentence, common mistakes, and a link to the website.
    """
    word = word_data["word"]
    slug = word_data["slug"]

    lines = [
        f'Learn how to pronounce "{word}" in American, British, Canadian, '
        f"and Australian English \u2014 all in one video.",
        "",
    ]

    # Regional pronunciations
    for region in REGION_ORDER:
        variant = _get_variant(word_data, region)
        if variant:
            flag = REGION_FLAGS.get(region, "")
            ipa = variant.get("ipa", "")
            respelling = variant.get("respelling", "")
            lines.append(f"{flag} {region}: {ipa} \u2014 {respelling}")
        else:
            flag = REGION_FLAGS.get(region, "")
            lines.append(f"{flag} {region}: (not available)")

    lines.append("")

    # Context sentence
    context = word_data.get("context_sentence")
    if context:
        lines.append(f'"{context}"')
        lines.append("")

    # Common mistakes
    mistakes = word_data.get("common_mistakes", [])
    if mistakes:
        mistake_parts = []
        for m in mistakes:
            explanation = m.get("explanation", "")
            if explanation:
                mistake_parts.append(explanation)
        if mistake_parts:
            lines.append(f"Common mistakes: {'; '.join(mistake_parts)}")
            lines.append("")

    # Links
    lines.append(
        f"\U0001f310 Details + contribute: https://pronounce.how/{slug}"
    )
    lines.append(
        f"\U0001f4d6 Open-source data: https://github.com/PronounceHow/pronounce.how"
    )
    lines.append(
        f"\u270f\ufe0f Edit this word: https://github.com/PronounceHow/pronounce.how/blob/main/data/words/{slug[0]}/{slug}.json"
    )
    lines.append("")

    # Hashtags for Shorts discoverability
    lines.append("#Shorts #pronunciation #English #ESL #pronouncehow")

    description = "\n".join(lines)

    # YouTube description limit is 5,000 characters
    if len(description) > 5000:
        description = description[:4997] + "..."

    return description


def generate_tags(word_data: dict) -> list[str]:
    """Generate YouTube tags from word data.

    Tags help with search discoverability. YouTube allows up to 500 characters
    total across all tags.
    """
    word = word_data["word"]

    tags = [
        f"how to pronounce {word}",
        f"{word} pronunciation",
        f"{word} American English",
        f"{word} British English",
        f"{word} Canadian English",
        f"{word} Australian English",
        "English pronunciation",
        "ESL",
        "pronounce.how",
        "pronunciation guide",
        "how to say",
        f"say {word}",
        "Shorts",
    ]

    # Add IPA-based tags for common search patterns
    us_variant = _get_variant(word_data, "US")
    if us_variant:
        respelling = us_variant.get("respelling", "")
        if respelling:
            tags.append(f"{word} {respelling}")

    # Trim to fit YouTube's 500-character tag limit
    total_chars = 0
    trimmed = []
    for tag in tags:
        total_chars += len(tag) + 1  # +1 for comma separator
        if total_chars > 500:
            break
        trimmed.append(tag)

    return trimmed


# ── Upload tracker ───────────────────────────────────────────────────────────

def load_upload_tracker(tracker_path: Path) -> dict:
    """Load the upload tracker JSON file.

    Returns a dict mapping slugs to upload records:
    {
        "tomato": {
            "video_id": "abc123",
            "uploaded_at": "2025-06-15T10:30:00Z",
            "title": "How to Pronounce ...",
            "playlist_id": "PLxxx",
        },
        ...
    }
    """
    if tracker_path.exists():
        try:
            data = json.loads(tracker_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load upload tracker %s: %s", tracker_path, exc)
    return {}


def save_upload_tracker(tracker_path: Path, tracker: dict) -> None:
    """Save the upload tracker to disk."""
    try:
        tracker_path.parent.mkdir(parents=True, exist_ok=True)
        json_str = json.dumps(tracker, indent=2, ensure_ascii=False) + "\n"
        tracker_path.write_text(json_str, encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to save upload tracker: %s", exc)


# ── YouTube API authentication ───────────────────────────────────────────────

def get_authenticated_service(client_secrets_file: str, token_path: Path):
    """Build an authenticated YouTube API service using OAuth2.

    On first run, opens a browser for user consent. Subsequent runs use the
    cached token (refreshing if expired).

    Args:
        client_secrets_file: Path to OAuth2 client secrets JSON from Google
            Cloud Console.
        token_path: Where to store/load the OAuth token.

    Returns:
        googleapiclient.discovery.Resource for YouTube Data API v3.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        logger.error(
            "Missing required packages. Install with:\n"
            "  pip install google-auth-oauthlib google-api-python-client"
        )
        raise SystemExit(1) from exc

    creds = None

    # Load cached token
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception:
            logger.warning("Cached token invalid, will re-authenticate.")
            creds = None

    # Refresh or obtain new credentials
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            logger.info("Refreshed expired OAuth token.")
        except Exception:
            logger.warning("Token refresh failed, will re-authenticate.")
            creds = None

    if not creds or not creds.valid:
        if not Path(client_secrets_file).exists():
            logger.error(
                "Client secrets file not found: %s\n"
                "Download it from Google Cloud Console > APIs & Services > Credentials.",
                client_secrets_file,
            )
            raise SystemExit(1)

        flow = InstalledAppFlow.from_client_secrets_file(
            client_secrets_file, SCOPES
        )
        try:
            creds = flow.run_local_server(port=0)
        except Exception:
            logger.info("Browser auth failed, falling back to console auth.")
            creds = flow.run_console()
        logger.info("OAuth authentication successful.")

        # Save token for next run
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        logger.info("Saved OAuth token to %s", token_path)

    return build(
        YOUTUBE_API_SERVICE_NAME,
        YOUTUBE_API_VERSION,
        credentials=creds,
    )


# ── Playlist management ─────────────────────────────────────────────────────

def get_or_create_playlist(
    youtube, title: str, playlist_cache: dict
) -> str | None:
    """Get an existing playlist by title, or create one.

    Args:
        youtube: Authenticated YouTube API service.
        title: Playlist title (e.g., "Pronounce: A words").
        playlist_cache: Dict mapping title -> playlist_id (updated in-place).

    Returns:
        Playlist ID string, or None on failure.
    """
    if title in playlist_cache:
        return playlist_cache[title]

    try:
        # Search existing playlists
        request = youtube.playlists().list(
            part="snippet",
            mine=True,
            maxResults=50,
        )
        response = request.execute()

        for item in response.get("items", []):
            pl_title = item["snippet"]["title"]
            pl_id = item["id"]
            playlist_cache[pl_title] = pl_id
            if pl_title == title:
                logger.debug("Found existing playlist: %s (%s)", title, pl_id)
                return pl_id

        # Handle pagination for channels with many playlists
        while response.get("nextPageToken"):
            request = youtube.playlists().list(
                part="snippet",
                mine=True,
                maxResults=50,
                pageToken=response["nextPageToken"],
            )
            response = request.execute()
            for item in response.get("items", []):
                pl_title = item["snippet"]["title"]
                pl_id = item["id"]
                playlist_cache[pl_title] = pl_id
                if pl_title == title:
                    logger.debug(
                        "Found existing playlist: %s (%s)", title, pl_id
                    )
                    return pl_id

    except Exception as exc:
        logger.warning("Failed to list playlists: %s", exc)

    # Create new playlist
    try:
        request = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": title,
                    "description": (
                        f"Pronunciation videos for words starting with "
                        f"'{title.split()[-2] if len(title.split()) >= 2 else '?'}'. "
                        f"Learn US, UK, CA, and AU English pronunciations. "
                        f"https://pronounce.how"
                    ),
                },
                "status": {
                    "privacyStatus": "public",
                },
            },
        )
        response = request.execute()
        pl_id = response["id"]
        playlist_cache[title] = pl_id
        logger.info("Created playlist: %s (%s)", title, pl_id)
        return pl_id

    except Exception as exc:
        logger.error("Failed to create playlist '%s': %s", title, exc)
        return None


def add_video_to_playlist(youtube, video_id: str, playlist_id: str) -> bool:
    """Add a video to a playlist.

    Returns True on success, False on failure.
    """
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id,
                    },
                },
            },
        ).execute()
        logger.debug("Added video %s to playlist %s", video_id, playlist_id)
        return True

    except Exception as exc:
        logger.warning(
            "Failed to add video %s to playlist %s: %s",
            video_id, playlist_id, exc,
        )
        return False


# ── Video upload ─────────────────────────────────────────────────────────────

def upload_video(
    youtube,
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    category_id: str = YOUTUBE_CATEGORY_EDUCATION,
    privacy_status: str = "public",
) -> str | None:
    """Upload a video to YouTube.

    Args:
        youtube: Authenticated YouTube API service.
        video_path: Path to the MP4 file.
        title: Video title.
        description: Video description.
        tags: List of tags.
        category_id: YouTube category ID (default: Education).
        privacy_status: "public", "private", or "unlisted".

    Returns:
        Video ID string on success, None on failure.
    """
    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        logger.error("Missing google-api-python-client package.")
        raise SystemExit(1) from exc

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,  # 10 MB chunks
    )

    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.debug(
                    "Upload progress: %.1f%%", status.progress() * 100
                )

        video_id = response["id"]
        logger.info(
            "Uploaded: %s -> https://youtube.com/watch?v=%s",
            video_path.name, video_id,
        )
        return video_id

    except Exception as exc:
        logger.error("Upload failed for %s: %s", video_path.name, exc)
        return None


# ── Batch processing ─────────────────────────────────────────────────────────

def discover_videos(
    video_dir: Path,
    data_dir: Path,
    words: list[str] | None = None,
) -> list[dict]:
    """Discover video files and match them with word JSON data.

    Returns a list of dicts with keys: slug, video_path, word_data.
    Sorted alphabetically by slug.
    """
    candidates = []

    if words:
        # Specific words requested
        for word in words:
            slug = word.lower().replace(" ", "-")
            video_path = video_dir / f"{slug}.mp4"
            json_path = data_dir / slug[0] / f"{slug}.json"

            if not video_path.exists():
                logger.warning("Video not found for '%s': %s", word, video_path)
                continue
            if not json_path.exists():
                logger.warning("Word data not found for '%s': %s", word, json_path)
                continue

            try:
                word_data = json.loads(json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read %s: %s", json_path, exc)
                continue

            candidates.append({
                "slug": slug,
                "video_path": video_path,
                "word_data": word_data,
            })
    else:
        # Discover all videos in the directory
        video_files = sorted(video_dir.glob("*.mp4"))
        for video_path in video_files:
            slug = video_path.stem
            json_path = data_dir / slug[0] / f"{slug}.json"

            if not json_path.exists():
                logger.debug("No word data for video %s, skipping.", slug)
                continue

            try:
                word_data = json.loads(json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read %s: %s", json_path, exc)
                continue

            candidates.append({
                "slug": slug,
                "video_path": video_path,
                "word_data": word_data,
            })

    return candidates


def run_upload_batch(
    youtube,
    candidates: list[dict],
    tracker: dict,
    tracker_path: Path,
    playlist_prefix: str,
    privacy_status: str,
    dry_run: bool = False,
    limit: int = 0,
) -> dict:
    """Upload a batch of videos, skipping already-uploaded ones.

    Args:
        youtube: Authenticated YouTube API service (None if dry_run).
        candidates: List of {slug, video_path, word_data} dicts.
        tracker: Upload tracker dict (modified in-place).
        tracker_path: Path to save tracker after each upload.
        playlist_prefix: Prefix for playlist names (e.g., "Pronounce:").
        privacy_status: YouTube privacy status for uploads.
        dry_run: If True, preview metadata without uploading.
        limit: Max number of uploads (0 = no limit, respects daily quota).

    Returns:
        Summary dict with counts.
    """
    playlist_cache = {}
    stats = {
        "uploaded": 0,
        "skipped_already_uploaded": 0,
        "skipped_no_video": 0,
        "failed": 0,
        "dry_run_previewed": 0,
    }

    # Filter out already-uploaded videos
    to_upload = []
    for candidate in candidates:
        slug = candidate["slug"]
        if slug in tracker:
            stats["skipped_already_uploaded"] += 1
            logger.debug("Already uploaded: %s", slug)
            continue
        to_upload.append(candidate)

    if limit > 0:
        effective_limit = min(limit, MAX_UPLOADS_PER_DAY)
        if limit > MAX_UPLOADS_PER_DAY:
            logger.warning(
                "Limit %d exceeds daily quota cap of %d uploads/day. "
                "Capping at %d.",
                limit, MAX_UPLOADS_PER_DAY, MAX_UPLOADS_PER_DAY,
            )
        to_upload = to_upload[:effective_limit]
    else:
        # Even without explicit limit, cap at daily quota
        if len(to_upload) > MAX_UPLOADS_PER_DAY and not dry_run:
            logger.warning(
                "%d videos to upload, but daily quota allows ~%d. "
                "Processing first %d. Use --limit to control batch size.",
                len(to_upload), MAX_UPLOADS_PER_DAY, MAX_UPLOADS_PER_DAY,
            )
            to_upload = to_upload[:MAX_UPLOADS_PER_DAY]

    if not to_upload:
        logger.info("No new videos to upload.")
        return stats

    action = "Previewing" if dry_run else "Uploading"
    logger.info("%s %d video(s)...", action, len(to_upload))

    last_upload_time = 0.0

    for candidate in tqdm(to_upload, desc=action, unit="video"):
        slug = candidate["slug"]
        video_path = candidate["video_path"]
        word_data = candidate["word_data"]

        # Generate metadata
        title = generate_title(word_data)
        description = generate_description(word_data)
        tags = generate_tags(word_data)

        if dry_run:
            stats["dry_run_previewed"] += 1
            _print_dry_run(slug, video_path, title, description, tags)
            continue

        # Rate limiting
        elapsed = time.monotonic() - last_upload_time
        if elapsed < MIN_UPLOAD_INTERVAL_SECONDS and last_upload_time > 0:
            wait = MIN_UPLOAD_INTERVAL_SECONDS - elapsed
            logger.debug("Rate limiting: waiting %.1fs...", wait)
            time.sleep(wait)

        # Upload
        video_id = upload_video(
            youtube,
            video_path,
            title,
            description,
            tags,
            privacy_status=privacy_status,
        )

        last_upload_time = time.monotonic()

        if not video_id:
            stats["failed"] += 1
            continue

        # Add to playlist
        letter = slug[0].upper()
        playlist_title = f"{playlist_prefix} {letter} words"
        playlist_id = get_or_create_playlist(
            youtube, playlist_title, playlist_cache
        )
        if playlist_id:
            add_video_to_playlist(youtube, video_id, playlist_id)

        # Record in tracker
        tracker[slug] = {
            "video_id": video_id,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "title": title,
            "playlist_id": playlist_id,
            "video_url": f"https://youtube.com/watch?v={video_id}",
        }
        save_upload_tracker(tracker_path, tracker)

        stats["uploaded"] += 1
        logger.info(
            "Uploaded %d/%d: %s -> %s",
            stats["uploaded"], len(to_upload), slug, video_id,
        )

    return stats


def _print_dry_run(
    slug: str,
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
) -> None:
    """Print a dry-run preview of upload metadata."""
    size_mb = video_path.stat().st_size / (1024 * 1024) if video_path.exists() else 0
    separator = "-" * 70

    print(f"\n{separator}")
    print(f"  Slug:        {slug}")
    print(f"  Video:       {video_path} ({size_mb:.1f} MB)")
    print(f"  Title:       {title}")
    print(f"  Tags:        {', '.join(tags[:8])}{'...' if len(tags) > 8 else ''}")
    print(f"  Description:")
    for line in description.split("\n")[:12]:
        print(f"    {line}")
    if description.count("\n") > 12:
        print(f"    ... ({description.count(chr(10)) - 12} more lines)")
    print(separator)


# ── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Upload pronunciation videos to YouTube via Data API v3. "
            "Generates SEO metadata from word JSON files. "
            "Tracks uploads to avoid re-uploading."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Dry run to preview metadata\n"
            "  python -m pipeline.upload_youtube --video-dir video/ --dry-run\n"
            "\n"
            "  # Upload up to 5 videos\n"
            "  python -m pipeline.upload_youtube --video-dir video/ --limit 5\n"
            "\n"
            "  # Upload specific words\n"
            "  python -m pipeline.upload_youtube --video-dir video/ "
            "--words tomato schedule\n"
            "\n"
            "  # Use custom client secrets and playlist prefix\n"
            "  python -m pipeline.upload_youtube --video-dir video/ "
            "--client-secrets ~/secrets.json --playlist-prefix 'Say it:'\n"
        ),
    )

    parser.add_argument(
        "--video-dir",
        type=Path,
        default=Path("video"),
        help="Directory containing MP4 video files (default: video/)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_WORDS_DIR,
        help=(
            "Directory containing word JSON files organized by letter "
            "(default: from config)"
        ),
    )
    parser.add_argument(
        "--words",
        nargs="+",
        metavar="WORD",
        help="Upload only these specific words (by slug name)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help=(
            "Maximum number of videos to upload in this run "
            f"(default: 0 = up to daily quota of {MAX_UPLOADS_PER_DAY})"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview metadata without uploading anything",
    )
    parser.add_argument(
        "--client-secrets",
        type=str,
        default="client_secrets.json",
        help="Path to OAuth2 client secrets JSON (default: client_secrets.json)",
    )
    parser.add_argument(
        "--token-path",
        type=Path,
        default=TOKEN_PATH,
        help=f"Path to cached OAuth token (default: {TOKEN_PATH})",
    )
    parser.add_argument(
        "--tracker-path",
        type=Path,
        default=UPLOADS_TRACKER_PATH,
        help=f"Path to upload tracker JSON (default: {UPLOADS_TRACKER_PATH})",
    )
    parser.add_argument(
        "--playlist-prefix",
        type=str,
        default="Pronounce:",
        help='Prefix for playlist names (default: "Pronounce:")',
    )
    parser.add_argument(
        "--privacy",
        choices=["public", "private", "unlisted"],
        default="public",
        help="Video privacy status (default: public)",
    )
    parser.add_argument(
        "--reset-tracker",
        action="store_true",
        help="Reset the upload tracker (allows re-uploading everything)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )

    return parser


def main(argv=None) -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    video_dir = args.video_dir.resolve()
    data_dir = args.data_dir.resolve()

    # Validate directories
    if not video_dir.is_dir():
        logger.error("Video directory not found: %s", video_dir)
        return 1

    if not data_dir.is_dir():
        logger.error("Data directory not found: %s", data_dir)
        return 1

    # Load or reset tracker
    tracker_path = args.tracker_path
    if args.reset_tracker:
        logger.warning("Resetting upload tracker at %s", tracker_path)
        tracker = {}
        save_upload_tracker(tracker_path, tracker)
    else:
        tracker = load_upload_tracker(tracker_path)
        logger.info(
            "Upload tracker: %d previously uploaded videos.", len(tracker)
        )

    # Discover videos
    logger.info("Discovering videos in %s ...", video_dir)
    candidates = discover_videos(video_dir, data_dir, words=args.words)
    logger.info(
        "Found %d video(s) with matching word data.", len(candidates)
    )

    if not candidates:
        logger.warning("No videos found to process.")
        return 0

    # Authenticate (skip in dry-run mode)
    youtube = None
    if not args.dry_run:
        logger.info("Authenticating with YouTube API...")
        youtube = get_authenticated_service(
            args.client_secrets, args.token_path
        )

    # Run uploads
    stats = run_upload_batch(
        youtube=youtube,
        candidates=candidates,
        tracker=tracker,
        tracker_path=tracker_path,
        playlist_prefix=args.playlist_prefix,
        privacy_status=args.privacy,
        dry_run=args.dry_run,
        limit=args.limit,
    )

    # Print summary
    print(f"\n{'=' * 60}")
    print("Upload Summary")
    print(f"{'=' * 60}")

    if args.dry_run:
        print(f"  [DRY RUN] Previewed:   {stats['dry_run_previewed']}")
    else:
        print(f"  Uploaded:              {stats['uploaded']}")
        print(f"  Failed:                {stats['failed']}")

    print(f"  Skipped (already up):  {stats['skipped_already_uploaded']}")
    print(f"  Total tracked:         {len(tracker)}")

    if not args.dry_run and stats["uploaded"] > 0:
        remaining_quota = QUOTA_DAILY_LIMIT - (stats["uploaded"] * QUOTA_PER_UPLOAD)
        remaining_uploads = remaining_quota // QUOTA_PER_UPLOAD
        print(f"\n  Estimated remaining daily quota: ~{remaining_uploads} uploads")

    print(f"  Tracker file: {tracker_path}")
    print(f"{'=' * 60}")

    return 1 if stats.get("failed", 0) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
