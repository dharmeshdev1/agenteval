set -e
git init -q .
git checkout -q -b main
printf 'def greet(name):\n    return "Hello, " + name\n' > greet.py
printf '# Changelog\n\n- initial release\n' > CHANGELOG.md
git add greet.py CHANGELOG.md
git commit -q -m "initial"
git checkout -q -b feature
printf 'def greet(name):\n    return "Hi, " + name\n\n\ndef farewell(name):\n    return "Goodbye, " + name\n' > greet.py
printf '# Changelog\n\n- initial release\n- add farewell\n' > CHANGELOG.md
git commit -q -a -m "feature: farewell"
git checkout -q main
printf 'def greet(name="World"):\n    return "Hello, " + name + "!"\n' > greet.py
printf '# Changelog\n\n- initial release\n- default greeting name\n' > CHANGELOG.md
git commit -q -a -m "main: default name"
git merge feature > /dev/null 2>&1 || true
printf '.home/\n.tmp/\n' >> .git/info/exclude
