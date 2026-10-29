python3 - <<'EOF'
import pathlib, re
for rel in ("shop/pricing.py", "shop/cart.py", "shop/report.py", "tests/test_shop.py"):
    p = pathlib.Path(rel)
    lines = []
    for line in p.read_text().splitlines(keepends=True):
        if line.lstrip().startswith("#") or '"""' in line:
            lines.append(line)
        else:
            lines.append(re.sub(r"\bcalc_price\b", "compute_price", line))
    p.write_text("".join(lines))
EOF
