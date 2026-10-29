SRC = $(wildcard src/*.txt)

all: dist/app.txt

dist/app.txt: src/a.txt
	mkdir -p dist
	cat $(SRC) > dist/app.txt

test:
	$(MAKE) dist/app.txt
	python3 test/check.py

clean:
	rm -rf dist
