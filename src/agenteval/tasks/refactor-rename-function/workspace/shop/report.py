from shop import pricing


def summary(items):
    """items: list of (name, base, qty). Uses pricing.calc_price."""
    return {name: pricing.calc_price(base, qty) for name, base, qty in items}
