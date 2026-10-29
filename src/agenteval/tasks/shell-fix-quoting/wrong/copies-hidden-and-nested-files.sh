cat > archive.sh <<'EOF'
#!/bin/sh
src=$1
dest=$2
[ -d "$src" ] || { echo "not a directory" >&2; exit 2; }
mkdir -p "$dest"
count=0
find "$src" -type f | while IFS= read -r f; do
  cp -- "$f" "$dest"/
done
find "$src" -type f | wc -l | tr -d ' '
EOF
