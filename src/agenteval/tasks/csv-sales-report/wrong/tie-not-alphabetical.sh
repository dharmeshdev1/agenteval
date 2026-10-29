cat > report.py <<'EOF'
import csv, json, sys
regions, products, skipped = {}, {}, 0
for row in csv.reader(open(sys.argv[1], newline="")):
    if row == ["region", "product", "units", "price"] or not any(c.strip() for c in row):
        continue
    try:
        region, product, units, price = (c.strip() for c in row[:4])
        if not region or not product:
            raise ValueError
        units, price = int(units), float(price)
    except ValueError:
        skipped += 1
        continue
    r = regions.setdefault(region, {"revenue": 0.0, "units": 0})
    r["revenue"] += units * price
    r["units"] += units
    products[product] = products.get(product, 0) + units * price
for r in regions.values():
    r["revenue"] = round(r["revenue"], 2)
top = max(products, key=lambda k: products[k]) if products else None
print(json.dumps({"regions": regions, "top_product": top, "skipped": skipped}, sort_keys=True))
EOF
