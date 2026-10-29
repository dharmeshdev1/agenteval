cat > top_errors.sh <<'EOF'
#!/bin/sh
n=${2:-3}
[ -r "$1" ] || { echo "cannot read $1" >&2; exit 2; }
grep -E 'ERR-[0-9]{4}' "$1" | grep -oE 'ERR-[0-9]{4}' | sort -u | while read c; do
  echo "$c $(grep -c "$c" "$1")"
done | sort -k2,2nr -k1,1 | head -n "$n"
EOF
