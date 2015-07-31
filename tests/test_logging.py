import os
import shutil
import stat
import unittest

from mock import patch

from tests.utils import (
    setup_test_env,
)
setup_test_env()

import softwarecenter.log
import softwarecenter.paths


class TestLogging(unittest.TestCase):
    """Tests for the sc logging facilities."""

    @unittest.skipIf(
        os.getuid() == 0, 
        "fails when run as root as os.access() is always successful")
    def test_no_write_access_for_cache_dir(self):
        """Test for bug LP: #688682."""
        cache_dir = './foo'
        os.mkdir(cache_dir)
        self.addCleanup(shutil.rmtree, cache_dir)
        with patch('softwarecenter.paths.SOFTWARE_CENTER_CACHE_DIR',
                    cache_dir):
            # make the test cache dir non-writeable
            os.chmod(cache_dir, stat.S_IRUSR)
            self.addCleanup(os.chmod, cache_dir,
                            stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            self.assertFalse(os.access(cache_dir, os.W_OK))

            # and then start up the logger
            reload(softwarecenter.log)
            new_cache_dir = cache_dir + ".0"
            self.addCleanup(shutil.rmtree, new_cache_dir)

            # check that the old directory was moved aside
            # (renamed with a ".0" appended)
            self.assertTrue(os.path.exists(new_cache_dir))
            self.assertFalse(os.path.exists(cache_dir + ".1"))
            # and check that the new directory was created and is now writable
            self.assertTrue(os.access(new_cache_dir, os.R_OK | os.W_OK))


if __name__ == "__main__":
    unittest.main()
