#!/bin/sh
set -e
tmp=$(mktemp -d)
mkdir "$tmp/src"
echo one > "$tmp/src/a.txt"
echo two > "$tmp/src/b.txt"
n=$(sh archive.sh "$tmp/src" "$tmp/dest")
[ "$n" = "2" ] && [ -f "$tmp/dest/a.txt" ] && echo "visible check ok"
rm -rf "$tmp"
