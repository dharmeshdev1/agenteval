"""Hidden-test runner used by Python task verifiers.

    python3 -I .verifier/_shared/pyrun.py TEST_DIR

It runs under ``-I`` (isolated mode) and appends the workspace to ``sys.path`` after the
standard library, so a file the agent created, such as ``unittest.py`` or ``json.py``,
can never replace a standard module. The agent's own modules are still importable.
Exit code 0 only if at least one test ran and every test passed.
"""

import os
import sys
import unittest

workspace = os.getcwd()
test_dir = os.path.abspath(sys.argv[1])
sys.path.append(workspace)

suite = unittest.defaultTestLoader.discover(test_dir, pattern="test*.py", top_level_dir=test_dir)
result = unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(0 if result.wasSuccessful() and result.testsRun > 0 else 1)
