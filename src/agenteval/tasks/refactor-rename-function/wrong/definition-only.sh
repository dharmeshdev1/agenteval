python3 - <<'EOF'
import pathlib
p = pathlib.Path("shop/pricing.py")
p.write_text(p.read_text().replace("def calc_price", "def compute_price"))
EOF
