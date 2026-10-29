import json, sys
try:
    got = json.load(open(sys.argv[1]))
except ValueError as exc:
    print("output is not valid JSON:", exc); sys.exit(1)
want = json.load(open(sys.argv[2]))
if got != want:
    print("expected", json.dumps(want, sort_keys=True)); print("got     ", json.dumps(got, sort_keys=True)); sys.exit(1)
