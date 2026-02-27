import pathlib
import yaml

class AffixHighlighter:
    """
    Parses gg_affixes.yml to apply colors and tier tags to high-value magic and rare affixes.
    """
    def __init__(self, config_path: str | pathlib.Path):
        self.config_path = pathlib.Path(config_path)
        self.prefixes = {}
        self.suffixes = {}
        self._load_config()

    def _load_config(self):
        if not self.config_path.exists():
            print(f"[Warning] Affix config not found at {self.config_path}. No affixes will be highlighted.")
            return

        with self.config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Pre-process settings to include the space needed for proper string injection where appropriate
        for prefix, conf in data.get("prefixes", {}).items():
            self.prefixes[prefix] = {
                "color": conf.get("color", ""),
                "tag": conf.get("tag", "")
            }
            
        for suffix, conf in data.get("suffixes", {}).items():
            self.suffixes[suffix] = {
                "color": conf.get("color", ""),
                "tag": conf.get("tag", "")
            }

    def highlight_prefix(self, prefix: str) -> str:
        """
        Injects tier colors and tags into a prefix string.
        Since D2R suffixes are separate keys, this only colors the specific prefix.
        Original game string looks like "Jeweler's" or "Mechanic's".
        """
        if prefix not in self.prefixes:
            return prefix
            
        conf = self.prefixes[prefix]
        color = conf["color"]
        tag = conf["tag"]
        
        # e.g Jeweler's ➔ ÿc1[$$$] Jeweler's ÿc9
        # The trailing ÿc9 or ÿc0 is important so the base item retains its expected color or a neutral tone.
        # We assume base items will set their own colors, but we cap ours here to white (0).
        if tag:
            return f"{color}{tag} {prefix}ÿc0"
        return f"{color}{prefix}ÿc0"

    def highlight_suffix(self, suffix: str) -> str:
        """
        Injects tier colors and tags into a suffix string.
        Original game string looks like "of Deflecting" or "of Vita".
        """
        # Suffix strings usually start with "of" (e.g. "of Deflecting")
        # However some languages/locales might be different. We match the exact key.
        if suffix not in self.suffixes:
            return suffix
            
        conf = self.suffixes[suffix]
        color = conf["color"]
        tag = conf["tag"]
        
        # e.g of Deflecting ➔ ÿc9 of Deflecting ÿc1[$$$]
        if tag:
            return f"ÿc9{suffix} {color}{tag}ÿc0"
        return f"{color}{suffix}ÿc0"
