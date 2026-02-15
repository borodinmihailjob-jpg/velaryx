import hashlib
import json
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from .config import settings

DECK_PATH = Path(__file__).resolve().parent / "assets" / "tarot_deck.json"

SPREADS = {
    "one_card": ["focus"],
    "three_card": ["past", "present", "future"],
    "relationship": ["you", "partner", "connection"],
    "career": ["situation", "challenge", "advice"],
}

MAJOR_ARCANA = [
    "The Fool",
    "The Magician",
    "The High Priestess",
    "The Empress",
    "The Emperor",
    "The Hierophant",
    "The Lovers",
    "The Chariot",
    "Strength",
    "The Hermit",
    "Wheel of Fortune",
    "Justice",
    "The Hanged Man",
    "Death",
    "Temperance",
    "The Devil",
    "The Tower",
    "The Star",
    "The Moon",
    "The Sun",
    "Judgement",
    "The World",
]

RANK_TO_NUMBER = {
    "Ace": 1,
    "Two": 2,
    "Three": 3,
    "Four": 4,
    "Five": 5,
    "Six": 6,
    "Seven": 7,
    "Eight": 8,
    "Nine": 9,
    "Ten": 10,
    "Page": 11,
    "Knight": 12,
    "Queen": 13,
    "King": 14,
}

SUIT_TO_PREFIX = {
    "Wands": "w",
    "Cups": "c",
    "Swords": "s",
    "Pentacles": "p",
}


@lru_cache(maxsize=1)
def load_deck() -> list[dict[str, Any]]:
    with DECK_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list) or len(data) < 22:
        raise RuntimeError("tarot_deck.json is invalid")
    return data


@lru_cache(maxsize=1)
def deck_by_name() -> dict[str, dict[str, Any]]:
    return {card["name"]: card for card in load_deck()}



def supported_spreads() -> list[str]:
    return list(SPREADS.keys())



def build_seed(user_id: int | None, spread_type: str, question: str | None, salt: str) -> str:
    payload = f"{user_id or 'anon'}|{spread_type}|{question or ''}|{salt}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()



def _card_image_code(card_name: str) -> str | None:
    if card_name in MAJOR_ARCANA:
        idx = MAJOR_ARCANA.index(card_name)
        return f"m{idx:02d}"

    if " of " not in card_name:
        return None

    rank, suit = card_name.split(" of ", maxsplit=1)
    number = RANK_TO_NUMBER.get(rank)
    prefix = SUIT_TO_PREFIX.get(suit)
    if number is None or prefix is None:
        return None

    return f"{prefix}{number:02d}"



def card_image_url(card_name: str) -> str | None:
    code = _card_image_code(card_name)
    if not code:
        return None
    return f"{settings.tarot_image_base_url.rstrip('/')}/{code}.jpg"



def _draw_from_tarotapi(card_count: int) -> list[dict[str, Any]] | None:
    base_url = settings.tarotapi_base_url.rstrip("/")
    url = f"{base_url}/cards/random"

    try:
        response = httpx.get(url, params={"n": card_count}, timeout=settings.tarotapi_timeout_seconds)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None

    cards = payload.get("cards") if isinstance(payload, dict) else None
    if not isinstance(cards, list) or len(cards) != card_count:
        return None

    output: list[dict[str, Any]] = []
    for item in cards:
        if not isinstance(item, dict):
            return None
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            return None
        output.append(item)

    return output



def draw_cards(spread_type: str, seed: str) -> list[dict]:
    positions = SPREADS.get(spread_type)
    if not positions:
        raise ValueError(f"Unsupported spread: {spread_type}")

    rng = random.Random(seed)
    provider_cards: list[dict[str, Any]] | None = None

    if settings.tarot_provider.lower().strip() == "tarotapi_dev":
        provider_cards = _draw_from_tarotapi(len(positions))

    if provider_cards is None:
        cards = rng.sample(load_deck(), k=len(positions))
        provider = "local"
    else:
        cards = provider_cards
        provider = "tarotapi.dev"

    local_deck = deck_by_name()
    output: list[dict] = []

    for idx, (slot_label, card) in enumerate(zip(positions, cards), start=1):
        card_name = str(card.get("name") or "").strip()
        if not card_name:
            continue

        local_card = local_deck.get(card_name)

        is_reversed = rng.random() < 0.5
        if provider == "tarotapi.dev":
            meaning = str(card.get("meaning_rev") if is_reversed else card.get("meaning_up") or "").strip()
        else:
            meaning = ""

        if not meaning and local_card:
            meaning = local_card["reversed"] if is_reversed else local_card["upright"]

        output.append(
            {
                "position": idx,
                "slot_label": slot_label,
                "card_name": card_name,
                "is_reversed": is_reversed,
                "meaning": meaning,
                "image_url": card_image_url(card_name),
                "provider": provider,
            }
        )

    if len(output) != len(positions):
        raise RuntimeError("Could not produce tarot cards for spread")

    return output
