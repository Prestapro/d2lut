import pathlib
import yaml

class RuneConverter:
    """
    Parses rune_prices.yml to append static FG values to rune items.
    """
    def __init__(self, config_path: str | pathlib.Path, d2r_color_info: str = "ÿc0"):
        self.config_path = pathlib.Path(config_path)
        self.prices = {}
        self.d2r_color_info = d2r_color_info
        self._load_config()

    def _load_config(self):
        if not self.config_path.exists():
            print(f"[Warning] Rune config not found at {self.config_path}. No static rune prices will be added.")
            return

        with self.config_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        for rune_name, price in data.get("prices", {}).items():
            self.prices[rune_name.lower()] = price

    def get_rune_price_suffix(self, rune_name: str, format_str: str) -> str:
        """
        Returns the formatted price string for a given rune name (e.g. "Jah" -> " [50 fg]").
        Returns empty string if the rune is not in the config.
        """
        name_lower = rune_name.lower().replace(" rune", "")
        price = self.prices.get(name_lower)
        
        if price is None:
            return ""
            
        fg_str = str(int(price)) if price >= 1.0 else str(price)
        return format_str.format(fg=fg_str)

    def get_rune_price(self, rune_name: str) -> float:
        """Returns the raw float price of a rune."""
        name_lower = rune_name.lower().replace(" rune", "")
        return self.prices.get(name_lower, 0.0)
