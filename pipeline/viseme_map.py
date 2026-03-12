"""Phoneme-to-viseme mapping and keyframe generation.

Viseme set based on Rhubarb's Preston Blair shapes:
  A = Closed lips (P, B, M)
  B = Slightly open, teeth visible (most consonants)
  C = Open (EH, AE, AH)
  D = Wide open (AA, AY, AW)
  E = Slightly rounded (AO, ER, OY)
  F = Puckered (UW, OW, W)
  G = Teeth on lip (F, V)
  H = Tongue visible (L)
  X = Idle/silence
"""

import re
from .config import ARPABET_VOWELS

# ARPAbet phoneme → viseme shape
PHONEME_TO_VISEME = {
    # A: Closed lips
    "P": "A", "B": "A", "M": "A",
    # B: Slightly open, teeth visible
    "K": "B", "S": "B", "T": "B", "N": "B", "D": "B",
    "TH": "B", "DH": "B", "G": "B", "HH": "B", "NG": "B",
    "Z": "B", "ZH": "B", "SH": "B", "CH": "B", "JH": "B",
    "R": "B", "Y": "B",
    # C: Open
    "EH": "C", "AE": "C", "AH": "C", "IH": "C", "IY": "C",
    # D: Wide open
    "AA": "D", "AY": "D", "AW": "D",
    # E: Slightly rounded
    "AO": "E", "ER": "E", "OY": "E", "EY": "E",
    # F: Puckered
    "UW": "F", "OW": "F", "W": "F", "UH": "F",
    # G: Teeth on lip
    "F": "G", "V": "G",
    # H: Tongue visible
    "L": "H",
}

# Default duration per viseme in seconds (used when no timing data available)
DEFAULT_PHONEME_DURATIONS = {
    # Vowels tend to be longer
    "AA": 0.12, "AE": 0.11, "AH": 0.08, "AO": 0.12, "AW": 0.14,
    "AY": 0.14, "EH": 0.10, "ER": 0.12, "EY": 0.13, "IH": 0.08,
    "IY": 0.10, "OW": 0.13, "OY": 0.14, "UH": 0.08, "UW": 0.10,
    # Consonants are shorter
    "B": 0.06, "CH": 0.08, "D": 0.05, "DH": 0.05, "F": 0.07,
    "G": 0.06, "HH": 0.05, "JH": 0.08, "K": 0.06, "L": 0.06,
    "M": 0.07, "N": 0.05, "NG": 0.07, "P": 0.06, "R": 0.05,
    "S": 0.08, "SH": 0.08, "T": 0.05, "TH": 0.06, "V": 0.06,
    "W": 0.05, "Y": 0.04, "Z": 0.07, "ZH": 0.07,
}


def phoneme_base(token):
    """Strip stress digit from ARPAbet token."""
    return re.sub(r"[012]$", "", token)


def get_viseme(arpabet_token):
    """Map an ARPAbet token to a viseme shape."""
    base = phoneme_base(arpabet_token)
    return PHONEME_TO_VISEME.get(base, "X")


def generate_keyframes(arpabet_tokens, start_time=0.0, total_duration=None):
    """Generate viseme keyframes from ARPAbet tokens.

    Args:
        arpabet_tokens: List of ARPAbet tokens (e.g. ["S", "K", "EH1", "JH", "UW0", "L"])
        start_time: Offset in seconds
        total_duration: If provided, scale keyframes to fit this duration

    Returns:
        List of {"time": float, "viseme": str} dicts.
    """
    if not arpabet_tokens:
        return [{"time": start_time, "viseme": "X"}]

    # Calculate natural durations
    raw_keyframes = []
    t = 0.0

    for token in arpabet_tokens:
        base = phoneme_base(token)
        viseme = get_viseme(token)
        duration = DEFAULT_PHONEME_DURATIONS.get(base, 0.06)
        raw_keyframes.append({"time": t, "viseme": viseme, "duration": duration})
        t += duration

    natural_duration = t

    # Scale to fit total_duration if provided
    if total_duration and natural_duration > 0:
        scale = total_duration / natural_duration
    else:
        scale = 1.0

    # Build final keyframes with idle bookends
    keyframes = [{"time": start_time, "viseme": "X"}]

    for kf in raw_keyframes:
        keyframes.append({
            "time": round(start_time + kf["time"] * scale, 3),
            "viseme": kf["viseme"],
        })

    # End with idle
    end_time = start_time + natural_duration * scale
    keyframes.append({"time": round(end_time + 0.05, 3), "viseme": "X"})

    return keyframes


def generate_keyframes_from_timing(arpabet_tokens, timepoints):
    """Generate viseme keyframes using TTS timepoint data.

    Args:
        arpabet_tokens: List of ARPAbet tokens
        timepoints: List of {"time": float} dicts from TTS API

    Returns:
        List of {"time": float, "viseme": str} dicts.
    """
    keyframes = [{"time": 0.0, "viseme": "X"}]

    for i, token in enumerate(arpabet_tokens):
        viseme = get_viseme(token)
        if i < len(timepoints):
            t = timepoints[i].get("time", i * 0.08)
        else:
            t = i * 0.08
        keyframes.append({"time": round(t, 3), "viseme": viseme})

    # End with idle
    if keyframes:
        last_time = keyframes[-1]["time"]
        keyframes.append({"time": round(last_time + 0.15, 3), "viseme": "X"})

    return keyframes
