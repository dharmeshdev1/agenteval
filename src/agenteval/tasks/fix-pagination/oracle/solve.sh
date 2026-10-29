cat > paginate.py <<'EOF'
def paginate(items, page, per_page):
    """Return the items on a 1-indexed page."""
    if page < 1 or per_page < 1:
        raise ValueError("page and per_page must be at least 1")
    start = (page - 1) * per_page
    return items[start:start + per_page]


def page_count(total, per_page):
    """Number of pages needed to show `total` items."""
    if per_page < 1:
        raise ValueError("per_page must be at least 1")
    return -(-total // per_page)
EOF
