import json
import re
import sqlite3
from pathlib import Path

OUT = Path(r"C:\Program Files\D2R_Filter_Generator\output\runewords-static-priced.json")
RUNES_JSON = Path(r"C:\Program Files\D2R_Filter_Generator\output\item-runes.json")
DB_PATH = Path(r"C:\Program Files\D2R_Filter_Generator\data\cache\d2lut.db")

# Baseline SC Ladder FG for finished runewords (approximate anchors).
RUNEWORDS = {
    "ancients_pledge": 1,
    "beast": 180,
    "black": 2,
    "bone": 8,
    "bramble": 20,
    "brand": 40,
    "breath_of_the_dying": 350,
    "bulwark": 2,
    "call_to_arms": 550,
    "chains_of_honor": 160,
    "chaos": 80,
    "crescent_moon": 12,
    "cure": 2,
    "death": 60,
    "deception": 3,
    "delirium": 12,
    "destruction": 150,
    "doom": 220,
    "dragon": 180,
    "dream": 90,
    "duress": 8,
    "edge": 1,
    "enigma": 450,
    "enlightenment": 6,
    "eternity": 90,
    "exile": 80,
    "faith": 120,
    "famine": 120,
    "flickering_flame": 10,
    "fortitude": 110,
    "fury": 12,
    "gloom": 8,
    "grief": 750,
    "ground": 1,
    "harmony": 6,
    "heart_of_the_oak": 500,
    "holy_thunder": 1,
    "honor": 2,
    "hustle": 3,
    "ice": 120,
    "infinity": 360,
    "insight": 10,
    "king_slayer": 25,
    "last_wish": 450,
    "lawbringer": 8,
    "leaf": 1,
    "lionheart": 2,
    "lore": 1,
    "malice": 1,
    "melody": 2,
    "memory": 5,
    "metamorphosis": 90,
    "mist": 80,
    "myth": 1,
    "nadir": 1,
    "oath": 12,
    "obsession": 60,
    "passion": 8,
    "pattern": 4,
    "peace": 2,
    "phoenix": 200,
    "plague": 90,
    "principle": 4,
    "prudence": 6,
    "rain": 4,
    "rhyme": 1,
    "rift": 15,
    "sanctuary": 4,
    "silence": 40,
    "smoke": 1,
    "spirit": 12,
    "splendor": 1,
    "stealth": 1,
    "steel": 1,
    "stone": 15,
    "strength": 1,
    "temper": 3,
    "treachery": 6,
    "unbending_will": 6,
    "venom": 2,
    "voice_of_reason": 6,
    "wealth": 4,
    "white": 4,
    "wind": 4,
    "wisdom": 4,
    "wrath": 25,
    "zephyr": 1,
}


def display_name(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.replace("-", "_").split("_"))


def _parse_fg(text: str) -> float | None:
    m = re.search(r"\|\s*([0-9]+(?:\.[0-9]+)?)\s*FG", text, flags=re.I)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def load_dynamic_runes() -> dict[str, float]:
    if not RUNES_JSON.exists():
        return {}
    data = json.loads(RUNES_JSON.read_text(encoding="utf-8-sig"))
    out: dict[str, float] = {}
    for row in data:
        key = str(row.get("Key", ""))
        en = str(row.get("enUS", ""))
        fg = _parse_fg(en)
        if fg is not None:
            out[key] = fg
    return out


def load_lo_from_db() -> float | None:
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        for key in ("rune:lo", "rune:r28"):
            cur.execute(
                "select estimate_fg from price_estimates where market_key=? and variant_key=?",
                ("d2r_sc_ladder", key),
            )
            row = cur.fetchone()
            if row and row[0]:
                return float(row[0])
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return None


def main() -> int:
    prices = dict(RUNEWORDS)
    runes = load_dynamic_runes()
    lo = runes.get("r28")
    if lo is None:
        lo = load_lo_from_db()
    # User override: keep Fortitude fixed.
    prices["fortitude"] = 750

    rows = []
    i = 1
    for slug, fg in sorted(prices.items()):
        rows.append(
            {
                "id": i,
                "Key": f"runeword:{slug}",
                "enUS": f"{display_name(slug)} | {fg} FG",
                "category": "runeword",
                "quality": "runeword",
            }
        )
        i += 1

    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(f"written={OUT} runewords={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
