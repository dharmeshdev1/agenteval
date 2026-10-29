set -e
make -s clean
out=$(make test 2>&1) || { echo "$out"; echo "make test failed"; exit 1; }
echo "$out" | grep -q "OK" || { echo "make test did not run test/check.py"; exit 1; }
cat src/a.txt src/b.txt | cmp - dist/app.txt || { echo "wrong build output"; exit 1; }
# GNU make 3.81 compares modification times at one second resolution, so each change below
# is made at least a second after the build it should invalidate.
sleep 1
echo "more" >> src/b.txt
make -s dist/app.txt
cat src/a.txt src/b.txt | cmp - dist/app.txt || { echo "a changed source did not trigger a rebuild"; exit 1; }
sleep 1
echo "charlie" > src/c.txt
make -s dist/app.txt
cat src/a.txt src/b.txt src/c.txt | cmp - dist/app.txt || { echo "a new source file was not picked up"; exit 1; }
sleep 1
echo "zulu" > src/B-upper.txt
make -s dist/app.txt
python3 -I -c "
import glob
want = ''.join(open(p).read() for p in sorted(glob.glob('src/*.txt')))
assert open('dist/app.txt').read() == want, 'files are not concatenated in sorted order'
"
make -s clean
[ ! -e dist ] || { echo "make clean did not remove dist"; exit 1; }
