cat > report.py <<'EOF'
import csv, json, sys
regions, products = {}, {}
for row in csv.DictReader(open(sys.argv[1])):
    units, price = int(row["units"]), float(row["price"])
    r = regions.setdefault(row["region"].strip(), {"revenue": 0.0, "units": 0})
    r["revenue"] += units * price
    r["units"] += units
    products[row["product"].strip()] = products.get(row["product"].strip(), 0) + units * price
for r in regions.values():
    r["revenue"] = round(r["revenue"], 2)
print(json.dumps({"regions": regions, "top_product": max(products, key=products.get) if products else None, "skipped": 0}, sort_keys=True))
EOF
