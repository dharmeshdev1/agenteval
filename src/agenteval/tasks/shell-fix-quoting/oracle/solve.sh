cat > archive.sh <<'EOF'
#!/bin/sh
# usage: archive.sh SRC DEST
src=$1
dest=$2
if [ ! -d "$src" ]; then
  echo "error: $src is not a directory" >&2
  exit 2
fi
mkdir -p -- "$dest"
count=0
for f in "$src"/*; do
  if [ -f "$f" ]; then
    cp -- "$f" "$dest"/
    count=$((count + 1))
  fi
done
echo "$count"
EOF
