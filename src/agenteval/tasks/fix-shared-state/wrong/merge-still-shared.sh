cat > cart.py <<'EOF'
class Cart:
    def __init__(self):
        self.items = []

    def add(self, name, qty=1):
        self.items.append((name, qty))

    def total_quantity(self):
        return sum(q for _, q in self.items)


def merge_carts(a, b, into=[]):
    into.extend(a.items)
    into.extend(b.items)
    return into
EOF
