"""pronounceHow pronunciation pipeline.

Modules:
- config: Paths, constants, source URLs, phoneme mappings
- db: SQLite staging database schema and helpers
- ipa_utils: IPA segmentation, normalization, ARPAbet conversion
- download_sources: Fetch raw data files
- ingest_cmudict: Import CMU Pronouncing Dictionary
- ingest_britfone: Import Britfone UK pronunciation data
- ingest_wiktextract: Import Wiktextract pronunciation data
- build_word_list: Determine target word set
- ingest_espeak: Generate AU variants + gap-fill via eSpeak NG
- apply_ca_rules: Generate CA variants from US base
- syllabify: Break phoneme sequences into syllables with stress
- generate_respelling: Generate human-readable respellings
- merge_sources: Cross-validate and merge pronunciation data
- export: Export validated data to final JSON format
- build_audio: Generate TTS audio files
- viseme_map: Phoneme-to-viseme mapping and keyframe generation
- build_video: Generate pronunciation videos (YouTube Shorts format)
- upload_youtube: Upload videos to YouTube with SEO metadata and playlist management
"""
