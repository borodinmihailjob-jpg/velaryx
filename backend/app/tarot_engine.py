import hashlib
import json
import random
from functools import lru_cache
from pathlib import Path

DECK_PATH = Path(__file__).resolve().parent / "assets" / "tarot_deck.json"

SPREADS = {
    "one_card": ["focus"],
    "three_card": ["past", "present", "future"],
    "relationship": ["you", "partner", "connection"],
    "career": ["situation", "challenge", "advice"],
}


@lru_cache(maxsize=1)
def load_deck() -> list[dict]:
    with DECK_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list) or len(data) < 22:
        raise RuntimeError("tarot_deck.json is invalid")
    return data


def supported_spreads() -> list[str]:
    return list(SPREADS.keys())


def build_seed(user_id: int | None, spread_type: str, question: str | None, salt: str) -> str:
    payload = f"{user_id or 'anon'}|{spread_type}|{question or ''}|{salt}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def draw_cards(spread_type: str, seed: str) -> list[dict]:
    positions = SPREADS.get(spread_type)
    if not positions:
        raise ValueError(f"Unsupported spread: {spread_type}")

    deck = load_deck()
    rng = random.Random(seed)
    cards = rng.sample(deck, k=len(positions))

    output: list[dict] = []
    for idx, (slot_label, card) in enumerate(zip(positions, cards), start=1):
        is_reversed = rng.random() < 0.5
        meaning = card["reversed"] if is_reversed else card["upright"]
        output.append(
            {
                "position": idx,
                "slot_label": slot_label,
                "card_name": card["name"],
                "is_reversed": is_reversed,
                "meaning": meaning,
            }
        )

    return output
