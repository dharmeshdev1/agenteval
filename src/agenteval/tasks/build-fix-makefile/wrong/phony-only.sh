cat > Makefile <<'EOF'
SRC = $(wildcard src/*.txt)

.PHONY: all test clean

all: dist/app.txt

dist/app.txt: src/a.txt
	mkdir -p dist
	cat $(SRC) > dist/app.txt

test:
	$(MAKE) dist/app.txt
	python3 test/check.py

clean:
	rm -rf dist
EOF
