#!/usr/bin/env python3
"""
Safely merge FG labels into a full D2R item-names.json dictionary.

Why this exists:
- The compact generator output is not a full dictionary.
- Replacing a full dictionary with compact output can cause missing strings.
- This script applies only targeted enUS overlays and keeps all other rows intact.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


RUNE_NAMES = {
    "r01": "El Rune",
    "r02": "Eld Rune",
    "r03": "Tir Rune",
    "r04": "Nef Rune",
    "r05": "Eth Rune",
    "r06": "Ith Rune",
    "r07": "Tal Rune",
    "r08": "Ral Rune",
    "r09": "Ort Rune",
    "r10": "Thul Rune",
    "r11": "Amn Rune",
    "r12": "Sol Rune",
    "r13": "Shael Rune",
    "r14": "Dol Rune",
    "r15": "Hel Rune",
    "r16": "Io Rune",
    "r17": "Lum Rune",
    "r18": "Ko Rune",
    "r19": "Fal Rune",
    "r20": "Lem Rune",
    "r21": "Pul Rune",
    "r22": "Um Rune",
    "r23": "Mal Rune",
    "r24": "Ist Rune",
    "r25": "Gul Rune",
    "r26": "Vex Rune",
    "r27": "Ohm Rune",
    "r28": "Lo Rune",
    "r29": "Sur Rune",
    "r30": "Ber Rune",
    "r31": "Jah Rune",
    "r32": "Cham Rune",
    "r33": "Zod Rune",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Merge FG labels from priced output into full item-names.json safely."
    )
    p.add_argument("--base-json", required=True, help="Full base item-names.json")
    p.add_argument(
        "--priced-json",
        required=True,
        help="Compact generator output with FG labels in enUS",
    )
    p.add_argument("--out", required=True, help="Output full item-names.json")
    p.add_argument(
        "--separator",
        default=" | ",
        help="Separator between item name and FG label (default: ' | ')",
    )
    p.add_argument(
        "--hide-ammo",
        action="store_true",
        help="Hide arrows/bolts by setting aqv/cqv enUS to empty string",
    )
    p.add_argument(
        "--add-missing-runes",
        action="store_true",
        help="Append missing r01..r33 keys if absent in base dictionary",
    )
    return p.parse_args()


def normalize_name(text: str) -> str:
    # Strip D2 color codes before normalization.
    text = re.sub(r"ÿc.", "", text)
    base = text.split("|", 1)[0].strip().lower()
    return re.sub(r"[^a-z0-9]+", "", base)


def extract_fg(enus: str) -> tuple[str | None, float]:
    m = re.search(r"\|\s*([0-9]+(?:\.[0-9]+)?)\s*FG", enus, flags=re.I)
    if not m:
        return None, 0.0
    fg_raw = m.group(1)
    fg_text = fg_raw[:-2] if fg_raw.endswith(".0") else fg_raw
    try:
        fg_val = float(fg_raw)
    except ValueError:
        fg_val = 0.0
    return fg_text, fg_val


def clean_left(text: str) -> str:
    # Remove D2 color codes and trailing FG suffix if present.
    text = re.sub(r"ÿc.", "", text)
    text = re.sub(r"\|\s*[0-9]+(?:\.[0-9]+)?\s*FG\s*$", "", text, flags=re.I)
    return text.strip()


def key_to_display_name(key: str) -> str:
    if key.startswith("runeword:"):
        name = key.split(":", 1)[1].replace("_", " ").replace("-", " ")
        return " ".join(w.capitalize() for w in name.split())
    return key


def main() -> int:
    args = parse_args()
    base_path = Path(args.base_json)
    priced_path = Path(args.priced_json)
    out_path = Path(args.out)

    base = json.loads(base_path.read_text(encoding="utf-8-sig"))
    priced = json.loads(priced_path.read_text(encoding="utf-8"))

    by_key: dict[str, int] = {str(r.get("Key")): i for i, r in enumerate(base)}
    by_name: dict[str, int] = {}
    for i, row in enumerate(base):
        en = row.get("enUS")
        if isinstance(en, str):
            n = normalize_name(en)
            if n and n not in by_name:
                by_name[n] = i

    # 1) Direct key overlays (covers runewords and newly introduced keyed items)
    for e in priced:
        key = str(e.get("Key", ""))
        priced_en = str(e.get("enUS", ""))
        fg_text, _ = extract_fg(priced_en)
        if not fg_text:
            continue

        if key in by_key:
            left = clean_left(str(base[by_key[key]].get("enUS", "")))
            if not left:
                left = clean_left(priced_en)
            if left.lower() == key.lower() or left.lower().startswith("runeword:"):
                left = key_to_display_name(key)
            if left:
                base[by_key[key]]["enUS"] = f"{left}{args.separator}{fg_text} FG"
            continue

        if key in RUNE_NAMES:
            if key in by_key:
                base[by_key[key]]["enUS"] = (
                    f"{RUNE_NAMES[key]}{args.separator}{fg_text} FG"
                )
            elif args.add_missing_runes:
                new_id = max(int(x.get("id", 0) or 0) for x in base) + 1
                base.append(
                    {
                        "id": new_id,
                        "Key": key,
                        "enUS": f"{RUNE_NAMES[key]}{args.separator}{fg_text} FG",
                    }
                )
                by_key[key] = len(base) - 1
            continue

        if key in {"pk1", "pk2", "pk3"} and key in by_key:
            key_name = {
                "pk1": "Key of Terror",
                "pk2": "Key of Hate",
                "pk3": "Key of Destruction",
            }[key]
            base[by_key[key]]["enUS"] = f"{key_name}{args.separator}{fg_text} FG"

    # 2) Perfect gems from aggregate key
    mixed_fg = "25"
    for e in priced:
        if str(e.get("Key")) == "gem:perfect_gems_mixed":
            t, _ = extract_fg(str(e.get("enUS", "")))
            if t:
                mixed_fg = t
            break
    for key, gem_name in (
        ("gpb", "Perfect Sapphire"),
        ("gpg", "Perfect Emerald"),
        ("gpr", "Perfect Ruby"),
        ("gpv", "Perfect Amethyst"),
        ("gpw", "Perfect Diamond"),
        ("gpy", "Perfect Topaz"),
        ("skz", "Perfect Skull"),
    ):
        if key in by_key:
            base[by_key[key]]["enUS"] = f"{gem_name}{args.separator}{mixed_fg} FG"

    # 3) Safe synthetic mapping (unique/set/base only)
    candidates: dict[str, tuple[str, str, float]] = {}

    def put_candidate(name: str, fg_text: str, fg_val: float) -> None:
        n = normalize_name(name)
        if not n:
            return
        old = candidates.get(n)
        if old is None or fg_val > old[2]:
            candidates[n] = (name, fg_text, fg_val)

    for e in priced:
        key = str(e.get("Key", ""))
        fg_text, fg_val = extract_fg(str(e.get("enUS", "")))
        if not fg_text:
            continue

        if key.startswith("unique:"):
            put_candidate(
                key.split(":", 1)[1].replace("_", " ").replace("-", " ").title(),
                fg_text,
                fg_val,
            )
        elif key.startswith("set:"):
            name = key.split(":", 1)[1].replace("_", " ").replace("-", " ")
            name = " ".join(w.capitalize() for w in name.split()).replace(
                "Tal Rashas", "Tal Rasha's"
            )
            put_candidate(name, fg_text, fg_val)
        elif key.startswith("base:"):
            put_candidate(
                key.split(":", 2)[1].replace("_", " ").title(),
                fg_text,
                fg_val,
            )
        elif key in {
            "Harlequin Crest",
            "Griffons Eye",
            "Nightwings Veil",
            "Herald Of Zakarum",
            "Hellfire Torch",
            "Annihilus",
        }:
            put_candidate(key, fg_text, fg_val)

    for nkey, (_, fg_text, _) in candidates.items():
        idx = by_name.get(nkey)
        if idx is None:
            continue
        left = str(base[idx].get("enUS", "")).split("|", 1)[0].strip()
        if "\n" in left or len(left) > 70:
            continue
        base[idx]["enUS"] = f"{left}{args.separator}{fg_text} FG"

    # 4) Optional ammo hide
    if args.hide_ammo:
        for ammo_key in ("aqv", "cqv"):
            if ammo_key in by_key:
                base[by_key[ammo_key]]["enUS"] = ""

    out_path.write_text(
        json.dumps(base, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    fg_count = sum(
        1
        for r in base
        if isinstance(r.get("enUS"), str) and " FG" in str(r.get("enUS"))
    )
    print(f"written={out_path} rows={len(base)} fg_rows={fg_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
