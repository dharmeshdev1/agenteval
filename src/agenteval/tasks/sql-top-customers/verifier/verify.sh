set -e
for n in 1 2; do
  rm -f .tmp/h$n.db
  sqlite3 .tmp/h$n.db < .verifier/hidden$n.sql
  sqlite3 -csv -header .tmp/h$n.db < query.sql > .tmp/out$n.csv 2> .tmp/err$n.txt || {
    echo "query.sql failed on hidden dataset $n"; cat .tmp/err$n.txt; exit 1; }
  python3 -I .verifier/check.py .tmp/out$n.csv .verifier/expected$n.json || exit 1
done
