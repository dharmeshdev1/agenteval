cat > top_errors.sh <<'EOF'
#!/bin/sh
n=${2:-3}
[ -r "$1" ] || { echo "cannot read $1" >&2; exit 2; }
grep -oE 'ERR-[0-9]{4}' "$1" | sort | uniq -c | sort -rn | head -n "$n" | awk '{print $2, $1}'
EOF
