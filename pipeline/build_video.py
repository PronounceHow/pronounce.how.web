#!/usr/bin/env python3
"""Generate pronunciation videos (YouTube Shorts format).

Warm, animated design with a cute face character, gradient backgrounds,
smooth easing transitions, and playful motion.

Output: 1080x1920 vertical MP4, 30fps, H.264 + AAC

Usage:
    python -m pipeline.build_video --word schedule
    python -m pipeline.build_video --data-dir ../pronounce-how-data/data/words --limit 10
    python -m pipeline.build_video --word schedule --no-audio
"""

import argparse
import json
import math
import multiprocessing
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .config import DATA_WORDS_DIR
from .viseme_map import generate_keyframes, get_viseme, phoneme_base

# ── Dimensions ───────────────────────────────────────────────────────────────
WIDTH = 1080
HEIGHT = 1920
FPS = 30

# ── Warm color palette ───────────────────────────────────────────────────────
BG_TOP = (30, 15, 50)
BG_BOTTOM = (12, 20, 45)
TEXT_COLOR = (255, 248, 240)
ACCENT_CORAL = (255, 112, 100)
ACCENT_GOLD = (255, 210, 60)
ACCENT_TEAL = (72, 210, 155)
ACCENT_SKY = (100, 175, 255)
ACCENT_PURPLE = (175, 130, 255)
MUTED_COLOR = (160, 150, 180)
CARD_BG_RGB = (40, 28, 65)
HIGHLIGHT_COLOR = (255, 220, 80)

# Face colors
FACE_FILL = (255, 218, 185)
FACE_OUTLINE = (230, 185, 150)
CHEEK_COLOR = (255, 155, 135)
EYE_DARK = (45, 35, 55)
EYE_SHINE = (255, 255, 255)
LIP_COLOR = (230, 120, 110)
MOUTH_INSIDE = (100, 40, 50)
TEETH_COLOR = (245, 240, 235)
TONGUE_COLOR = (210, 110, 105)

# Region config
REGION_INFO = {
    "US": {"label": "American English", "color": ACCENT_SKY},
    "UK": {"label": "British English", "color": ACCENT_CORAL},
    "CA": {"label": "Canadian English", "color": ACCENT_GOLD},
    "AU": {"label": "Australian English", "color": ACCENT_TEAL},
}
REGION_ORDER = {"US": 0, "UK": 1, "CA": 2, "AU": 3}


# ── Sprite caches ─────────────────────────────────────────────────────────────

