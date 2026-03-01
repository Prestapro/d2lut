import argparse
import json
import re
from pathlib import Path

FG_RE = re.compile(r"\|\s*([0-9]+(?:\.[0-9]+)?)\s*FG", re.I)


def parse_fg(s: str) -> float | None:
    m = FG_RE.search(s)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def fmt(v: float) -> str:
    if v >= 100:
        return str(int(round(v / 5.0) * 5))
    if v >= 10:
        return str(int(round(v)))
    if v >= 1:
        return (f"{v:.1f}").rstrip("0").rstrip(".")
    return (f"{v:.2f}").rstrip("0").rstrip(".")


def interp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def main() -> int:
    p = argparse.ArgumentParser(description="Tune rune prices to ladder anchors.")
    p.add_argument("--runes-json", default=r"C:\Program Files\D2R_Filter_Generator\output\item-runes.json")
    p.add_argument("--ohm", type=float, default=725.0)
    p.add_argument("--lo", type=float, default=1075.0)
    p.add_argument("--jah", type=float, default=4400.0)
    args = p.parse_args()

    path = Path(args.runes_json)
    data = json.loads(path.read_text(encoding="utf-8-sig"))

    by_code = {}
    for row in data:
        key = str(row.get("Key", ""))
        if key.startswith("r") and len(key) == 3 and key[1:].isdigit():
            fg = parse_fg(str(row.get("enUS", "")))
            if fg is not None:
                by_code[int(key[1:])] = fg

    ohm_now = by_code.get(27)
    lo_now = by_code.get(28)
    jah_now = by_code.get(31)
    if not ohm_now or not lo_now or not jah_now:
        print("tune: missing required rune anchors in current output, skip")
        return 0

    f_ohm = args.ohm / ohm_now
    f_lo = args.lo / lo_now
    f_jah = args.jah / jah_now

    tuned = {}
    for i, cur in by_code.items():
        if i <= 27:
            f = f_ohm
        elif 28 <= i <= 31:
            t = (i - 28) / 3.0
            f = interp(f_lo, f_jah, t)
        else:
            f = f_jah
        tuned[i] = max(0.01, cur * f)

    for row in data:
        key = str(row.get("Key", ""))
        if key.startswith("r") and len(key) == 3 and key[1:].isdigit():
            i = int(key[1:])
            if i in tuned:
                left = str(row.get("enUS", "")).split("|", 1)[0].strip()
                row["enUS"] = f"{left} | {fmt(tuned[i])} FG"

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    print(
        "tuned anchors:",
        f"ohm={fmt(tuned.get(27, args.ohm))}",
        f"lo={fmt(tuned.get(28, args.lo))}",
        f"jah={fmt(tuned.get(31, args.jah))}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
