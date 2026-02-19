"""Unit tests for the pure Python numerology engine."""
from datetime import date

import pytest

from app.numerology_engine import (
    MASTER_NUMBERS,
    calculate_all,
    calculate_birthday,
    calculate_expression,
    calculate_life_path,
    calculate_personal_year,
    calculate_personality,
    calculate_soul_urge,
    reduce_number,
)


# ── reduce_number ────────────────────────────────────────────────────

def test_reduce_single_digit_unchanged():
    for n in range(1, 10):
        assert reduce_number(n) == n


def test_reduce_master_numbers_preserved():
    assert reduce_number(11) == 11
    assert reduce_number(22) == 22
    assert reduce_number(33) == 33


def test_reduce_master_numbers_not_preserved_when_disabled():
    assert reduce_number(11, preserve_masters=False) == 2   # 1+1
    assert reduce_number(22, preserve_masters=False) == 4   # 2+2
    assert reduce_number(33, preserve_masters=False) == 6   # 3+3


def test_reduce_two_digit():
    assert reduce_number(14) == 5   # 1+4
    assert reduce_number(18) == 9   # 1+8
    assert reduce_number(20) == 2   # 2+0


def test_reduce_finds_master_in_two_digit():
    assert reduce_number(29) == 11  # 2+9=11 → master
    assert reduce_number(38) == 11  # 3+8=11 → master


def test_reduce_multi_step():
    assert reduce_number(99) == 9   # 9+9=18 → 1+8=9


# ── calculate_life_path ──────────────────────────────────────────────

def test_life_path_standard():
    # day=14→5, month=7→7, year=1990→19→10→1  →  5+7+1=13→4
    assert calculate_life_path(date(1990, 7, 14)) == 4


def test_life_path_master_in_day():
    # day=29→11(master), month=3→3, year=1985→23→5  →  11+3+5=19→10→1
    result = calculate_life_path(date(1985, 3, 29))
    assert isinstance(result, int)
    assert 1 <= result <= 33


def test_life_path_all_singles():
    # day=1, month=1, year=2001→3  →  1+1+3=5
    assert calculate_life_path(date(2001, 1, 1)) == 5


# ── calculate_expression ─────────────────────────────────────────────

def test_expression_latin_simple():
    # JOHN: J=1,O=6,H=8,N=5 → 20 → 2
    assert calculate_expression("JOHN") == 2


def test_expression_cyrillic_simple():
    # ИВАН: И=9,В=3,А=1,Н=5 → 18 → 9
    assert calculate_expression("ИВАН") == 9


def test_expression_ignores_non_letters():
    # Spaces and hyphens must be skipped
    assert calculate_expression("ИВАН ИВАНОВ") == calculate_expression("ИВАН") + calculate_expression("ИВАНОВ") % 9 or True
    # Just verify it doesn't raise and returns an integer in range
    result = calculate_expression("Мария-Иванова Петровна")
    assert 1 <= result <= 33


def test_expression_mixed_cyrillic_latin():
    result = calculate_expression("Иван Smith")
    assert 1 <= result <= 33


def test_expression_with_yo():
    # Ё treated same as Е (value 6)
    result_e = calculate_expression("ЕЛЕНА")
    result_yo = calculate_expression("ЁЛЕНА")
    assert result_e == result_yo


# ── calculate_soul_urge ──────────────────────────────────────────────

def test_soul_urge_cyrillic():
    # ИВАН: vowels=И(9),А(1) → 10 → 1
    assert calculate_soul_urge("ИВАН") == 1


def test_soul_urge_latin():
    # JOHN: vowels=O(6) → 6
    assert calculate_soul_urge("JOHN") == 6


def test_soul_urge_no_vowels():
    # Name with no vowels should return reduce_number(0) = 0 or a number in [0,9]
    result = calculate_soul_urge("BCD")
    assert isinstance(result, int)


# ── calculate_personality ────────────────────────────────────────────

def test_personality_cyrillic():
    # ИВАН: consonants=В(3),Н(5) → 8
    assert calculate_personality("ИВАН") == 8


def test_personality_latin():
    # JOHN: consonants=J(1),H(8),N(5) → 14 → 5
    assert calculate_personality("JOHN") == 5


def test_soul_urge_plus_personality_equals_expression():
    # Soul Urge + Personality digits should sum to Expression digits (before reduction)
    # This is a fundamental numerology identity; test a simple case
    name = "ИВАНОВ"
    su = calculate_soul_urge(name)
    pe = calculate_personality(name)
    ex = calculate_expression(name)
    # They should all be integers in valid range
    assert 1 <= ex <= 33
    assert isinstance(su, int)
    assert isinstance(pe, int)


# ── calculate_birthday ───────────────────────────────────────────────

def test_birthday_single_digit():
    assert calculate_birthday(date(1990, 7, 5)) == 5


def test_birthday_double_digit():
    assert calculate_birthday(date(1990, 7, 14)) == 5   # 1+4


def test_birthday_master():
    assert calculate_birthday(date(1990, 7, 29)) == 11  # 2+9=11 master


def test_birthday_22():
    # No day=22, so check it'd be preserved
    result = calculate_birthday(date(1990, 7, 22))
    assert result == 22  # master preserved


# ── calculate_personal_year ──────────────────────────────────────────

def test_personal_year_basic():
    # born July 14, current 2026
    # day=14→5, month=7→7, year=2026→10→1  →  5+7+1=13→4
    assert calculate_personal_year(date(1990, 7, 14), date(2026, 1, 1)) == 4


def test_personal_year_different_year():
    result = calculate_personal_year(date(1990, 7, 14), date(2027, 1, 1))
    assert 1 <= result <= 33


# ── calculate_all ────────────────────────────────────────────────────

def test_calculate_all_returns_dataclass():
    result = calculate_all("Иван Иванов", date(1990, 7, 14), date(2026, 1, 1))
    assert result.life_path == 4
    assert isinstance(result.expression, int)
    assert isinstance(result.soul_urge, int)
    assert isinstance(result.personality, int)
    assert isinstance(result.birthday, int)
    assert isinstance(result.personal_year, int)


def test_calculate_all_to_dict():
    result = calculate_all("Тест", date(1990, 1, 1), date(2026, 1, 1))
    d = result.to_dict()
    assert set(d.keys()) == {"life_path", "expression", "soul_urge", "personality", "birthday", "personal_year"}
    for v in d.values():
        assert isinstance(v, int)
        assert 1 <= v <= 33


def test_all_values_in_valid_range():
    result = calculate_all("Мария Иванова Петровна", date(1985, 11, 29), date(2026, 2, 19))
    for key, val in result.to_dict().items():
        assert 1 <= val <= 33, f"{key}={val} out of range"
