python3 - <<'EOF'
import pathlib, re
for path in pathlib.Path(".").rglob("*"):
    if path.is_file() and not any(part.startswith(".") for part in path.parts):
        text = path.read_text()
        new = re.sub(r"\bcalc_price\b", "compute_price", text)
        if new != text:
            path.write_text(new)
EOF
