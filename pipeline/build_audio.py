#!/usr/bin/env python3
"""Generate TTS audio files for all words.

Google Cloud TTS (US/UK/AU) + Azure TTS (CA).
Credentials read from environment variables.

Usage:
    python -m pipeline.build_audio [--data-dir PATH] [--regions us,uk,ca,au]
                                   [--backend google|azure|espeak] [--limit N]
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from tqdm import tqdm

from .config import TTS_VOICES, DATA_WORDS_DIR, AUDIO_CACHE_DIR


def content_hash(word, region, ipa, backend, voice):
    """Generate a content hash for cache lookup."""
    key = f"{word}|{region}|{ipa}|{backend}|{voice}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def get_google_tts_client():
    """Get Google Cloud TTS client. Returns None if credentials missing."""
    try:
        from google.cloud import texttospeech
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not creds_path:
            print("  Warning: GOOGLE_APPLICATION_CREDENTIALS not set")
            return None
        client = texttospeech.TextToSpeechClient()
        return client
    except ImportError:
        print("  Warning: google-cloud-texttospeech not installed")
        return None
    except Exception as e:
        print(f"  Warning: Google TTS init failed: {e}")
        return None


def get_azure_tts_config():
    """Get Azure TTS config. Returns None if credentials missing."""
    key = os.environ.get("AZURE_SPEECH_KEY")
    region = os.environ.get("AZURE_SPEECH_REGION")
    if not key or not region:
        print("  Warning: AZURE_SPEECH_KEY/AZURE_SPEECH_REGION not set")
        return None
    return {"key": key, "region": region}


def synthesize_google(client, text, voice_name, language_code, rate="medium"):
    """Synthesize audio via Google Cloud TTS. Returns audio bytes or None."""
    try:
        from google.cloud import texttospeech

        # Build SSML for rate control
        if rate == "slow":
            ssml = f'<speak><prosody rate="slow">{text}</prosody></speak>'
            input_text = texttospeech.SynthesisInput(ssml=ssml)
        else:
            input_text = texttospeech.SynthesisInput(text=text)

        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            sample_rate_hertz=44100,
        )

        response = client.synthesize_speech(
            input=input_text, voice=voice, audio_config=audio_config
        )
        return response.audio_content

    except Exception as e:
        print(f"    Google TTS error: {e}")
        return None


def synthesize_azure(config, text, voice_name, rate="medium"):
    """Synthesize audio via Azure TTS. Returns audio bytes or None."""
    try:
        import azure.cognitiveservices.speech as speechsdk

        speech_config = speechsdk.SpeechConfig(
            subscription=config["key"],
            region=config["region"],
        )
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        )

        # Build SSML
        rate_val = "slow" if rate == "slow" else "medium"
        ssml = (
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xml:lang="en-CA">'
            f'<voice name="{voice_name}">'
            f'<prosody rate="{rate_val}">{text}</prosody>'
            f'</voice></speak>'
        )

        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=None
        )
        result = synthesizer.speak_ssml_async(ssml).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return result.audio_data
        else:
            print(f"    Azure TTS error: {result.reason}")
            return None

    except ImportError:
        print("    azure-cognitiveservices-speech not installed")
        return None
    except Exception as e:
        print(f"    Azure TTS error: {e}")
        return None


def synthesize_espeak(word, voice="en-us", rate="normal"):
    """Fallback: synthesize via eSpeak NG + FFmpeg. Returns audio bytes or None."""
    try:
        # Generate WAV via eSpeak
        speed = "100" if rate == "slow" else "160"
        result = subprocess.run(
            ["espeak-ng", "-v", voice, "-s", speed, "--stdout", word],
            capture_output=True, timeout=10
        )
        if result.returncode != 0:
            return None

        wav_data = result.stdout

        # Convert to MP3 via FFmpeg
        ffmpeg = subprocess.run(
            ["ffmpeg", "-y", "-i", "pipe:0",
             "-ar", "44100", "-ac", "1",
             "-filter:a", "loudnorm=I=-16:LRA=11:TP=-3",
             "-f", "mp3", "pipe:1"],
            input=wav_data, capture_output=True, timeout=10
        )
        if ffmpeg.returncode != 0:
            return None

        return ffmpeg.stdout

    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate TTS audio files.")
    parser.add_argument("--data-dir", type=Path, default=DATA_WORDS_DIR,
                        help="Path to data/words directory")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Audio output directory (default: audio/ in data dir parent)")
    parser.add_argument("--regions", default="us,uk,ca,au",
                        help="Comma-separated regions to generate")
    parser.add_argument("--backend", default=None,
                        help="Force backend: google, azure, or espeak")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit to N words (0 = no limit)")
    args = parser.parse_args(argv)

    regions = [r.strip().upper() for r in args.regions.split(",")]
    data_dir = args.data_dir
    audio_dir = args.output_dir or data_dir.parent.parent / "audio"

    # Find all word JSON files
    word_files = sorted(data_dir.rglob("*.json"))
    if args.limit > 0:
        word_files = word_files[:args.limit]

    print(f"Word files: {len(word_files)}")
    print(f"Regions: {regions}")
    print(f"Audio output: {audio_dir}")

    # Initialize TTS clients
    google_client = None
    azure_config = None

    if args.backend != "espeak":
        if any(r in ("US", "UK", "AU") for r in regions):
            google_client = get_google_tts_client()
        if "CA" in regions:
            azure_config = get_azure_tts_config()

    # Set up cache
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    generated = 0
    cached = 0
    failed = 0

    for filepath in tqdm(word_files, desc="Audio"):
        with open(filepath) as f:
            try:
                entry = json.load(f)
            except json.JSONDecodeError:
                continue

        word = entry.get("word", "")
        slug = entry.get("slug", "")

        for variant in entry.get("variants", []):
            region = variant.get("region", "")
            if region not in regions:
                continue

            ipa = variant.get("ipa", "")
            voice_config = TTS_VOICES.get(region, {})
            backend = args.backend or voice_config.get("backend", "espeak")
            voice_name = voice_config.get("voice", "")
            lang_code = voice_config.get("language_code", "")

            for speed in ("normal", "slow"):
                # Check cache
                cache_key = content_hash(word, region, ipa, backend, voice_name)
                cache_path = AUDIO_CACHE_DIR / f"{cache_key}_{speed}.mp3"

                if cache_path.exists():
                    cached += 1
                    continue

                # Synthesize
                audio_data = None

                if backend == "google" and google_client:
                    audio_data = synthesize_google(
                        google_client, word, voice_name, lang_code,
                        rate=speed
                    )
                elif backend == "azure" and azure_config:
                    audio_data = synthesize_azure(
                        azure_config, word, voice_name, rate=speed
                    )

                # Fallback to eSpeak
                if audio_data is None:
                    espeak_voice = {"US": "en-us", "UK": "en-gb",
                                    "AU": "en-au", "CA": "en-us"}.get(region, "en-us")
                    audio_data = synthesize_espeak(word, espeak_voice, speed)

                if audio_data:
                    # Write to cache
                    cache_path.write_bytes(audio_data)

                    # Write to output directory
                    region_dir = audio_dir / region.lower()
                    region_dir.mkdir(parents=True, exist_ok=True)
                    out_path = region_dir / f"{slug}_{speed}.mp3"
                    out_path.write_bytes(audio_data)

                    generated += 1
                else:
                    failed += 1

    print(f"\n{'='*60}")
    print(f"Generated: {generated}")
    print(f"From cache: {cached}")
    print(f"Failed: {failed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
