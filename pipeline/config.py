"""Pipeline configuration: paths, constants, source URLs, phoneme mappings."""

from pathlib import Path

# ── Directory layout ──────────────────────────────────────────────────────────
PIPELINE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PIPELINE_DIR.parent
SOURCES_DIR = PIPELINE_DIR / "sources"
DB_PATH = PIPELINE_DIR / "staging.db"
AUDIO_CACHE_DIR = PIPELINE_DIR / "audio_cache"

# Data repo — sibling directory
DATA_REPO_DIR = PROJECT_DIR.parent / "pronounce-how-data"
DATA_WORDS_DIR = DATA_REPO_DIR / "data" / "words"
SCHEMA_PATH = DATA_REPO_DIR / "schema" / "word.schema.json"

# ── Download URLs ─────────────────────────────────────────────────────────────
SOURCE_URLS = {
    "cmudict.dict": (
        "https://raw.githubusercontent.com/cmusphinx/cmudict/master/cmudict.dict"
    ),
    "cmudict-0.7b-ipa.txt": (
        "https://raw.githubusercontent.com/menelik3/cmudict-ipa/master/cmudict-0.7b-ipa.txt"
    ),
    "brown-frequency-list-with-ipa.txt": (
        "https://raw.githubusercontent.com/menelik3/cmudict-ipa/master/brown-frequency-list-with-ipa.txt"
    ),
    "britfone.main.3.0.1.csv": (
        "https://raw.githubusercontent.com/JoseLlarena/Britfone/master/britfone.main.3.0.1.csv"
    ),
    "kaikki.org-dictionary-English.jsonl": (
        "https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl"
    ),
}

# ── 10 hand-crafted sample slugs (never overwritten by pipeline) ─────────────
EXCLUDED_SLUGS = frozenset([
    "aluminum", "caramel", "data", "gyrfalcon", "herb",
    "lieutenant", "process", "route", "schedule", "tomato",
])

# ── ARPAbet phoneme inventory (CMU Dict standard, 39 phonemes) ────────────────
ARPABET_VOWELS = frozenset([
    "AA", "AE", "AH", "AO", "AW", "AY",
    "EH", "ER", "EY",
    "IH", "IY",
    "OW", "OY",
    "UH", "UW",
])

ARPABET_CONSONANTS = frozenset([
    "B", "CH", "D", "DH", "F", "G", "HH", "JH",
    "K", "L", "M", "N", "NG", "P", "R", "S", "SH",
    "T", "TH", "V", "W", "Y", "Z", "ZH",
])

ARPABET_ALL = ARPABET_VOWELS | ARPABET_CONSONANTS

# ── IPA ↔ ARPAbet mapping ────────────────────────────────────────────────────
# IPA → ARPAbet (base, without stress digits on vowels)
IPA_TO_ARPABET = {
    # Vowels
    "ɑ": "AA", "ɑː": "AA",
    "æ": "AE",
    "ʌ": "AH", "ə": "AH",
    "ɔ": "AO", "ɔː": "AO",
    "aʊ": "AW",
    "aɪ": "AY",
    "ɛ": "EH", "e": "EH",
    "ɜː": "ER", "ɜːr": "ER", "ɝ": "ER", "ɚ": "ER", "ɜ": "ER",
    "eɪ": "EY",
    "ɪ": "IH",
    "iː": "IY", "i": "IY",
    "oʊ": "OW", "əʊ": "OW", "o": "OW",
    "ɔɪ": "OY",
    "ʊ": "UH",
    "uː": "UW", "u": "UW",
    # UK-specific
    "ɒ": "AA",  # CLOTH/LOT vowel → AA in ARPAbet
    # Consonants
    "b": "B",
    "tʃ": "CH",
    "d": "D",
    "ð": "DH",
    "f": "F",
    "ɡ": "G", "g": "G",
    "h": "HH",
    "dʒ": "JH",
    "k": "K",
    "l": "L",
    "m": "M",
    "n": "N",
    "ŋ": "NG",
    "p": "P",
    "ɹ": "R", "r": "R",
    "s": "S",
    "ʃ": "SH",
    "t": "T",
    "θ": "TH",
    "v": "V",
    "w": "W",
    "j": "Y",
    "z": "Z",
    "ʒ": "ZH",
}

