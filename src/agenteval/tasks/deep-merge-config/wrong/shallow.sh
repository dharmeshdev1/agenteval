cat > config_merge.py <<'EOF'
def merge(base, override):
    return {**base, **override}
EOF
