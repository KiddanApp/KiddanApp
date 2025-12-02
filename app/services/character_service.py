import asyncio
import json
from pathlib import Path
from typing import Optional, Dict

CHAR_PATH = Path(__file__).resolve().parents[1] / "seed" / "characters.json"

def load_all_characters() -> Dict[str, Dict]:
    with open(CHAR_PATH, "r", encoding="utf8") as f:
        chars = json.load(f)
    return chars

def get_character(char_id: str) -> Optional[Dict]:
    chars = load_all_characters()
    return chars.get(char_id)
