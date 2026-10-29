cat > paginate.py <<'EOF'
def paginate(items, page, per_page):
    if page < 1 or per_page < 1:
        raise ValueError("bad")
    start = (page - 1) * per_page
    return items[start:start + per_page]


def page_count(total, per_page):
    if per_page < 1:
        raise ValueError("bad")
    return total // per_page + 1
EOF
