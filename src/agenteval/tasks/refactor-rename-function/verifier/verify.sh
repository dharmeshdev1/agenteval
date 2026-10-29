set -e
if grep -rIEw --exclude-dir=.verifier --exclude-dir=.home --exclude-dir=.tmp --exclude-dir=.git calc_price . ; then
  echo "the old name calc_price is still used somewhere"; exit 1
fi
python3 -I .verifier/_shared/pyrun.py .verifier/tests
python3 -I -c "
import sys, unittest
sys.path.append('.')
sys.path.append('tests')
suite = unittest.defaultTestLoader.discover('tests', pattern='test*.py')
result = unittest.TextTestRunner().run(suite)
sys.exit(0 if result.wasSuccessful() and result.testsRun > 0 else 1)
" || { echo "the project's own tests do not pass"; exit 1; }