# ARPAbet → IPA (canonical direction, for display)
ARPABET_TO_IPA = {
    "AA": "ɑː", "AE": "æ", "AH": "ə", "AO": "ɔː",
    "AW": "aʊ", "AY": "aɪ", "EH": "ɛ", "ER": "ɜːr",
    "EY": "eɪ", "IH": "ɪ", "IY": "iː", "OW": "oʊ",
    "OY": "ɔɪ", "UH": "ʊ", "UW": "uː",
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð",
    "F": "f", "G": "ɡ", "HH": "h", "JH": "dʒ",
    "K": "k", "L": "l", "M": "m", "N": "n",
    "NG": "ŋ", "P": "p", "R": "r", "S": "s",
    "SH": "ʃ", "T": "t", "TH": "θ", "V": "v",
    "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}

# ── IPA-to-Respelling table ───────────────────────────────────────────────────
IPA_TO_RESPELLING = {
    "æ": "a", "eɪ": "ay", "ɑː": "ah", "ɑ": "ah",
    "ɛ": "eh", "e": "eh",
    "iː": "ee", "i": "ee",
    "ɪ": "i",
    "oʊ": "oh", "əʊ": "oh", "o": "oh",
    "uː": "oo", "u": "oo",
    "ʌ": "uh", "ə": "uh",
    "aɪ": "eye", "aʊ": "ow", "ɔɪ": "oy",
    "ɔː": "aw", "ɔ": "aw",
    "ɜːr": "ur", "ɜː": "ur", "ɝ": "ur", "ɚ": "ur",
    "ʊ": "uu",
    "ɒ": "o",
    # Consonants (only non-obvious mappings)
    "dʒ": "j", "tʃ": "ch", "ʃ": "sh", "θ": "th", "ð": "th",
    "ŋ": "ng", "ʒ": "zh",
    "b": "b", "d": "d", "f": "f", "ɡ": "g", "g": "g",
    "h": "h", "k": "k", "l": "l", "m": "m", "n": "n",
    "p": "p", "ɹ": "r", "r": "r", "s": "s", "t": "t",
    "v": "v", "w": "w", "j": "y", "z": "z",
}

# ── Region → TTS voice mapping ───────────────────────────────────────────────
TTS_VOICES = {
    "US": {
        "backend": "google",
        "voice": "en-US-Neural2-J",
        "language_code": "en-US",
    },
    "UK": {
        "backend": "google",
        "voice": "en-GB-Neural2-B",
        "language_code": "en-GB",
    },
    "AU": {
        "backend": "google",
        "voice": "en-AU-Neural2-A",
        "language_code": "en-AU",
    },
    "CA": {
        "backend": "azure",
        "voice": "en-CA-LiamNeural",
        "language_code": "en-CA",
    },
}

# ── Region → eSpeak voice codes ──────────────────────────────────────────────
ESPEAK_VOICES = {
    "US": "en-us",
    "UK": "en-gb",
    "AU": "en-au",
    "CA": "en-us",  # eSpeak has no en-ca; use US as base
}

# ── POS mapping (Wiktextract → schema enum) ──────────────────────────────────
WIKT_POS_MAP = {
    "noun": "noun",
    "verb": "verb",
    "adj": "adjective",
    "adv": "adverb",
    "prep": "preposition",
    "conj": "conjunction",
    "intj": "interjection",
    "pron": "pronoun",
    "det": "determiner",
    "name": "noun",        # proper nouns → noun
    "num": "other",
    "particle": "other",
    "phrase": "other",
    "prefix": "other",
    "suffix": "other",
    "infix": "other",
    "abbrev": "other",
    "affix": "other",
    "character": "other",
    "symbol": "other",
}

# ── Canadian English rules ────────────────────────────────────────────────────
# Voiceless consonants that trigger Canadian raising
CA_VOICELESS = frozenset(["p", "t", "k", "f", "θ", "s", "ʃ", "tʃ"])

# Lexical overrides: words where CA pronunciation differs from US
CA_LEXICAL_OVERRIDES = {
    "sorry": {"us_ipa": "sɑːri", "ca_ipa": "sɔːri"},
    "process": {"us_ipa": "prɑːsɛs", "ca_ipa": "proʊsɛs"},
    "been": {"us_ipa": "bɪn", "ca_ipa": "biːn"},
    "pasta": {"us_ipa": "pɑːstə", "ca_ipa": "pæstə"},
    "drama": {"us_ipa": "drɑːmə", "ca_ipa": "dræmə"},
    "llama": {"us_ipa": "lɑːmə", "ca_ipa": "læmə"},
    "lava": {"us_ipa": "lɑːvə", "ca_ipa": "lævə"},
    "mazda": {"us_ipa": "mɑːzdə", "ca_ipa": "mæzdə"},
    "saga": {"us_ipa": "sɑːɡə", "ca_ipa": "sæɡə"},
    "plaza": {"us_ipa": "plɑːzə", "ca_ipa": "plæzə"},
    "baga": {"us_ipa": "bɑːɡə", "ca_ipa": "bæɡə"},
    "about": {"us_ipa": "əbaʊt", "ca_ipa": "əbʌʊt"},
    "out": {"us_ipa": "aʊt", "ca_ipa": "ʌʊt"},
    "house": {"us_ipa": "haʊs", "ca_ipa": "hʌʊs"},
    "couch": {"us_ipa": "kaʊtʃ", "ca_ipa": "kʌʊtʃ"},
    "shout": {"us_ipa": "ʃaʊt", "ca_ipa": "ʃʌʊt"},
    "project": {"us_ipa": "prɑːdʒɛkt", "ca_ipa": "proʊdʒɛkt"},
    "progress": {"us_ipa": "prɑːɡrɛs", "ca_ipa": "proʊɡrɛs"},
    "produce": {"us_ipa": "prɑːduːs", "ca_ipa": "proʊduːs"},
    "against": {"us_ipa": "əɡɛnst", "ca_ipa": "əɡeɪnst"},
    "again": {"us_ipa": "əɡɛn", "ca_ipa": "əɡeɪn"},
    "vase": {"us_ipa": "veɪs", "ca_ipa": "vɑːz"},
    "lever": {"us_ipa": "lɛvər", "ca_ipa": "liːvər"},
    "z": {"us_ipa": "ziː", "ca_ipa": "zɛd"},
    "lieutenant": {"us_ipa": "luːtɛnənt", "ca_ipa": "luːtɛnənt"},
}
