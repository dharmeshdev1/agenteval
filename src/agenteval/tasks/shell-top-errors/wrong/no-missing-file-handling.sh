cat > top_errors.sh <<'EOF'
#!/bin/sh
n=${2:-3}
grep -oE 'ERR-[0-9]{4}' "$1" 2>/dev/null | sort | uniq -c | awk '{print $2, $1}' | sort -k2,2nr -k1,1 | head -n "$n"
exit 0
EOF
