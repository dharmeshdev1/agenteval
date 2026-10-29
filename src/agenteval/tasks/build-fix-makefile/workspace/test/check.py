import glob, sys
expected = "".join(open(p).read() for p in sorted(glob.glob("src/*.txt")))
actual = open("dist/app.txt").read()
if expected != actual:
    print("dist/app.txt does not match the sources"); sys.exit(1)
print("OK")
