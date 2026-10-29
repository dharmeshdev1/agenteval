printf 'def greet(name="World"):\n    return "Hello, " + name + "!"\n\n\ndef farewell(name):\n    return "Goodbye, " + name\n' > greet.py
printf '# Changelog\n\n- initial release\n- default greeting name\n- add farewell\n' > CHANGELOG.md
git add greet.py CHANGELOG.md
git commit -q --no-edit
