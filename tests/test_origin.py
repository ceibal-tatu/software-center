import apt
import os
import unittest

from tests.utils import (
    DATA_DIR,
    setup_test_env,
    url_accessable,
)
setup_test_env()


class TestOrigins(unittest.TestCase):
    """ tests the origin code """

    @unittest.skipUnless(
        url_accessable("http://de.archive.ubuntu.com/ubuntu", "dists/"),
        "Can not access the network, skipping")
    def test_origin(self):
        # get a cache
        cache = apt.Cache(rootdir=os.path.join(DATA_DIR, "aptroot"))
        cache.update()
        cache.open()
        # PPA origin
        origins = cache["firefox-trunk"].candidate.origins

        self.assertEqual(origins[0].site, "ppa.launchpad.net")
        self.assertEqual(origins[0].origin, "LP-PPA-ubuntu-mozilla-daily")
        # archive origin
        origins = cache["apt"].candidate.origins
        self.assertEqual(origins[0].site, "archive.ubuntu.com")
        self.assertEqual(origins[0].origin, "Ubuntu")
        self.assertEqual(origins[1].site, "de.archive.ubuntu.com")
        self.assertEqual(origins[1].origin, "Ubuntu")


if __name__ == "__main__":
    unittest.main()
