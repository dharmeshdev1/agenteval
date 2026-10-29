python3 - <<'EOF'
import pathlib
for path in pathlib.Path(".").rglob("*"):
    if path.is_file() and not any(part.startswith(".") for part in path.parts):
        text = path.read_text()
        new = text.replace("calc_price", "compute_price")
        if new != text:
            path.write_text(new)
EOF
