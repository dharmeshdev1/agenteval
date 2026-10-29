set -e
if grep -E '^(<<<<<<<|=======|>>>>>>>)' greet.py CHANGELOG.md; then
  echo "conflict markers remain"; exit 1
fi
python3 -I -c "
import sys
sys.path.append('.')
import greet
assert greet.greet() == 'Hello, World!', greet.greet()
assert greet.greet('Bob') == 'Hello, Bob!'
assert greet.farewell('Bob') == 'Goodbye, Bob'
" || { echo "greet.py does not behave as required"; exit 1; }
python3 -I -c "
lines = [l.strip() for l in open('CHANGELOG.md') if l.strip()]
assert '- default greeting name' in lines and '- add farewell' in lines, lines
assert lines.index('- default greeting name') < lines.index('- add farewell'), lines
assert lines.count('- initial release') == 1, lines
" || { echo "CHANGELOG.md is not resolved as required"; exit 1; }
merges=$(git log --merges --oneline | wc -l | tr -d ' ')
[ "$merges" -ge 1 ] || { echo "no merge commit in history"; exit 1; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "working tree is not clean"; exit 1; }
[ ! -f .git/MERGE_HEAD ] || { echo "merge is still in progress"; exit 1; }
