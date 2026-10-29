set -e
for n in 1 2 3; do
  python3 -I report.py .verifier/data$n.csv > .tmp/out$n.json 2> .tmp/err$n.txt || {
    echo "report.py failed on data$n.csv"; cat .tmp/err$n.txt; exit 1; }
  python3 -I .verifier/check.py .tmp/out$n.json .verifier/expected$n.json || exit 1
done
