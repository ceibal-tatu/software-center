import os
import subprocess
import unittest

import softwarecenter


class PackagePep8TestCase(unittest.TestCase):

    def test_all_code(self):
        res = 0
        testdir = os.path.dirname(__file__)
        res += subprocess.call(
            ["pep8",
             "--repeat",
             # FIXME: FIXME!
             "--ignore=E126,E127,E128",
             os.path.dirname(softwarecenter.__file__),
             # test the main binary too
             os.path.join(testdir, "..", "software-center"),
             ])
        self.assertEqual(res, 0)


if __name__ == "__main__":
    unittest.main()
