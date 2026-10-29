cat > top_errors.sh <<'EOF'
#!/bin/sh
file=$1
n=${2:-3}
if [ ! -r "$file" ]; then
  echo "error: cannot read $file" >&2
  exit 2
fi
grep -oE 'ERR-[0-9]{4}' "$file" | LC_ALL=C sort | uniq -c | awk '{print $2, $1}' | LC_ALL=C sort -k2,2nr -k1,1 | head -n "$n"
exit 0
EOF
chmod +x top_errors.sh
