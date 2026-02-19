"""Pure Python Pythagorean numerology calculations. No external dependencies."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


# ── Pythagorean letter-to-digit tables ──────────────────────────────

# Latin Pythagorean (standard Western table)
# A=1 B=2 C=3 D=4 E=5 F=6 G=7 H=8 I=9
# J=1 K=2 L=3 M=4 N=5 O=6 P=7 Q=8 R=9
# S=1 T=2 U=3 V=4 W=5 X=6 Y=7 Z=8
LATIN_TABLE: dict[str, int] = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8, "I": 9,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "O": 6, "P": 7, "Q": 8, "R": 9,
    "S": 1, "T": 2, "U": 3, "V": 4, "W": 5, "X": 6, "Y": 7, "Z": 8,
}

# Russian Cyrillic Pythagorean mapping (positional 1-9 cycle)
# А=1 Б=2 В=3 Г=4 Д=5 Е=6 Ж=7 З=8 И=9
# Й=1 К=2 Л=3 М=4 Н=5 О=6 П=7 Р=8 С=9
# Т=1 У=2 Ф=3 Х=4 Ц=5 Ч=6 Ш=7 Щ=8 Ъ=9
# Ы=1 Ь=2 Э=3 Ю=4 Я=5  (Ё=6, same as Е)
CYRILLIC_TABLE: dict[str, int] = {
    "А": 1, "Б": 2, "В": 3, "Г": 4, "Д": 5, "Е": 6, "Ж": 7, "З": 8, "И": 9,
    "Й": 1, "К": 2, "Л": 3, "М": 4, "Н": 5, "О": 6, "П": 7, "Р": 8, "С": 9,
    "Т": 1, "У": 2, "Ф": 3, "Х": 4, "Ц": 5, "Ч": 6, "Ш": 7, "Щ": 8, "Ъ": 9,
    "Ы": 1, "Ь": 2, "Э": 3, "Ю": 4, "Я": 5,
    "Ё": 6,  # treated as Е (universal Russian numerology convention)
}

MASTER_NUMBERS: frozenset[int] = frozenset({11, 22, 33})

# Vowels for Soul Urge calculation
CYRILLIC_VOWELS: frozenset[str] = frozenset("АЕЁИОУЫЭЮЯ")
LATIN_VOWELS: frozenset[str] = frozenset("AEIOU")


# ── Core reduction logic ─────────────────────────────────────────────

def reduce_number(n: int, preserve_masters: bool = True) -> int:
    """Reduce n to a single digit (1-9), preserving master numbers 11, 22, 33."""
    if n <= 9:
        return n
    if preserve_masters and n in MASTER_NUMBERS:
        return n
    digit_sum = sum(int(d) for d in str(n))
    return reduce_number(digit_sum, preserve_masters=preserve_masters)


def _letter_value(char: str) -> int | None:
    """Return Pythagorean value for a single letter (Cyrillic or Latin), or None."""
    upper = char.upper()
    if upper in CYRILLIC_TABLE:
        return CYRILLIC_TABLE[upper]
    if upper in LATIN_TABLE:
        return LATIN_TABLE[upper]
    return None


def _is_vowel(char: str) -> bool:
    upper = char.upper()
    return upper in CYRILLIC_VOWELS or upper in LATIN_VOWELS


# ── Six calculation functions ────────────────────────────────────────

def calculate_life_path(birth_date: date) -> int:
    """Life Path: reduce day, month, year separately → sum → reduce.

    Each component is reduced independently before summing so that master
    numbers within components (e.g. day=29→11) are preserved.
    """
    day_reduced = reduce_number(birth_date.day)
    month_reduced = reduce_number(birth_date.month)
    year_digits_sum = sum(int(d) for d in str(birth_date.year))
    year_reduced = reduce_number(year_digits_sum)
    return reduce_number(day_reduced + month_reduced + year_reduced)


def calculate_expression(full_name: str) -> int:
    """Expression (Destiny): sum Pythagorean values of ALL letters."""
    total = sum(v for c in full_name if (v := _letter_value(c)) is not None)
    return reduce_number(total)


def calculate_soul_urge(full_name: str) -> int:
    """Soul Urge (Heart's Desire): sum values of vowels only."""
    total = 0
    for char in full_name:
        if _is_vowel(char):
            v = _letter_value(char)
            if v is not None:
                total += v
    return reduce_number(total)


def calculate_personality(full_name: str) -> int:
    """Personality: sum values of consonants only."""
    total = 0
    for char in full_name:
        v = _letter_value(char)
        if v is not None and not _is_vowel(char):
            total += v
    return reduce_number(total)


def calculate_birthday(birth_date: date) -> int:
    """Birthday: birth day reduced to single digit or master number."""
    return reduce_number(birth_date.day)


def calculate_personal_year(birth_date: date, current_date: date) -> int:
    """Personal Year: reduce(birth_day + birth_month + current_year_digits)."""
    day_reduced = reduce_number(birth_date.day)
    month_reduced = reduce_number(birth_date.month)
    year_digits_sum = sum(int(d) for d in str(current_date.year))
    year_reduced = reduce_number(year_digits_sum)
    return reduce_number(day_reduced + month_reduced + year_reduced)


# ── Result dataclass ─────────────────────────────────────────────────

@dataclass
class NumerologyResult:
    life_path: int
    expression: int
    soul_urge: int
    personality: int
    birthday: int
    personal_year: int

    def to_dict(self) -> dict[str, int]:
        return {
            "life_path": self.life_path,
            "expression": self.expression,
            "soul_urge": self.soul_urge,
            "personality": self.personality,
            "birthday": self.birthday,
            "personal_year": self.personal_year,
        }


def calculate_all(full_name: str, birth_date: date, current_date: date) -> NumerologyResult:
    """Compute all 6 numerology numbers at once."""
    return NumerologyResult(
        life_path=calculate_life_path(birth_date),
        expression=calculate_expression(full_name),
        soul_urge=calculate_soul_urge(full_name),
        personality=calculate_personality(full_name),
        birthday=calculate_birthday(birth_date),
        personal_year=calculate_personal_year(birth_date, current_date),
    )
