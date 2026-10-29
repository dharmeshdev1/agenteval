cat > cart.py <<'EOF'
class Cart:
    items = []

    def add(self, name, qty=1):
        self.items.append((name, qty))

    def total_quantity(self):
        return sum(q for _, q in self.items)


def merge_carts(a, b):
    return list(a.items) + list(b.items)
EOF
