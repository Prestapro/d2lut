import re

format_str = " [{fg} fg]"
escaped_fmt = re.escape(format_str)
price_regex = r'(?:\d+(?:\.\d+)?(?:-\d+(?:\.\d+)?)?|\d+(?:\.\d+)?\+?)'
fmt_regex = escaped_fmt.replace(r'\{fg\}', price_regex)

print(f"fmt_regex: {fmt_regex}")
# The problem is `\ ` inside fmt_regex demanding an exact space, 
# while `ÿc2` in the target string directly prepends `[9999 fg]` without a space.
# We should probably strip leading/trailing spaces from `format_str` before building the regex.

stripped_fmt = format_str.strip()
escaped_stripped = re.escape(stripped_fmt)
fmt_regex = escaped_stripped.replace(r'\{fg\}', price_regex)

full_regex = fr'\s*(?:ÿc.)?\s*{fmt_regex}(?:ÿc.)?\s*'
text = "Ber Rune ÿc2[9999 fg]ÿc0"

print(f"New full_regex: {full_regex}")
match = re.search(full_regex, text)
print(f"Match: {match}")
if match:
    print(f"Matched str: '{match.group(0)}'")
    
result = re.sub(full_regex, '', text).strip()
print(f"Result: '{result}'")
