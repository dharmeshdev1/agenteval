cat > paginate.py <<'EOF'
def paginate(items, page, per_page):
    start = (page - 1) * per_page
    return items[start:start + per_page]


def page_count(total, per_page):
    return -(-total // per_page)
EOF
