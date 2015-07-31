import unittest

from tests.utils import (
    do_events,
    setup_test_env,
)
setup_test_env()

from tests.gtk3 import windows


class TestPanes(unittest.TestCase):

    def test_availablepane(self):
        win = windows.get_test_window_availablepane()
        self.addCleanup(win.destroy)

    def test_globalpane(self):
        win = windows.get_test_window_globalpane()
        self.addCleanup(win.destroy)

    def test_pendingpane(self):
        win = windows.get_test_window_pendingpane()
        self.addCleanup(win.destroy)

    def test_historypane(self):
        win = windows.get_test_window_historypane()
        self.addCleanup(win.destroy)

    def test_installedpane(self):
        win = windows.get_test_window_installedpane()
        self.addCleanup(win.destroy)
        pane = win.get_data("pane")
        # ensure it visible
        self.assertTrue(pane.get_property("visible"))
        # ensure the treeview is there and has data
        do_events()
        self.assertTrue(len(pane.treefilter.get_model()) > 2)


if __name__ == "__main__":
    unittest.main()
