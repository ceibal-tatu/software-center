import apt
import time
import unittest

from gi.repository import GLib
from mock import patch

from tests.utils import (
    get_test_pkg_info,
    setup_test_env,
)
setup_test_env()

import softwarecenter
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.utils import ExecutionTime


class TestAptCache(unittest.TestCase):

    def test_open_aptcache(self):
        # mvo: for the performance, its critical to have a
        #      /var/cache/apt/srcpkgcache.bin - otherwise stuff will get slow

        # open s-c aptcache
        with ExecutionTime("s-c softwarecenter.apt.AptCache"):
            self.sccache = get_pkg_info()
        # cache is opened with a timeout_add() in get_pkg_info()
        time.sleep(0.2)
        context = GLib.main_context_default()
        while context.pending():
            context.iteration()
        # compare with plain apt
        with ExecutionTime("plain apt: apt.Cache()"):
            self.cache = apt.Cache()
        with ExecutionTime("plain apt: apt.Cache(memonly=True)"):
            self.cache = apt.Cache(memonly=True)

    def test_get_total_size(self):
        def _on_query_total_size_on_install_done(pkginfo, pkgname, 
                                                 download, space):
            self.need_download = download
            self.need_space = space
            loop.quit()
        TEST_PKG = "casper"
        ADDONS_TO_INSTALL = [ "lupin-casper" ]
        ADDONS_TO_REMOVE = []
        loop =  GLib.MainLoop(GLib.main_context_default())
        cache = get_test_pkg_info()
        cache.connect(
            "query-total-size-on-install-done", 
            _on_query_total_size_on_install_done)
        cache.query_total_size_on_install(
            TEST_PKG, ADDONS_TO_INSTALL, ADDONS_TO_REMOVE)
        loop.run()
        # ensure the test eventually stops and does not hang
        GLib.timeout_add_seconds(10, loop.quit)
        # work out the numbers that we at least need to get (this will
        # not include dependencies so it is probably lower)
        need_at_least_download = (
            cache[TEST_PKG].candidate.size + 
            sum([cache[pkg].candidate.size for pkg in ADDONS_TO_INSTALL]))
        need_at_least_installed = (
            cache[TEST_PKG].candidate.installed_size +
            sum([cache[pkg].candidate.installed_size for pkg in ADDONS_TO_INSTALL]))
        self.assertTrue(self.need_download >= need_at_least_download)
        self.assertTrue(self.need_space >= need_at_least_installed)
        del self.need_download
        del self.need_space

    def test_get_total_size_with_mock(self):
        # get a cache 
        cache = get_pkg_info()
        cache.open()
        # pick first uninstalled pkg
        for pkg in cache:
            if not pkg.is_installed:
                break
        # prepare args
        addons_to_install = addons_to_remove = []
        archive_suite = "foo"
        with patch.object(cache.aptd_client, "commit_packages") as f_mock:
            cache.query_total_size_on_install(
                pkg.name, addons_to_install, addons_to_remove, archive_suite)
            # ensure it got called with the right arguments
            args, kwargs = f_mock.call_args
            to_install = args[0]
            self.assertTrue(to_install[0].endswith("/%s" % archive_suite))

    @patch("softwarecenter.db.pkginfo_impl.aptcache.AptClient")
    def test_aptd_client_unavailable(self, mock_apt_client):
        mock_apt_client.side_effect = Exception("fake")
        cache = softwarecenter.db.pkginfo_impl.aptcache.AptCache()
        self.assertEqual(cache.aptd_client, None)

if __name__ == "__main__":
    unittest.main()