class FaceSpriteCache:
    """Pre-rendered face sprites keyed by (radius, viseme, is_blinking).

    Eliminates per-frame GaussianBlur by rendering all 54 face states
    (9 visemes x 2 blink states x 3 sizes) once at init on small images.
    """

    VISEMES = ("X", "A", "B", "C", "D", "E", "F", "G", "H")
    RADII = (100, 120, 145)
    MARGIN = 50  # extra pixels for cheek blur bleed

    def __init__(self):
        self._cache = {}
        self.glow_sprites = {}
        self._build_faces()
        self._build_glows()

    def _build_faces(self):
        for r in self.RADII:
            for viseme in self.VISEMES:
                for is_blinking in (False, True):
                    key = (r, viseme, is_blinking)
                    self._cache[key] = self._render_face(r, viseme, is_blinking)

    def _build_glows(self):
        """Pre-render glow sprites for each region color."""
        glow_r = 145 + 35  # face_r + 35
        margin = 60
        size = 2 * (glow_r + margin)
        for region, info in REGION_INFO.items():
            color = info["color"][:3]
            glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            c = size // 2
            gd.ellipse([(c - glow_r, c - glow_r), (c + glow_r, c + glow_r)],
                       fill=(*color, 25))
            glow = glow.filter(ImageFilter.GaussianBlur(radius=20))
            self.glow_sprites[region] = glow

    def _render_face(self, r, viseme, is_blinking):
        """Render a single face state as a small RGBA sprite."""
        m = self.MARGIN
        size = 2 * (r + m)
        cx, cy = size // 2, size // 2
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Face circle
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)],
                     fill=FACE_FILL, outline=FACE_OUTLINE, width=3)

        # Eyes
        eye_y = cy - int(r * 0.18)
        eye_spacing = int(r * 0.38)
        eye_rx = int(r * 0.13)
        eye_ry = int(r * 0.16)

        for side in [-1, 1]:
            ex = cx + side * eye_spacing
            if is_blinking:
                draw.arc([(ex - eye_rx, eye_y - eye_ry // 3),
                          (ex + eye_rx, eye_y + eye_ry // 3)],
                         0, 180, fill=EYE_DARK, width=4)
            else:
                draw.ellipse([(ex - eye_rx, eye_y - eye_ry),
                              (ex + eye_rx, eye_y + eye_ry)],
                             fill=EYE_DARK)
                hx = ex + int(eye_rx * 0.3)
                hy = eye_y - int(eye_ry * 0.35)
                hr = max(2, int(eye_rx * 0.28))
                draw.ellipse([(hx - hr, hy - hr), (hx + hr, hy + hr)],
                             fill=EYE_SHINE)

        # Cheeks (blur on small sprite — the key optimization)
        cheek_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        cd = ImageDraw.Draw(cheek_layer)
        cheek_y = cy + int(r * 0.08)
        cheek_spacing = int(r * 0.52)
        cheek_r = int(r * 0.14)

        for side in [-1, 1]:
            chx = cx + side * cheek_spacing
            cd.ellipse([(chx - cheek_r, cheek_y - cheek_r),
                         (chx + cheek_r, cheek_y + cheek_r)],
                        fill=(*CHEEK_COLOR[:3], 70))

        cheek_layer = cheek_layer.filter(ImageFilter.GaussianBlur(radius=8))
        img = Image.alpha_composite(img, cheek_layer)

        # Mouth
        draw = ImageDraw.Draw(img)
        mouth_cy = cy + int(r * 0.32)
        _draw_mouth(draw, cx, mouth_cy, r, viseme)

        return img

    def paste_face(self, target, cx, cy, face_radius, viseme, frame_num):
        """Paste the appropriate face sprite onto target image."""
        is_blinking = (frame_num % 90) >= 85
        key = (face_radius, viseme, is_blinking)
        sprite = self._cache.get(key)
        if sprite is None:
            draw_face(target, cx, cy, face_radius, viseme, frame_num)
            return
        half = face_radius + self.MARGIN
        target.paste(sprite, (cx - half, cy - half), sprite)

    def paste_glow(self, target, cx, cy, region):
        """Paste a pre-rendered glow sprite centered at (cx, cy)."""
        sprite = self.glow_sprites.get(region)
        if sprite is None:
            return
        half = sprite.size[0] // 2
        target.paste(sprite, (cx - half, cy - half), sprite)


# ── Easing & math utilities ─────────────────────────────────────────────────

def ease_out_cubic(t):
    return 1.0 - (1.0 - t) ** 3


def ease_out_back(t):
    c1 = 1.70158
    c3 = c1 + 1
    return 1.0 + c3 * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2


def ease_in_out_sine(t):
    return -(math.cos(math.pi * t) - 1.0) / 2.0


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def stagger(progress, delay, duration=0.35):
    return clamp((progress - delay) / max(duration, 0.001))


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    n = min(len(c1), len(c2))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(n))


# ── Drawing utilities ────────────────────────────────────────────────────────

def create_gradient_bg():
    """Pre-compute the gradient background image (RGBA)."""
    img = Image.new("RGBA", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b, 255))
    return img


def draw_pill_badge(draw, text, center_x, y, font, text_color, bg_color,
                    padding=(24, 8)):
    """Draw a pill-shaped badge centered at center_x."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = padding
    left = center_x - tw // 2 - px
    top = y - py
    right = center_x + tw // 2 + px
    bottom = y + th + py
    radius = (bottom - top) // 2
    draw.rounded_rectangle([(left, top), (right, bottom)],
                           radius=radius, fill=bg_color)
    draw.text((center_x - tw // 2, y), text, fill=text_color, font=font)
    return bottom


def tw(draw, text, font):
    """Text width shorthand."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def th(draw, text, font):
    """Text height shorthand."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


# ── Font loading ─────────────────────────────────────────────────────────────

def _find_font(names, size):
    """Try to load a font by name, fall back to default."""
    search_dirs = [
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        str(Path.home() / ".fonts"),
        str(Path.home() / ".local/share/fonts"),
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            pass
        for d in search_dirs:
            if not os.path.isdir(d):
                continue
            for root, _dirs, files in os.walk(d):
                for f in files:
                    if name.lower() in f.lower() and f.endswith((".ttf", ".otf")):
                        try:
                            return ImageFont.truetype(os.path.join(root, f), size)
                        except (OSError, IOError):
                            pass
    return ImageFont.load_default()


def get_fonts():
    """Load fonts for video rendering."""
    bold = ["NotoSans-Bold", "DejaVuSans-Bold"]
    regular = ["NotoSans-Regular", "DejaVuSans"]
    return {
        "title": _find_font(bold, 78),
        "word_large": _find_font(bold, 96),
        "subtitle": _find_font(regular, 44),
        "ipa": _find_font(regular, 50),
        "respelling": _find_font(bold, 46),
        "syllable": _find_font(regular, 54),
        "label": _find_font(regular, 38),
        "small": _find_font(regular, 30),
        "brand": _find_font(bold, 34),
        "big_label": _find_font(bold, 42),
    }


# ── Face character ───────────────────────────────────────────────────────────

def draw_face(img, cx, cy, face_radius, viseme, frame_num=0):
    """Draw a cute face character with eyes, cheeks, and animated mouth.

    Modifies img in-place via paste and returns it.
    Kept as fallback — prefer FaceSpriteCache.paste_face() in hot paths.
    """
    draw = ImageDraw.Draw(img)
    r = face_radius

    # Face circle
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)],
                 fill=FACE_FILL, outline=FACE_OUTLINE, width=3)

    # Eyes
    eye_y = cy - int(r * 0.18)
    eye_spacing = int(r * 0.38)
    eye_rx = int(r * 0.13)
    eye_ry = int(r * 0.16)

    blink_cycle = frame_num % 90
    is_blinking = blink_cycle >= 85

    for side in [-1, 1]:
        ex = cx + side * eye_spacing
        if is_blinking:
            draw.arc([(ex - eye_rx, eye_y - eye_ry // 3),
                      (ex + eye_rx, eye_y + eye_ry // 3)],
                     0, 180, fill=EYE_DARK, width=4)
        else:
            draw.ellipse([(ex - eye_rx, eye_y - eye_ry),
                          (ex + eye_rx, eye_y + eye_ry)],
                         fill=EYE_DARK)
            hx = ex + int(eye_rx * 0.3)
            hy = eye_y - int(eye_ry * 0.35)
            hr = max(2, int(eye_rx * 0.28))
            draw.ellipse([(hx - hr, hy - hr), (hx + hr, hy + hr)],
                         fill=EYE_SHINE)

    # Cheeks (blurred blush)
    cheek_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(cheek_layer)
    cheek_y = cy + int(r * 0.08)
    cheek_spacing = int(r * 0.52)
    cheek_r = int(r * 0.14)

    for side in [-1, 1]:
        chx = cx + side * cheek_spacing
        cd.ellipse([(chx - cheek_r, cheek_y - cheek_r),
                     (chx + cheek_r, cheek_y + cheek_r)],
                    fill=(*CHEEK_COLOR[:3], 70))

    cheek_layer = cheek_layer.filter(ImageFilter.GaussianBlur(radius=8))
    result = Image.alpha_composite(img, cheek_layer)
    img.paste(result)
    draw = ImageDraw.Draw(img)

    # Mouth
    mouth_cy = cy + int(r * 0.32)
    _draw_mouth(draw, cx, mouth_cy, face_radius, viseme)

    return img


def _draw_mouth(draw, cx, cy, face_r, viseme):
    """Draw the mouth shape on the face."""
    s = face_r / 160.0  # scale factor

    if viseme == "X":
        # Idle: gentle smile
        pts = []
        for i in range(21):
            t = i / 20.0
            x = cx + (t - 0.5) * 50 * s
            y = cy + math.sin(t * math.pi) * 8 * s
            pts.append((x, y))
        draw.line(pts, fill=LIP_COLOR, width=max(3, int(3 * s)))

    elif viseme == "A":
        w = int(45 * s)
        draw.line([(cx - w, cy), (cx + w, cy)],
                  fill=LIP_COLOR, width=max(4, int(4 * s)))
        draw.arc([(cx - w, int(cy - 6 * s)), (cx + w, int(cy + 4 * s))],
                 180, 360, fill=LIP_COLOR, width=max(3, int(3 * s)))

    elif viseme == "B":
        w, h = int(40 * s), int(14 * s)
        draw.ellipse([(cx - w, cy - h), (cx + w, cy + h)], fill=MOUTH_INSIDE)
        draw.ellipse([(cx - w, cy - h), (cx + w, cy + h)],
                     outline=LIP_COLOR, width=max(3, int(3 * s)))
        draw.line([(int(cx - w * 0.7), int(cy - h * 0.2)),
                   (int(cx + w * 0.7), int(cy - h * 0.2))],
                  fill=TEETH_COLOR, width=max(2, int(2 * s)))

    elif viseme == "C":
        w, h = int(42 * s), int(28 * s)
        draw.ellipse([(cx - w, cy - h), (cx + w, cy + h)], fill=MOUTH_INSIDE)
        draw.ellipse([(cx - w, cy - h), (cx + w, cy + h)],
                     outline=LIP_COLOR, width=max(3, int(3 * s)))
        draw.rectangle([(int(cx - w * 0.6), int(cy - h * 0.6)),
                        (int(cx + w * 0.6), int(cy - h * 0.2))],
                       fill=TEETH_COLOR)

    elif viseme == "D":
        w, h = int(46 * s), int(38 * s)
        draw.ellipse([(cx - w, cy - h), (cx + w, cy + h)], fill=MOUTH_INSIDE)
        draw.ellipse([(cx - w, cy - h), (cx + w, cy + h)],
                     outline=LIP_COLOR, width=max(3, int(3 * s)))
        draw.rectangle([(int(cx - w * 0.55), int(cy - h * 0.65)),
                        (int(cx + w * 0.55), int(cy - h * 0.3))],
                       fill=TEETH_COLOR)
        draw.chord([(int(cx - w * 0.4), int(cy + h * 0.15)),
                    (int(cx + w * 0.4), int(cy + h * 0.7))],
                   0, 180, fill=TONGUE_COLOR)

    elif viseme == "E":
        w, h = int(30 * s), int(26 * s)
        draw.ellipse([(cx - w, cy - h), (cx + w, cy + h)], fill=MOUTH_INSIDE)
        draw.ellipse([(cx - w, cy - h), (cx + w, cy + h)],
                     outline=LIP_COLOR, width=max(3, int(3 * s)))

    elif viseme == "F":
        w, h = int(18 * s), int(20 * s)
        draw.ellipse([(cx - w, cy - h), (cx + w, cy + h)], fill=MOUTH_INSIDE)
        draw.ellipse([(cx - w, cy - h), (cx + w, cy + h)],
                     outline=LIP_COLOR, width=max(4, int(4 * s)))

    elif viseme == "G":
        w, h = int(40 * s), int(18 * s)
        draw.ellipse([(cx - w, cy - h), (cx + w, cy + h)], fill=MOUTH_INSIDE)
        draw.ellipse([(cx - w, cy - h), (cx + w, cy + h)],
                     outline=LIP_COLOR, width=max(3, int(3 * s)))
        draw.rectangle([(int(cx - w * 0.5), int(cy - h * 0.5)),
                        (int(cx + w * 0.5), int(cy + h * 0.1))],
                       fill=TEETH_COLOR)

    elif viseme == "H":
        w, h = int(38 * s), int(22 * s)
        draw.ellipse([(cx - w, cy - h), (cx + w, cy + h)], fill=MOUTH_INSIDE)
        draw.ellipse([(cx - w, cy - h), (cx + w, cy + h)],
                     outline=LIP_COLOR, width=max(3, int(3 * s)))
        draw.chord([(int(cx - w * 0.35), int(cy - h * 0.1)),
                    (int(cx + w * 0.35), int(cy + h * 0.8))],
                   0, 180, fill=TONGUE_COLOR)


# ── Overlay helper ───────────────────────────────────────────────────────────

def _text_overlay(img, x, y, text, font, color_rgb, alpha):
    """Draw text with alpha onto an RGBA image. Returns new image."""
    a = int(alpha)
    if a >= 254:
        # Fast path: draw directly, no allocation needed
        draw = ImageDraw.Draw(img)
        draw.text((x, y), text, fill=(*color_rgb[:3], 255), font=font)
        return img
    if a <= 0:
        return img
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.text((x, y), text, fill=(*color_rgb[:3], a), font=font)
    return Image.alpha_composite(img, ov)


def _badge_overlay(img, text, center_x, y, font, text_color, bg_color,
                   padding=(24, 8)):
    """Draw a pill badge with alpha onto an RGBA image."""
    # Fast path: if both colors are fully opaque, draw directly
    if (len(text_color) < 4 or text_color[3] >= 254) and \
       (len(bg_color) < 4 or bg_color[3] >= 254):
        draw = ImageDraw.Draw(img)
        draw_pill_badge(draw, text, center_x, y, font, text_color, bg_color,
                        padding)
        return img
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    draw_pill_badge(od, text, center_x, y, font, text_color, bg_color,
                    padding)
    return Image.alpha_composite(img, ov)


# ── Frame renderers ──────────────────────────────────────────────────────────

def render_intro_frame(word, fonts, bg, progress, frame_num, *,
                       face_cache=None):
    """Render intro: word fades and bounces in, face peeks up."""
    img = bg.copy()
    draw = ImageDraw.Draw(img)

    # "How to Pronounce" slides down
    p1 = ease_out_cubic(stagger(progress, 0.05, 0.4))
    subtitle = "How to Pronounce"
    sw = tw(draw, subtitle, fonts["subtitle"])
    sub_y = int(lerp(680, 740, p1))
    img = _text_overlay(img, (WIDTH - sw) // 2, sub_y,
                        subtitle, fonts["subtitle"], MUTED_COLOR, p1 * 255)

    # Word bounces in from below
    draw = ImageDraw.Draw(img)
    p2 = ease_out_back(stagger(progress, 0.15, 0.5))
    ww = tw(draw, word, fonts["word_large"])
    word_y = int(lerp(910, 830, p2))
    img = _text_overlay(img, (WIDTH - ww) // 2, word_y,
                        word, fonts["word_large"], TEXT_COLOR, p2 * 255)

    # Face peeks up from bottom
    p3 = ease_out_cubic(stagger(progress, 0.3, 0.5))
    face_target_cy = 1100
    face_cy = int(lerp(HEIGHT + 120, face_target_cy, p3))
    if p3 > 0.01:
        if face_cache is not None:
            face_cache.paste_face(img, WIDTH // 2, face_cy, 120, "X", frame_num)
        else:
            draw_face(img, WIDTH // 2, face_cy, 120, "X", frame_num)

    # Floating decorative dots
    draw = ImageDraw.Draw(img)
    p4 = ease_in_out_sine((frame_num % 60) / 60.0)
    dot_colors = [ACCENT_CORAL, ACCENT_GOLD, ACCENT_TEAL, ACCENT_SKY,
                  ACCENT_PURPLE]
    for i in range(5):
        angle = (i * 72 + frame_num * 0.5) * math.pi / 180.0
        dist = 350 + i * 30
        px = int(WIDTH // 2 + math.cos(angle) * dist)
        py = int(500 + math.sin(angle) * dist * 0.5 + p4 * 15)
        dot_r = 4 + i % 3
        draw.ellipse([(px - dot_r, py - dot_r), (px + dot_r, py + dot_r)],
                     fill=(*dot_colors[i][:3], 40 + i * 15))

    # Brand
    p5 = ease_out_cubic(stagger(progress, 0.5, 0.4))
    brand = "https://pronounce.how"
    bw = tw(draw, brand, fonts["brand"])
    img = _text_overlay(img, (WIDTH - bw) // 2, HEIGHT - 410,
                        brand, fonts["brand"], MUTED_COLOR, p5 * 180)

    return img


def render_variant_frame(word, variant, fonts, bg, viseme, active_syl,
                         progress, frame_num, is_slow, show_entrance=True,
                         all_regions=None, *, face_cache=None):
    """Render a variant pronunciation frame."""
    img = bg.copy()
    draw = ImageDraw.Draw(img)

    region = variant.get("region", "US")
    info = REGION_INFO.get(region, REGION_INFO["US"])
    ipa = variant.get("ipa", "")
    respelling = variant.get("respelling", "")
    syllables = variant.get("syllables", [])
    derived_from = variant.get("derived_from")

    def anim(delay, dur=0.3):
        if not show_entrance:
            return 1.0
        return ease_out_cubic(stagger(progress, delay, dur))

    # Single shared overlay for all semi-transparent elements
    ov = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)

    y = 330

    # Word title (opaque → draw direct)
    p_w = anim(0.0)
    ww = tw(draw, word, fonts["title"])
    word_y = int(lerp(y - 30, y, p_w))
    a_w = int(p_w * 255)
    if a_w >= 254:
        draw.text(((WIDTH - ww) // 2, word_y), word,
                  fill=(*TEXT_COLOR[:3], 255), font=fonts["title"])
    elif a_w > 0:
        od.text(((WIDTH - ww) // 2, word_y), word,
                fill=(*TEXT_COLOR[:3], a_w), font=fonts["title"])
    y += 110

    # Region pill badge (semi-transparent bg → overlay)
    p_b = ease_out_back(stagger(progress, 0.08, 0.35)) if show_entrance else 1.0
    badge_y = int(lerp(y + 20, y, p_b))
    if p_b > 0.01:
        draw_pill_badge(od, info["label"], WIDTH // 2, badge_y, fonts["label"],
                        (*info["color"][:3], int(p_b * 255)),
                        (*info["color"][:3], int(p_b * 50)))
    y += 70

    # Derived badge (semi-transparent → overlay)
    if derived_from:
        p_d = anim(0.15)
        if p_d > 0.01:
            draw_pill_badge(od, f"Based on {derived_from} pronunciation",
                            WIDTH // 2, y, fonts["small"],
                            (*MUTED_COLOR, int(p_d * 200)),
                            (60, 50, 80, int(p_d * 150)))
        y += 50

    # IPA (opaque → draw direct)
    p_i = anim(0.12, 0.35)
    iw = tw(draw, ipa, fonts["ipa"])
    ipa_y = int(lerp(y + 25, y, p_i))
    a_i = int(p_i * 255)
    if a_i >= 254:
        draw.text(((WIDTH - iw) // 2, ipa_y), ipa,
                  fill=(*ACCENT_PURPLE[:3], 255), font=fonts["ipa"])
    elif a_i > 0:
        od.text(((WIDTH - iw) // 2, ipa_y), ipa,
                fill=(*ACCENT_PURPLE[:3], a_i), font=fonts["ipa"])
    y += 80

    # Syllables (has separator with alpha 180 → use overlay)
    if syllables:
        p_s = anim(0.18, 0.35)
        syl_texts = []
        for i, syl in enumerate(syllables):
            text = syl.get("text", "")
            stress = syl.get("stress", "unstressed")
            if stress == "primary":
                text = text.upper()
            syl_texts.append((text, stress, i))

        separator = "  ·  "
        full = separator.join(t for t, _, _ in syl_texts)
        total_w = tw(draw, full, fonts["syllable"])

        x = (WIDTH - total_w) // 2
        for j, (text, stress, idx) in enumerate(syl_texts):
            bounce = 0
            if idx == active_syl:
                bounce_t = (frame_num % 15) / 15.0
                bounce = int(math.sin(bounce_t * math.pi) * 8)
                color = (*HIGHLIGHT_COLOR[:3], int(p_s * 255))
            elif stress == "primary":
                color = (*TEXT_COLOR[:3], int(p_s * 255))
            else:
                color = (*MUTED_COLOR[:3], int(p_s * 255))

            od.text((x, y - bounce), text, fill=color, font=fonts["syllable"])
            x += tw(od, text, fonts["syllable"])

            if j < len(syl_texts) - 1:
                od.text((x, y), separator,
                        fill=(*MUTED_COLOR[:3], int(p_s * 180)),
                        font=fonts["syllable"])
                x += tw(od, separator, fonts["syllable"])
        y += 80

    # Respelling (alpha 230 → overlay)
    p_r = anim(0.22, 0.3)
    rw = tw(draw, respelling, fonts["respelling"])
    od.text(((WIDTH - rw) // 2, y), respelling,
            fill=(*TEXT_COLOR[:3], int(p_r * 230)), font=fonts["respelling"])
    y += 90

    # Speed badge (semi-transparent bg → overlay)
    speed_text = "SLOW" if is_slow else "NORMAL"
    speed_color = ACCENT_TEAL if is_slow else ACCENT_SKY
    pulse = 0.9 + 0.1 * math.sin(frame_num * 0.15)
    draw_pill_badge(od, speed_text, WIDTH // 2, y, fonts["small"],
                    (*speed_color[:3], int(230 * pulse)),
                    (*speed_color[:3], 40),
                    padding=(20, 6))
    y += 65

    # Progress dots (semi-transparent → overlay)
    dot_y = HEIGHT - 520
    regions = all_regions or ["US", "UK", "CA", "AU"]
    dot_spacing = 80
    start_x = WIDTH // 2 - (len(regions) - 1) * dot_spacing // 2

    for i, r in enumerate(regions):
        dx = start_x + i * dot_spacing
        r_info = REGION_INFO.get(r, {})
        is_current = r == region

        if is_current:
            pulse_r = 12 + int(2 * math.sin(frame_num * 0.12))
            od.ellipse([(dx - pulse_r, dot_y - pulse_r),
                        (dx + pulse_r, dot_y + pulse_r)],
                       fill=(*r_info.get("color", ACCENT_SKY)[:3], 230))
        else:
            od.ellipse([(dx - 7, dot_y - 7), (dx + 7, dot_y + 7)],
                       outline=(*MUTED_COLOR[:3], 120), width=2)

        label = r
        lw = tw(od, label, fonts["small"])
        a = 230 if is_current else 100
        c = TEXT_COLOR if is_current else MUTED_COLOR
        od.text((dx - lw // 2, dot_y + 22), label,
                fill=(*c[:3], a), font=fonts["small"])

    # Brand watermark (alpha 120 → overlay)
    brand = "https://pronounce.how"
    bw = tw(od, brand, fonts["brand"])
    od.text(((WIDTH - bw) // 2, HEIGHT - 390), brand,
            fill=(*MUTED_COLOR[:3], 120), font=fonts["brand"])

    # Single composite for ALL semi-transparent elements
    img = Image.alpha_composite(img, ov)

    # Face with colored glow (uses paste with mask, not alpha_composite)
    face_r = 145
    face_cy = y + face_r + 50

    if face_cache is not None:
        face_cache.paste_glow(img, WIDTH // 2, face_cy, region)
        face_cache.paste_face(img, WIDTH // 2, face_cy, face_r, viseme,
                              frame_num)
    else:
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        glow_r = face_r + 35
        gd.ellipse([(WIDTH // 2 - glow_r, face_cy - glow_r),
                    (WIDTH // 2 + glow_r, face_cy + glow_r)],
                   fill=(*info["color"][:3], 25))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=20))
        img = Image.alpha_composite(img, glow)
        draw_face(img, WIDTH // 2, face_cy, face_r, viseme, frame_num)

    return img


def render_comparison_frame(word, variants, fonts, bg, progress, frame_num):
    """Render comparison card with all variants sliding in."""
    img = bg.copy()
    draw = ImageDraw.Draw(img)

    y = 350

    # Title
    p_t = ease_out_cubic(stagger(progress, 0.0, 0.35))
    title = "All Pronunciations"
    title_w = tw(draw, title, fonts["subtitle"])
    title_y = int(lerp(y - 25, y, p_t))
    img = _text_overlay(img, (WIDTH - title_w) // 2, title_y,
                        title, fonts["subtitle"], MUTED_COLOR, p_t * 200)
    draw = ImageDraw.Draw(img)
    y += 80

    # Word
    p_word = ease_out_back(stagger(progress, 0.08, 0.4))
    ww = tw(draw, word, fonts["word_large"])
    word_y = int(lerp(y + 30, y, p_word))
    img = _text_overlay(img, (WIDTH - ww) // 2, word_y,
                        word, fonts["word_large"], TEXT_COLOR, p_word * 255)
    draw = ImageDraw.Draw(img)
    y += 140

    # Variant cards slide in from right
    for vi, v in enumerate(variants):
        region = v.get("region", "")
        ipa = v.get("ipa", "")
        v_info = REGION_INFO.get(region, {})

        p_c = ease_out_cubic(stagger(progress, 0.15 + vi * 0.08, 0.35))
        if p_c < 0.01:
            y += 110
            continue

        x_off = int((1 - p_c) * 120)
        a = int(p_c * 200)

        card_ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        cd = ImageDraw.Draw(card_ov)

        cl, cr = 70 + x_off, WIDTH - 70 + x_off
        ct, cb = y - 10, y + 80

        # Shadow
        cd.rounded_rectangle([(cl + 3, ct + 5), (cr + 3, cb + 5)],
                             radius=20, fill=(0, 0, 0, 30))
        # Card
        cd.rounded_rectangle([(cl, ct), (cr, cb)],
                             radius=20, fill=(*CARD_BG_RGB, a))
        # Color accent bar
        cd.rounded_rectangle([(cl, ct), (cl + 6, cb)],
                             radius=3,
                             fill=(*v_info.get("color", ACCENT_SKY)[:3], a))
        # Region label
        cd.text((cl + 25, ct + 18), region,
                fill=(*v_info.get("color", ACCENT_SKY)[:3], a),
                font=fonts["big_label"])
        # IPA
        cd.text((cl + 110, ct + 20), ipa,
                fill=(*TEXT_COLOR[:3], a), font=fonts["ipa"])

        img = Image.alpha_composite(img, card_ov)
        draw = ImageDraw.Draw(img)
        y += 110

    # Brand
    brand = "https://pronounce.how"
    bw_val = tw(draw, brand, fonts["brand"])
    img = _text_overlay(img, (WIDTH - bw_val) // 2, HEIGHT - 390,
                        brand, fonts["brand"], MUTED_COLOR, 120)

    return img


def render_outro_frame(word, fonts, bg, progress, frame_num, *,
                       face_cache=None):
    """Render outro with URL, CTA, and face."""
    img = bg.copy()
    draw = ImageDraw.Draw(img)

    # Face at top
    p_f = ease_out_back(stagger(progress, 0.0, 0.4))
    face_cy = int(lerp(680, 580, p_f))
    if p_f > 0.01:
        if face_cache is not None:
            face_cache.paste_face(img, WIDTH // 2, face_cy, 100, "X",
                                  frame_num)
        else:
            draw_face(img, WIDTH // 2, face_cy, 100, "X", frame_num)
    draw = ImageDraw.Draw(img)

    y = 730

    # URL
    p_u = ease_out_back(stagger(progress, 0.1, 0.4))
    url = f"https://pronounce.how/{word}"
    uw = tw(draw, url, fonts["subtitle"])
    url_y = int(lerp(y + 30, y, p_u))
    img = _text_overlay(img, (WIDTH - uw) // 2, url_y,
                        url, fonts["subtitle"], ACCENT_SKY, p_u * 255)
    draw = ImageDraw.Draw(img)
    y += 100

    # CTA
    p_c = ease_out_cubic(stagger(progress, 0.2, 0.35))
    cta = "Follow for more!"
    cw = tw(draw, cta, fonts["label"])
    img = _text_overlay(img, (WIDTH - cw) // 2, y,
                        cta, fonts["label"], TEXT_COLOR, p_c * 220)
    draw = ImageDraw.Draw(img)
    y += 80

    # Subscribe button
    p_btn = ease_out_back(stagger(progress, 0.3, 0.4))
    if p_btn > 0.01:
        sub = "Like & Subscribe"
        sw = tw(draw, sub, fonts["respelling"])
        sh = th(draw, sub, fonts["respelling"])
        px, py = 28, 14
        btn_ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(btn_ov)
        bl = (WIDTH - sw) // 2 - px
        bt = y - py
        br = (WIDTH + sw) // 2 + px
        bb = y + sh + py
        bd.rounded_rectangle([(bl, bt), (br, bb)],
                             radius=(bb - bt) // 2,
                             fill=(*ACCENT_CORAL[:3], int(p_btn * 220)))
        bd.text(((WIDTH - sw) // 2, y), sub,
                fill=(*TEXT_COLOR[:3], int(p_btn * 255)),
                font=fonts["respelling"])
        img = Image.alpha_composite(img, btn_ov)

    # Brand
    draw = ImageDraw.Draw(img)
    brand = "https://pronounce.how"
    bw_val = tw(draw, brand, fonts["brand"])
    img = _text_overlay(img, (WIDTH - bw_val) // 2, HEIGHT - 390,
                        brand, fonts["brand"], MUTED_COLOR, 130)

    return img


# ── Video assembly ───────────────────────────────────────────────────────────

def get_audio_duration(audio_path):
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True, timeout=5,
        )
        return float(result.stdout.strip())
    except (subprocess.SubprocessError, ValueError):
        return 2.5


def _compute_timeline(variants, audio_dir, slug):
    """Pre-compute video timeline without rendering any frames.

    Returns (sections, audio_segments, total_frames).
    Each section is a dict with 'type', 'frames', and section-specific metadata.
    """
    sections = []
    audio_segments = []
    frame_count = 0

    # Intro animation: 1.0s
    intro_n = int(1.0 * FPS)
    sections.append({"type": "intro_anim", "frames": intro_n})
    frame_count += intro_n

    # Intro hold: 0.3s
    hold_n = int(0.3 * FPS)
    sections.append({"type": "intro_hold", "frames": hold_n})
    frame_count += hold_n

    # Per-variant sections
    for vi, variant in enumerate(variants):
        region = variant.get("region", "US")
        phonemes = variant.get("phonemes", [])
        derived_from = variant.get("derived_from")

        # For derived variants, use base variant's phonemes if none of their own
        if derived_from and not phonemes:
            for v in variants:
                if v.get("region") == derived_from:
                    phonemes = v.get("phonemes", [])
                    break

        # Entrance: 0.5s
        ent_n = int(0.5 * FPS)
        sections.append({"type": "variant_entrance",
                         "variant_idx": vi, "frames": ent_n})
        frame_count += ent_n

        # Brief hold: 0.2s
        v_hold_n = int(0.2 * FPS)
        sections.append({"type": "variant_hold",
                         "variant_idx": vi, "frames": v_hold_n})
        frame_count += v_hold_n

        # Slow pronunciation
        slow_audio = None
        if audio_dir:
            sp = Path(audio_dir) / region.lower() / f"{slug}_slow.mp3"
            if not sp.exists() and derived_from:
                sp = Path(audio_dir) / derived_from.lower() / f"{slug}_slow.mp3"
            if sp.exists():
                slow_audio = sp
                audio_segments.append((frame_count / FPS, str(sp)))

        slow_dur = get_audio_duration(slow_audio) if slow_audio else 2.5
        slow_kf = generate_keyframes(phonemes, total_duration=slow_dur * 0.85)
        slow_n = int(slow_dur * FPS)
        sections.append({"type": "variant_slow", "variant_idx": vi,
                         "frames": slow_n, "duration": slow_dur,
                         "keyframes": slow_kf})
        frame_count += slow_n

        # Pause: 0.2s
        pause_n = int(0.2 * FPS)
        sections.append({"type": "variant_pause",
                         "variant_idx": vi, "frames": pause_n})
        frame_count += pause_n

        # Normal speed
        normal_audio = None
        if audio_dir:
            np_ = Path(audio_dir) / region.lower() / f"{slug}_normal.mp3"
            if not np_.exists() and derived_from:
                np_ = Path(audio_dir) / derived_from.lower() / f"{slug}_normal.mp3"
            if np_.exists():
                normal_audio = np_
                audio_segments.append((frame_count / FPS, str(np_)))

        normal_dur = get_audio_duration(normal_audio) if normal_audio else 1.5
        normal_kf = generate_keyframes(phonemes,
                                       total_duration=normal_dur * 0.75)
        normal_n = int(normal_dur * FPS)
        sections.append({"type": "variant_normal", "variant_idx": vi,
                         "frames": normal_n, "duration": normal_dur,
                         "keyframes": normal_kf})
        frame_count += normal_n

        # End hold: 0.3s
        end_n = int(0.3 * FPS)
        sections.append({"type": "variant_end_hold",
                         "variant_idx": vi, "frames": end_n})
        frame_count += end_n

    # Comparison: 3.0s
    comp_n = int(3.0 * FPS)
    sections.append({"type": "comparison", "frames": comp_n})
    frame_count += comp_n

    # Outro: 2.5s
    outro_n = int(2.5 * FPS)
    sections.append({"type": "outro", "frames": outro_n})
    frame_count += outro_n

    return sections, audio_segments, frame_count


def _build_audio_args(audio_segments):
    """Build FFmpeg audio input/filter arguments."""
    if not audio_segments:
        return []
    args = []
    filter_parts = []
    for idx, (start, path) in enumerate(audio_segments):
        args.extend(["-i", path])
        ms = int(start * 1000)
        filter_parts.append(f"[{idx + 1}]adelay={ms}|{ms}[a{idx}]")
    mix_in = "".join(f"[a{i}]" for i in range(len(audio_segments)))
    filt = (";".join(filter_parts) +
            f";{mix_in}amix=inputs={len(audio_segments)}:normalize=0[aout]")
    args.extend(["-filter_complex", filt, "-map", "0:v", "-map", "[aout]",
                 "-c:a", "aac", "-b:a", "128k"])
    return args


def build_video_for_word(entry, audio_dir=None, output_dir=None, fonts=None,
                         bg=None, face_cache=None):
    """Build a complete video for a word entry."""
    if fonts is None:
        fonts = get_fonts()
    if bg is None:
        bg = create_gradient_bg()
    if face_cache is None:
        face_cache = FaceSpriteCache()

    word = entry["word"]
    slug = entry["slug"]
    variants = entry.get("variants", [])

    if not variants:
        print(f"  {word}: no variants, skipping")
        return None

    variants = sorted(
        variants, key=lambda v: REGION_ORDER.get(v.get("region", ""), 99)
    )
    entry_regions = [v.get("region", "") for v in variants]

    if output_dir is None:
        output_dir = Path("video")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{slug}.mp4"

    # Pre-compute timeline and audio segments
    sections, audio_segments, total_frames = _compute_timeline(
        variants, audio_dir, slug)
    total_duration = total_frames / FPS

    # Build FFmpeg command for piped input
    audio_args = _build_audio_args(audio_segments)

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS),
        "-i", "pipe:0",
        *audio_args,
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "medium", "-crf", "18",
        "-profile:v", "high",
        "-t", str(total_duration),
        str(output_path),
    ]

    # Start FFmpeg process
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        print(f"  FFmpeg start failed: {e}")
        return None

    print(f"  Rendering {total_frames} frames...")

    frame_num = 0

    def pipe_frame(img):
        nonlocal frame_num
        proc.stdin.write(img.convert("RGB").tobytes())
        frame_num += 1

    def pipe_repeat(img, count):
        """Pipe the same frame multiple times (for hold sections)."""
        nonlocal frame_num
        data = img.convert("RGB").tobytes()
        for _ in range(count):
            proc.stdin.write(data)
            frame_num += 1

    try:
        for section in sections:
            stype = section["type"]
            n = section["frames"]

            if stype == "intro_anim":
                for i in range(n):
                    pipe_frame(render_intro_frame(
                        word, fonts, bg, i / max(1, n - 1), i,
                        face_cache=face_cache))

            elif stype == "intro_hold":
                hold = render_intro_frame(
                    word, fonts, bg, 1.0, frame_num,
                    face_cache=face_cache)
                pipe_repeat(hold, n)

            elif stype == "variant_entrance":
                variant = variants[section["variant_idx"]]
                for i in range(n):
                    pipe_frame(render_variant_frame(
                        word, variant, fonts, bg, "X", -1,
                        i / max(1, n - 1), frame_num + i, False,
                        show_entrance=True, all_regions=entry_regions,
                        face_cache=face_cache))

            elif stype == "variant_hold":
                variant = variants[section["variant_idx"]]
                hold = render_variant_frame(
                    word, variant, fonts, bg, "X", -1,
                    1.0, frame_num, False, show_entrance=False,
                    all_regions=entry_regions, face_cache=face_cache)
                pipe_repeat(hold, n)

            elif stype == "variant_slow":
                variant = variants[section["variant_idx"]]
                syllables = variant.get("syllables", [])
                dur = section["duration"]
                kf_list = section["keyframes"]
                for i in range(n):
                    t = i / FPS
                    vis = "X"
                    for kf in kf_list:
                        if kf["time"] <= t:
                            vis = kf["viseme"]
                    a_syl = -1
                    if syllables:
                        a_syl = min(int((t / dur) * len(syllables)),
                                    len(syllables) - 1)
                    pipe_frame(render_variant_frame(
                        word, variant, fonts, bg, vis, a_syl,
                        1.0, frame_num + i, True, show_entrance=False,
                        all_regions=entry_regions, face_cache=face_cache))

            elif stype == "variant_pause":
                variant = variants[section["variant_idx"]]
                pause = render_variant_frame(
                    word, variant, fonts, bg, "X", -1,
                    1.0, frame_num, False, show_entrance=False,
                    all_regions=entry_regions, face_cache=face_cache)
                pipe_repeat(pause, n)

            elif stype == "variant_normal":
                variant = variants[section["variant_idx"]]
                dur = section["duration"]
                kf_list = section["keyframes"]
                for i in range(n):
                    t = i / FPS
                    vis = "X"
                    for kf in kf_list:
                        if kf["time"] <= t:
                            vis = kf["viseme"]
                    pipe_frame(render_variant_frame(
                        word, variant, fonts, bg, vis, -1,
                        1.0, frame_num + i, False, show_entrance=False,
                        all_regions=entry_regions, face_cache=face_cache))

            elif stype == "variant_end_hold":
                variant = variants[section["variant_idx"]]
                hold = render_variant_frame(
                    word, variant, fonts, bg, "X", -1,
                    1.0, frame_num, False, show_entrance=False,
                    all_regions=entry_regions, face_cache=face_cache)
                pipe_repeat(hold, n)

            elif stype == "comparison":
                for i in range(n):
                    pipe_frame(render_comparison_frame(
                        word, variants, fonts, bg,
                        i / max(1, n - 1), frame_num + i))

            elif stype == "outro":
                for i in range(n):
                    pipe_frame(render_outro_frame(
                        word, fonts, bg,
                        i / max(1, n - 1), frame_num + i,
                        face_cache=face_cache))

    except BrokenPipeError:
        print("  Warning: FFmpeg pipe closed early")
    finally:
        try:
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    # Wait for FFmpeg to finish (stdin already closed, so use wait+stderr.read)
    try:
        stderr = proc.stderr.read() if proc.stderr else b""
        proc.wait(timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
        stderr = proc.stderr.read() if proc.stderr else b""
        proc.wait()

    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace")[:300] if stderr else ""
        print(f"  FFmpeg error: {err}")
        return None

    if output_path.exists():
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"  Created: {output_path} ({size_mb:.1f} MB, {total_duration:.1f}s)")
        return output_path
    return None


# ── Worker for multiprocessing ───────────────────────────────────────────────

# Per-process shared resources (initialized once per worker)
_worker_fonts = None
_worker_bg = None
_worker_face_cache = None


def _worker_init():
    """Initialize shared resources in each worker process."""
    global _worker_fonts, _worker_bg, _worker_face_cache
    _worker_fonts = get_fonts()
    _worker_bg = create_gradient_bg()
    _worker_face_cache = FaceSpriteCache()


def _worker_process(args_tuple):
    """Process a single word file in a worker. Returns (slug, ok)."""
    filepath, audio_dir, output_dir = args_tuple
    global _worker_fonts, _worker_bg, _worker_face_cache

    try:
        with open(filepath) as f:
            entry = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return (filepath.stem, False, str(e))

    result = build_video_for_word(
        entry,
        audio_dir=audio_dir,
        output_dir=output_dir,
        fonts=_worker_fonts,
        bg=_worker_bg,
        face_cache=_worker_face_cache,
    )
    return (entry.get("word", filepath.stem), result is not None, "")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate pronunciation videos (YouTube Shorts format)."
    )
    parser.add_argument("--word", help="Generate video for a single word")
    parser.add_argument("--data-dir", type=Path, default=DATA_WORDS_DIR)
    parser.add_argument("--audio-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip words that already have a video file")
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of parallel workers (default: 1)")
    args = parser.parse_args(argv)

    data_dir = args.data_dir
    audio_dir = args.audio_dir
    if audio_dir is None and not args.no_audio:
        audio_dir = data_dir.parent.parent / "audio"
    output_dir = args.output_dir or Path("video")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
    except (subprocess.SubprocessError, FileNotFoundError):
        print("Error: ffmpeg not found. Install with: sudo apt install ffmpeg")
        return 1

    # Collect word files
    if args.word:
        slug = args.word.lower().replace(" ", "-")
        filepath = data_dir / slug[0] / f"{slug}.json"
        if not filepath.exists():
            print(f"Error: {filepath} not found")
            return 1
        word_files = [filepath]
    else:
        word_files = sorted(data_dir.rglob("*.json"))
        if args.limit > 0:
            word_files = word_files[:args.limit]

    # Filter out existing videos
    if args.skip_existing:
        before = len(word_files)
        word_files = [
            f for f in word_files
            if not (output_dir / f"{f.stem}.mp4").exists()
        ]
        skipped = before - len(word_files)
        if skipped > 0:
            print(f"Skipping {skipped} words with existing videos")

    total = len(word_files)
    print(f"Words to process: {total}")
    print(f"Output directory: {output_dir}")

    if total == 0:
        print("Nothing to do.")
        return 0

    audio_dir_str = str(audio_dir) if audio_dir and not args.no_audio else None
    workers = min(args.workers, total)

    # Single-worker mode (simpler, no multiprocessing overhead)
    if workers <= 1:
        print("Loading fonts...")
        fonts = get_fonts()
        print("Pre-rendering sprite caches...")
        bg = create_gradient_bg()
        face_cache = FaceSpriteCache()

        generated = 0
        failed = 0
        t0 = time.time()

        for i, filepath in enumerate(word_files):
            try:
                with open(filepath) as f:
                    entry = json.load(f)
            except (json.JSONDecodeError, OSError):
                print(f"  Skipping {filepath}: invalid JSON")
                failed += 1
                continue

            elapsed = time.time() - t0
            rate = (i / elapsed) if elapsed > 0 and i > 0 else 0
            eta = ((total - i) / rate / 3600) if rate > 0 else 0
            print(f"\n[{i+1}/{total}] {entry.get('word', filepath.stem)}"
                  f"  ({rate:.1f}/s, ETA {eta:.1f}h)")

            result = build_video_for_word(
                entry, audio_dir=audio_dir_str, output_dir=output_dir,
                fonts=fonts, bg=bg, face_cache=face_cache,
            )
            if result:
                generated += 1
            else:
                failed += 1

        elapsed = time.time() - t0
        print(f"\n{'=' * 60}")
        print(f"Generated: {generated}  Failed: {failed}")
        print(f"Time: {elapsed/3600:.1f}h ({elapsed/max(1,generated):.1f}s/video)")
        return 0

    # Multi-worker mode
    print(f"Starting {workers} parallel workers...")
    tasks = [(f, audio_dir_str, output_dir) for f in word_files]

    generated = 0
    failed = 0
    t0 = time.time()

    with multiprocessing.Pool(workers, initializer=_worker_init) as pool:
        for i, (word, ok, err) in enumerate(
            pool.imap_unordered(_worker_process, tasks, chunksize=4)
        ):
            if ok:
                generated += 1
            else:
                failed += 1
                if err:
                    print(f"  FAIL: {word}: {err}")

            if (i + 1) % 50 == 0 or i + 1 == total:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (total - i - 1) / rate / 3600 if rate > 0 else 0
                print(f"  [{i+1}/{total}] generated={generated} failed={failed}"
                      f"  ({rate:.1f}/s, ETA {eta:.1f}h)")

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"Generated: {generated}  Failed: {failed}")
    print(f"Time: {elapsed/3600:.1f}h ({elapsed/max(1,generated):.1f}s/video)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
