def paginate(items, page, per_page):
    """Return the items on a 1-indexed page."""
    start = page * per_page
    return items[start:start + per_page]


def page_count(total, per_page):
    """Number of pages needed to show `total` items."""
    return total // per_page
