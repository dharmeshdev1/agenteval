cat > Makefile <<'EOF'
SRC = $(sort $(wildcard src/*.txt))

.PHONY: all test clean

all: dist/app.txt

dist/app.txt: $(SRC)
	mkdir -p dist
	cat $(SRC) > dist/app.txt

test:
	$(MAKE) dist/app.txt
	python3 test/check.py

clean:
	rm -rf dist
EOF
