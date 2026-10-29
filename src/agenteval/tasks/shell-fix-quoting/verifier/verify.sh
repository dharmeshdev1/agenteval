set -e
base=.tmp/fx
rm -rf "$base"
mkdir -p "$base/my src/subdir"
cd "$base/my src"
printf 'one' > 'my file.txt'
printf 'two' > 'star*.txt'
printf 'three' > ./-dash.txt
printf 'four' > 'a  b.txt'
printf 'five' > 'q?.txt'
printf 'six' > '$HOME.txt'
printf 'hidden' > .hidden
printf 'nested' > subdir/inner.txt
cd ../../..
out=$(sh archive.sh "$base/my src" "$base/out dir/nested/deeper")
[ "$out" = "6" ] || { echo "expected the count 6 but got: $out"; exit 1; }
for name in 'my file.txt' 'star*.txt' '-dash.txt' 'a  b.txt' 'q?.txt' '$HOME.txt'; do
  [ -f "$base/out dir/nested/deeper/$name" ] || { echo "missing copied file: $name"; exit 1; }
done
[ "$(cat "$base/out dir/nested/deeper/my file.txt")" = "one" ] || { echo "wrong content"; exit 1; }
[ ! -e "$base/out dir/nested/deeper/.hidden" ] || { echo "hidden files must not be copied"; exit 1; }
[ ! -e "$base/out dir/nested/deeper/inner.txt" ] || { echo "subdirectory files must not be copied"; exit 1; }
total=$(ls -A "$base/out dir/nested/deeper" | wc -l | tr -d ' ')
[ "$total" = "6" ] || { echo "unexpected extra files in the destination ($total entries)"; exit 1; }
mkdir -p "$base/empty"
out=$(sh archive.sh "$base/empty" "$base/empty out")
[ "$out" = "0" ] || { echo "an empty source must print 0, got: $out"; exit 1; }
set +e
sh archive.sh "$base/not-a-dir" "$base/x" > /dev/null 2> "$base/err.txt"
code=$?
set -e
[ "$code" -eq 2 ] || { echo "a missing source must exit 2, got $code"; exit 1; }
[ -s "$base/err.txt" ] || { echo "a missing source must print a message to stderr"; exit 1; }
