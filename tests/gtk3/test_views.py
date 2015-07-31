import unittest

from tests.utils import setup_test_env
setup_test_env()

from tests.gtk3.windows import (
    get_test_window_appdetails,
    get_test_window_appview,
    get_test_window_catview,
    get_test_window_pkgnamesview,
    get_test_window_purchaseview,
    get_test_window_viewswitcher,
)


class TestViews(unittest.TestCase):

    def test_viewswitcher(self):
        win = get_test_window_viewswitcher()
        self.addCleanup(win.destroy)

    def test_catview(self):
        win = get_test_window_catview()
        self.addCleanup(win.destroy)

    def test_appdetails(self):
        win = get_test_window_appdetails()
        self.addCleanup(win.destroy)

    def test_pkgsnames(self):
        win = get_test_window_pkgnamesview()
        self.addCleanup(win.destroy)

    def test_purchaseview(self):
        win = get_test_window_purchaseview()
        self.addCleanup(win.destroy)

    def test_appview(self):
        win = get_test_window_appview()
        self.addCleanup(win.destroy)


if __name__ == "__main__":
    unittest.main()
