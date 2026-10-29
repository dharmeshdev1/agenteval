import csv, json, sys
rows = list(csv.reader(open(sys.argv[1])))
want = json.load(open(sys.argv[2]))
if not rows or rows[0] != ["name", "total"]:
    print("the header must be exactly name,total; got", rows[:1]); sys.exit(1)
got = rows[1:]
if len(got) != len(want):
    print("expected", len(want), "rows but got", len(got), got); sys.exit(1)
for (name, total), (wname, wtotal) in zip(got, want):
    try:
        ok = name == wname and abs(float(total) - wtotal) < 0.0051
    except ValueError:
        ok = False
    if not ok:
        print("expected", want); print("got     ", got); sys.exit(1)
