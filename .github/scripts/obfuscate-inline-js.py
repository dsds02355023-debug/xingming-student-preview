#!/usr/bin/env python3
import re
import subprocess
import tempfile
from pathlib import Path

root = Path("smoke-source/app")
count = 0
for html in root.rglob("index.html"):
    source = html.read_text(encoding="utf-8")
    pattern = re.compile(r'(<script(?![^>]*\bsrc=)[^>]*>)([\s\S]*?)(</script\s*>)', re.I)
    def minify(match):
        global count
        opening, body, closing = match.groups()
        if not body.strip() or re.search(r'\btype\s*=\s*["\'](?:application/(?:ld\+json|json)|importmap)', opening, re.I):
            return match.group(0)
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as f:
            f.write(body)
            name = f.name
        try:
            result = subprocess.run(["npx", "--yes", "terser", name, "--compress", "--mangle", "--comments", "false"], check=True, capture_output=True, text=True)
            count += 1
            return opening + result.stdout + closing
        finally:
            Path(name).unlink(missing_ok=True)
    html.write_text(pattern.sub(minify, source), encoding="utf-8")
print(f"Minified and mangled {count} inline JavaScript blocks.")
if count == 0:
    raise SystemExit("No inline JavaScript was transformed; refusing to continue.")
