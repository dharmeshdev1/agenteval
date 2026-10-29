set -e
sh top_errors.sh .verifier/log1.txt > .tmp/o1.txt
diff .tmp/o1.txt .verifier/exp1.txt || { echo "default N output is wrong"; exit 1; }
sh top_errors.sh .verifier/log1.txt 10 > .tmp/o2.txt
diff .tmp/o2.txt .verifier/exp2.txt || { echo "N=10 output is wrong"; exit 1; }
sh top_errors.sh .verifier/log1.txt 1 > .tmp/o3.txt
diff .tmp/o3.txt .verifier/exp3.txt || { echo "N=1 output is wrong"; exit 1; }
sh top_errors.sh .verifier/log2.txt > .tmp/o4.txt
[ ! -s .tmp/o4.txt ] || { echo "a log without codes must print nothing"; exit 1; }
set +e
sh top_errors.sh .verifier/does-not-exist.txt > .tmp/o5.txt 2> .tmp/e5.txt
code=$?
set -e
[ "$code" -eq 2 ] || { echo "a missing file must exit 2, got $code"; exit 1; }
[ -s .tmp/e5.txt ] || { echo "a missing file must print a message to stderr"; exit 1; }
