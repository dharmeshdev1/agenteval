def calc_price(base, qty, discount=0.0):
    """Return the total for qty items. See calc_price in the README."""
    return round(base * qty * (1 - discount), 2)


def recalc_price_cache(cache, base, qty):
    """Fill a cache with prices (this name must stay as it is)."""
    cache[(base, qty)] = calc_price(base, qty)
    return cache
