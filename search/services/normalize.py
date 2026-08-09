from __future__ import annotations

import re
import unicodedata

_WS_RE = re.compile(r'\s+')


def _is_kept_char(char: str) -> bool:
    """Keep letters, marks (Bangla vowel signs), numbers, and spaces."""
    if char.isspace():
        return True
    category = unicodedata.category(char)
    if category.startswith(('L', 'M', 'N')):
        return True
    # Full Bangla block (includes digits/punctuation used in Bangla text)
    code = ord(char)
    if 0x0980 <= code <= 0x09FF:
        return category[0] != 'P' and category[0] != 'S'
    return False


def normalize_query(raw: str | None) -> str:
    """
    Normalize a user search string for matching/analytics.

    - Unicode NFC
    - trim + collapse whitespace
    - casefold (Latin; Bangla unaffected)
    - strip punctuation/symbols while preserving Bangla letters and vowel signs
    """
    if raw is None:
        return ''
    text = unicodedata.normalize('NFC', str(raw))
    text = text.strip()
    if not text:
        return ''
    text = _WS_RE.sub(' ', text)
    text = text.casefold()
    text = ''.join(ch if _is_kept_char(ch) else ' ' for ch in text)
    text = _WS_RE.sub(' ', text).strip()
    return text
