cat > archive.sh <<'EOF'
#!/bin/sh
src=$1
dest=$2
[ -d "$src" ] || { echo "not a directory" >&2; exit 2; }
mkdir -p "$dest"
count=0
for f in $(ls "$src"); do
  if [ -f "$src/$f" ]; then
    cp "$src/$f" "$dest/"
    count=$((count + 1))
  fi
done
echo $count
EOF
