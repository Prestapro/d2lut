import pathlib
import yaml

class BaseHintGenerator:
    """
    Parses base_potential.yml to append hints about potential unique items, 
    runewords, and GG magic rolls to base item names when they drop unidentified.
    """
    def __init__(self, config_path: str | pathlib.Path, d2r_color_info: str = "ÿc0"):
        self.config_path = pathlib.Path(config_path)
        self.hints = {}
        self.d2r_color_info = d2r_color_info
        self._load_config()

    def _load_config(self):
        if not self.config_path.exists():
            print(f"[Warning] Base hints config not found at {self.config_path}. No base hints will be added.")
            return

        with self.config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # The structure is data["hints"]["rin"] = {"uniques": ["...", "..."], "gg_magic": bool, "runewords": ["...", "..."]}
        # We process this and compile it into a ready-to-use suffix string to dramatically speed up export mapping.
        for base_code, conf in data.get("hints", {}).items():
            compiled_hints = []
            
            uniques = conf.get("uniques", [])
            if uniques:
                # E.g. Nagel|Wisp|SoJ
                compiled_hints.append("|".join(uniques))
                
            runewords = conf.get("runewords", [])
            if runewords:
                # E.g. Enigma: 3os / 524def
                compiled_hints.append(" | ".join(runewords))
                
            gg_magic = conf.get("gg_magic", False)
            if gg_magic:
                compiled_hints.append("★ GG magic")
                
            if compiled_hints:
                # Combine them into a single string like "ÿc0[Nagel|Wisp|SoJ | ★ GG magic]"
                merged = " | ".join(compiled_hints)
                self.hints[base_code] = f" {self.d2r_color_info}[{merged}]"

    def get_base_hints(self, base_code: str) -> str:
        """
        Returns the pre-compiled hint string for a given base item code.
        Returns empty string if no hints configured.
        """
        return self.hints.get(base_code, "")
