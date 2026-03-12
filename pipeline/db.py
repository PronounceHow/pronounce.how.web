"""SQLite staging database schema and helpers."""

import sqlite3
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS words (
    word        TEXT PRIMARY KEY,
    slug        TEXT NOT NULL,
    pos         TEXT,           -- JSON array or single string
    priority    TEXT DEFAULT 'medium',
    status      TEXT DEFAULT 'standard',
    frequency_rank INTEGER
);

CREATE TABLE IF NOT EXISTS variants (
    word            TEXT NOT NULL,
    region          TEXT NOT NULL,  -- US, UK, CA, AU
    ipa             TEXT,
    arpabet         TEXT,           -- JSON array of ARPAbet tokens
    syllables       TEXT,           -- JSON array of syllable objects
    respelling      TEXT,
    source_type     TEXT,
    source_detail   TEXT,
    confidence      REAL DEFAULT 0.5,
    confidence_reason TEXT,
    derived_from    TEXT,
    notes           TEXT,
    PRIMARY KEY (word, region)
);

CREATE TABLE IF NOT EXISTS wiktextract_cache (
    word    TEXT NOT NULL,
    region  TEXT NOT NULL,
    ipa     TEXT,
    pos     TEXT,
    PRIMARY KEY (word, region)
);

CREATE TABLE IF NOT EXISTS target_words (
    word        TEXT PRIMARY KEY,
    included    INTEGER DEFAULT 1,
    priority    TEXT DEFAULT 'medium'
);

CREATE INDEX IF NOT EXISTS idx_variants_word ON variants(word);
CREATE INDEX IF NOT EXISTS idx_variants_region ON variants(region);
CREATE INDEX IF NOT EXISTS idx_words_slug ON words(slug);
CREATE INDEX IF NOT EXISTS idx_target_words_included ON target_words(included);
"""


def get_db(db_path=None):
    """Open (and optionally create) the staging database."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    return conn


@contextmanager
def transaction(conn):
    """Context manager for atomic transactions."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def slugify(word):
    """Convert a word to a URL-safe slug."""
    import re
    slug = word.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def upsert_word(conn, word, slug=None, pos=None, priority=None,
                status=None, frequency_rank=None):
    """Insert or update a word row."""
    if slug is None:
        slug = slugify(word)
    conn.execute("""
        INSERT INTO words (word, slug, pos, priority, status, frequency_rank)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(word) DO UPDATE SET
            slug = COALESCE(excluded.slug, words.slug),
            pos = COALESCE(excluded.pos, words.pos),
            priority = COALESCE(excluded.priority, words.priority),
            status = COALESCE(excluded.status, words.status),
            frequency_rank = COALESCE(excluded.frequency_rank, words.frequency_rank)
    """, (word, slug, pos, priority, status, frequency_rank))


def upsert_variant(conn, word, region, ipa=None, arpabet=None,
                   syllables=None, respelling=None, source_type=None,
                   source_detail=None, confidence=None,
                   confidence_reason=None, derived_from=None, notes=None):
    """Insert or update a variant row."""
    conn.execute("""
        INSERT INTO variants (word, region, ipa, arpabet, syllables, respelling,
                              source_type, source_detail, confidence,
                              confidence_reason, derived_from, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(word, region) DO UPDATE SET
            ipa = COALESCE(excluded.ipa, variants.ipa),
            arpabet = COALESCE(excluded.arpabet, variants.arpabet),
            syllables = COALESCE(excluded.syllables, variants.syllables),
            respelling = COALESCE(excluded.respelling, variants.respelling),
            source_type = COALESCE(excluded.source_type, variants.source_type),
            source_detail = COALESCE(excluded.source_detail, variants.source_detail),
            confidence = COALESCE(excluded.confidence, variants.confidence),
            confidence_reason = COALESCE(excluded.confidence_reason, variants.confidence_reason),
            derived_from = COALESCE(excluded.derived_from, variants.derived_from),
            notes = COALESCE(excluded.notes, variants.notes)
    """, (word, region, ipa, arpabet, syllables, respelling,
          source_type, source_detail, confidence,
          confidence_reason, derived_from, notes))


def get_variant(conn, word, region):
    """Fetch a single variant row."""
    row = conn.execute(
        "SELECT * FROM variants WHERE word = ? AND region = ?",
        (word, region)
    ).fetchone()
    return dict(row) if row else None


def get_all_variants(conn, word):
    """Fetch all variant rows for a word."""
    rows = conn.execute(
        "SELECT * FROM variants WHERE word = ? ORDER BY region",
        (word,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_word(conn, word):
    """Fetch a word row."""
    row = conn.execute(
        "SELECT * FROM words WHERE word = ?", (word,)
    ).fetchone()
    return dict(row) if row else None


def count_variants(conn, region=None, source_type=None):
    """Count variants, optionally filtered."""
    query = "SELECT COUNT(*) FROM variants WHERE 1=1"
    params = []
    if region:
        query += " AND region = ?"
        params.append(region)
    if source_type:
        query += " AND source_type = ?"
        params.append(source_type)
    return conn.execute(query, params).fetchone()[0]
