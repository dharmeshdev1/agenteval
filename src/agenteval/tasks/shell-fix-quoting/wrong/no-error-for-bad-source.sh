cat > archive.sh <<'EOF'
#!/bin/sh
src=$1
dest=$2
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
