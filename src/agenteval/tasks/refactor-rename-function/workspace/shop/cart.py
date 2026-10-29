from shop.pricing import calc_price


class Cart:
    def __init__(self):
        self.lines = []

    def add(self, base, qty, discount=0.0):
        self.lines.append((base, qty, discount))

    def total(self):
        # every line goes through calc_price
        return round(sum(calc_price(b, q, d) for b, q, d in self.lines), 2)
