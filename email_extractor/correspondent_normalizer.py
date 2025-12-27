#!/usr/bin/env python3
"""
NAS5 Docker Apps Collection
"""

"""
This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels
"""

"""
This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels
"""

"""
Correspondent Normalizer for Paperless-NGX
==========================================
Normalizes correspondent names to prevent duplicates.
Handles common variations like:
- Case differences: "ADOBE" vs "Adobe"
- Legal suffixes: "Inc.", "s.r.o.", "GmbH", etc.
- Service variants: "Google" vs "Google Alerts"
- Unicode variants: "Gab" vs "Gab"
- Domain suffixes: "Alza.cz" vs "alza.cz"
"""

import re
import unicodedata
from typing import Optional, Dict, List, Tuple

# Legal entity suffixes to remove
LEGAL_SUFFIXES = [
    r'\s+inc\.?$', r'\s+ltd\.?$', r'\s+gmbh$', r'\s+s\.?r\.?o\.?$',
    r'\s+a\.?s\.?$', r'\s+corp\.?$', r'\s+llc$', r'\s+ag$', r'\s+co\.?$',
    r'\s+sp\.\s*z\.?\s*o\.?\s*o\.?$', r'\s+b\.?v\.?$', r'\s+n\.?v\.?$',
    r'\s+plc$', r'\s+pty\.?\s*ltd\.?$', r'\s+limited$', r'\s+holding$',
    r',\s*s\.?r\.?o\.?$', r',\s*a\.?s\.?$', r',\s*spol\.\s*s\s*r\.?o\.?$',
]

# Service/newsletter suffixes to remove
SERVICE_SUFFIXES = [
    r'\s+newsletter$', r'\s+news$', r'\s+alerts?$', r'\s+deals?$',
    r'\s+price\s+alerts?$', r'\s+home$', r'\s+info$', r'\s+team$',
    r'\s+support$', r'\s+noreply$', r'\s+no-reply$', r'\s+mailer$',
]

# Domain patterns
DOMAIN_PATTERN = re.compile(r'\.(cz|com|de|net|org|eu|sk|io|co|uk|at|ch)$', re.IGNORECASE)

# Unicode replacements
UNICODE_REPLACEMENTS = {
    '': '*',  # star emoji -> asterisk
    '': '*',
    '': '*',
    '': '',   # frog emoji -> remove
    '': '',   # other emojis
    '': '',
    '': '',
    '': '',
    '': '',
    '🛠': '',
    '🟣': '',
    '📣': '',
    '►': '',
    '◄': '',
}


def remove_emojis(text: str) -> str:
    """Remove emoji characters from text"""
    # First use explicit replacements
    for emoji, replacement in UNICODE_REPLACEMENTS.items():
        text = text.replace(emoji, replacement)

    # Then remove remaining emoji via unicode categories
    return ''.join(
        char for char in text
        if unicodedata.category(char) not in ('So', 'Sk', 'Sm', 'Sc')
        or char in ('©', '®', '™')  # Keep some symbols
    )


def normalize_correspondent(name: str) -> str:
    """
    Normalize a correspondent name for deduplication.

    Args:
        name: Original correspondent name

    Returns:
        Normalized name suitable for comparison
    """
    if not name:
        return ""

    # Remove email format if present: "Name <email@domain.com>"
    email_match = re.match(r'^(.+?)\s*<[^>]+>$', name)
    if email_match:
        name = email_match.group(1)

    # Remove emojis and special unicode
    name = remove_emojis(name)

    # Lowercase and strip
    name = name.lower().strip()

    # Remove legal suffixes
    for pattern in LEGAL_SUFFIXES:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)

    # Remove service suffixes
    for pattern in SERVICE_SUFFIXES:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)

    # Normalize domain extensions (keep domain, remove .xx)
    name = DOMAIN_PATTERN.sub('', name)

    # Replace special characters with spaces
    name = re.sub(r'[^\w\s-]', ' ', name)

    # Normalize whitespace
    name = re.sub(r'\s+', ' ', name).strip()

    # Remove trailing numbers (issue numbers etc)
    name = re.sub(r'\s+\d+$', '', name)
    name = re.sub(r'\s+(č|no|nr|issue|vol)\.?\s*\d+.*$', '', name, flags=re.IGNORECASE)

    return name


