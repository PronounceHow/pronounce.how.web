"""IPA segmentation, normalization, and ARPAbet conversion utilities."""

import re
from .config import IPA_TO_ARPABET, ARPABET_TO_IPA, IPA_TO_RESPELLING, ARPABET_VOWELS

# Build ordered IPA phoneme list for greedy matching (longest first)
_IPA_PHONEMES_ORDERED = sorted(IPA_TO_ARPABET.keys(), key=len, reverse=True)
_IPA_RESPELL_ORDERED = sorted(IPA_TO_RESPELLING.keys(), key=len, reverse=True)

# Stress markers in IPA
_STRESS_MARKERS = {"ˈ", "ˌ"}


def segment_ipa(ipa_string):
    """Greedy longest-match segmentation of an IPA string.

    Returns a list of IPA segments (phonemes + stress markers).
    Strips leading/trailing slashes and syllable dots.

    >>> segment_ipa("/ˈskɛdʒuːl/")
    ['ˈ', 's', 'k', 'ɛ', 'dʒ', 'uː', 'l']
    """
    # Strip slashes
    s = ipa_string.strip("/")
    # Remove syllable boundary markers
    s = s.replace(".", "")

    segments = []
    i = 0
    while i < len(s):
        # Check stress markers
        if s[i] in _STRESS_MARKERS:
            segments.append(s[i])
            i += 1
            continue

        # Skip whitespace
        if s[i].isspace():
            i += 1
            continue

        # Greedy longest match
        matched = False
        for phoneme in _IPA_PHONEMES_ORDERED:
            if s[i:i+len(phoneme)] == phoneme:
                segments.append(phoneme)
                i += len(phoneme)
                matched = True
                break

        if not matched:
            # Unknown character — include as-is
            segments.append(s[i])
            i += 1

    return segments


def ipa_to_arpabet(ipa_string, stress_from_ipa=True):
    """Convert an IPA string to a list of ARPAbet tokens.

    If stress_from_ipa is True, maps ˈ → 1, ˌ → 2, and applies stress
    digits to the next vowel. Unstressed vowels get 0.

    >>> ipa_to_arpabet("/ˈskɛdʒuːl/")
    ['S', 'K', 'EH1', 'JH', 'UW0', 'L']
    """
    segments = segment_ipa(ipa_string)

    # First pass: convert to base ARPAbet, tracking stress
    tokens = []
    pending_stress = None  # None, 1 (primary), or 2 (secondary)

    for seg in segments:
        if seg == "ˈ":
            pending_stress = 1
            continue
        elif seg == "ˌ":
            pending_stress = 2
            continue

        arpa = IPA_TO_ARPABET.get(seg)
        if arpa is None:
            continue  # Skip unknown segments

        if arpa in ARPABET_VOWELS:
            if stress_from_ipa and pending_stress is not None:
                tokens.append(f"{arpa}{pending_stress}")
                pending_stress = None
            elif stress_from_ipa:
                tokens.append(f"{arpa}0")
            else:
                tokens.append(f"{arpa}0")
        else:
            tokens.append(arpa)

    return tokens


def arpabet_to_ipa(arpabet_tokens):
    """Convert ARPAbet tokens back to an IPA string.

    >>> arpabet_to_ipa(["S", "K", "EH1", "JH", "UW0", "L"])
    'ˈskɛdʒuːl'
    """
    ipa_parts = []
    for token in arpabet_tokens:
        # Strip stress digit
        base = re.sub(r"[012]$", "", token)
        stress_digit = token[-1] if token[-1] in "012" else None

        ipa_seg = ARPABET_TO_IPA.get(base, "")
        if not ipa_seg:
            continue

        # Add stress marker before the vowel
        if stress_digit == "1":
            ipa_parts.append("ˈ" + ipa_seg)
        elif stress_digit == "2":
            ipa_parts.append("ˌ" + ipa_seg)
        else:
            ipa_parts.append(ipa_seg)

    return "".join(ipa_parts)


def normalize_ipa(ipa_string):
    """Strip stress markers and length marks for cross-source comparison.

    >>> normalize_ipa("/ˈskɛdʒuːl/")
    'skɛdʒul'
    """
    s = ipa_string.strip("/")
    s = s.replace("ˈ", "").replace("ˌ", "")
    s = s.replace("ː", "").replace("ˑ", "")
    s = s.replace(".", "")
    return s


def ipa_to_respelling(ipa_string, syllable_boundaries=None):
    """Convert IPA to human-readable respelling.

    If syllable_boundaries is provided (list of IPA strings per syllable),
    produces hyphen-separated syllables with stressed ones in CAPS.

    Otherwise, produces a flat respelling of the full IPA string.

    >>> ipa_to_respelling("/ˈskɛdʒuːl/")
    'SKEJ-ool'
    """
    if syllable_boundaries:
        parts = []
        for syl_ipa, stress in syllable_boundaries:
            text = _respell_segment(syl_ipa)
            if stress == "primary":
                text = text.upper()
            parts.append(text)
        return "-".join(parts)

    # Flat mode
    s = ipa_string.strip("/")

    # Track stress
    syllables_with_stress = []
    current = ""
    current_stress = "unstressed"

    i = 0
    while i < len(s):
        if s[i] == "ˈ":
            if current:
                syllables_with_stress.append((current, current_stress))
                current = ""
            current_stress = "primary"
            i += 1
        elif s[i] == "ˌ":
            if current:
                syllables_with_stress.append((current, current_stress))
                current = ""
            current_stress = "secondary"
            i += 1
        elif s[i] == ".":
            if current:
                syllables_with_stress.append((current, current_stress))
                current = ""
                current_stress = "unstressed"
            i += 1
        else:
            current += s[i]
            i += 1

    if current:
        syllables_with_stress.append((current, current_stress))

    parts = []
    for seg, stress in syllables_with_stress:
        text = _respell_segment(seg)
        if stress == "primary":
            text = text.upper()
        parts.append(text)

    return "-".join(parts) if len(parts) > 1 else (parts[0] if parts else "")


def _respell_segment(ipa_seg):
    """Convert a segment of IPA (no stress markers) to respelling text."""
    result = []
    i = 0
    s = ipa_seg.replace("ː", "").replace("ˑ", "")  # strip length marks

    while i < len(s):
        matched = False
        for phoneme in _IPA_RESPELL_ORDERED:
            if s[i:i+len(phoneme)] == phoneme:
                result.append(IPA_TO_RESPELLING[phoneme])
                i += len(phoneme)
                matched = True
                break
        if not matched:
            result.append(s[i])
            i += 1

    return "".join(result)


def parse_arpabet_string(arpabet_str):
    """Parse a space-separated ARPAbet string into token list.

    >>> parse_arpabet_string("S K EH1 JH UW0 L")
    ['S', 'K', 'EH1', 'JH', 'UW0', 'L']
    """
    return arpabet_str.strip().split()


def is_vowel_token(token):
    """Check if an ARPAbet token is a vowel (with or without stress digit)."""
    base = re.sub(r"[012]$", "", token)
    return base in ARPABET_VOWELS


def get_stress_from_arpabet(tokens):
    """Extract stress pattern from ARPAbet tokens.

    Returns list of stress levels per vowel: 'primary', 'secondary', 'unstressed'.
    """
    stresses = []
    for token in tokens:
        if not is_vowel_token(token):
            continue
        digit = token[-1] if token[-1] in "012" else "0"
        if digit == "1":
            stresses.append("primary")
        elif digit == "2":
            stresses.append("secondary")
        else:
            stresses.append("unstressed")
    return stresses
