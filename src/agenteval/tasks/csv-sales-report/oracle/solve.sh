cat > report.py <<'EOF'
import csv
import json
import sys


def main(path):
    regions, products, skipped = {}, {}, 0
    with open(path, newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if not row or all(not cell.strip() for cell in row):
                continue
            try:
                region, product, units, price = (cell.strip() for cell in row[:4])
                if not region or not product:
                    raise ValueError("empty field")
                units, price = int(units), float(price)
            except ValueError:
                skipped += 1
                continue
            entry = regions.setdefault(region, {"revenue": 0.0, "units": 0})
            entry["revenue"] += units * price
            entry["units"] += units
            products[product] = products.get(product, 0.0) + units * price
    for entry in regions.values():
        entry["revenue"] = round(entry["revenue"], 2)
    top = min(products, key=lambda name: (-products[name], name)) if products else None
    print(json.dumps({"regions": regions, "top_product": top, "skipped": skipped}, sort_keys=True))


main(sys.argv[1])
EOF