def get_canonical_name(names: List[str]) -> str:
    """
    Choose the best canonical name from a list of variants.
    Prefers: shorter names, proper case, no special chars.

    Args:
        names: List of variant names

    Returns:
        Best canonical name to use
    """
    if not names:
        return ""

    def score_name(name: str) -> Tuple[int, int, int, str]:
        """Score a name - lower is better"""
        # Prefer names without emojis/special chars
        special_chars = len(re.findall(r'[^\w\s.,\-]', name))
        # Prefer shorter names
        length = len(name)
        # Prefer proper case (not all caps, not all lower)
        case_score = 2 if name.isupper() or name.islower() else 0
        return (special_chars, case_score, length, name)

    sorted_names = sorted(names, key=score_name)
    return sorted_names[0]


def find_duplicates(correspondents: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Find duplicate correspondents based on normalized names.

    Args:
        correspondents: List of correspondent dicts with 'id', 'name', 'document_count'

    Returns:
        Dict mapping normalized name to list of correspondent dicts
    """
    from collections import defaultdict

    groups = defaultdict(list)
    for c in correspondents:
        norm = normalize_correspondent(c.get('name', ''))
        if norm:
            groups[norm].append(c)

    # Return only groups with duplicates
    return {k: v for k, v in groups.items() if len(v) > 1}


# Mapping for known correspondents (manual overrides)
KNOWN_MAPPINGS = {
    'adobe': 'Adobe',
    'adobe systems': 'Adobe',
    'google': 'Google',
    'google alerts': 'Google',
    'alza': 'Alza.cz',
    'alza cz': 'Alza.cz',
    'booking': 'Booking.com',
    'booking com': 'Booking.com',
    'tripadvisor': 'Tripadvisor',
    'kickstarter': 'Kickstarter',
    'hobynaradi': 'HobyNaradi.cz',
    'hobynaradi cz': 'HobyNaradi.cz',
    'datart': 'DATART',
    'mall': 'MALL.CZ',
    'mall cz': 'MALL.CZ',
    'slevomat': 'Slevomat.cz',
    'slevomat cz': 'Slevomat.cz',
    'aukro': 'Aukro',
    'tesla lighting': 'TESLA LIGHTING',
    'loxone': 'Loxone',
    'ubiquiti': 'Ubiquiti',
    'agoda': 'Agoda',
    'expondo': 'Expondo.cz',
    'expondo cz': 'Expondo.cz',
}


def get_best_correspondent_name(name: str) -> str:
    """
    Get the best correspondent name, using known mappings if available.

    Args:
        name: Input correspondent name

    Returns:
        Best normalized name
    """
    normalized = normalize_correspondent(name)

    # Check known mappings first
    if normalized in KNOWN_MAPPINGS:
        return KNOWN_MAPPINGS[normalized]

    # Otherwise return the original with cleanup
    # Remove emojis but keep structure
    cleaned = remove_emojis(name).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)

    # Remove legal suffixes for cleaner display
    for pattern in LEGAL_SUFFIXES:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    return cleaned.strip() or name


if __name__ == '__main__':
    # Test cases
    test_names = [
        "Adobe",
        "adobe systems",
        "ADOBE Inc.",
        "Google",
        "Google Alerts",
        "Alza.cz",
        "alza.cz",
        "ALZA.CZ a.s.",
        "100+1 ★ letní",
        "100+1 * nové č.8",
        "🛠 HobyNaradi.cz",
        "HobyNaradi.cz s.r.o.",
        "Gab🐸 <GabNews@mailer.gab.com>",
        "Gab 🐸 <GabNews@mailer.gab.com>",
        "►DATART◄",
        "DATART",
        "TESLA LIGHTING S.r.o.",
        "Tesla Lighting s.r.o.",
        "TESLA Lighting",
        "Agoda Price Alerts",
        "Agoda Deals",
    ]

    print("=== Correspondent Normalizer Test ===\n")
    for name in test_names:
        normalized = normalize_correspondent(name)
        best = get_best_correspondent_name(name)
        print(f"'{name}'")
        print(f"  -> normalized: '{normalized}'")
        print(f"  -> best name:  '{best}'")
        print()
