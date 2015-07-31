import unittest

from tests.utils import do_events_with_sleep, setup_test_env
setup_test_env()

from tests.gtk3.windows import (
    get_test_window_availablepane,
    get_test_window_installedpane,
)


class TestSearch(unittest.TestCase):

    def test_installedpane(self):
        win = get_test_window_installedpane()
        self.addCleanup(win.destroy)
        installedpane = win.get_data("pane")
        do_events_with_sleep()
        installedpane.on_search_terms_changed(None, "the")
        do_events_with_sleep()
        model = installedpane.app_view.tree_view.get_model()
        len1 = len(model)
        installedpane.on_search_terms_changed(None, "nosuchsearchtermforsure")
        do_events_with_sleep()
        len2 = len(model)
        self.assertTrue(len2 < len1)

    def test_availablepane(self):
        win = get_test_window_availablepane()
        self.addCleanup(win.destroy)
        pane = win.get_data("pane")
        do_events_with_sleep()
        pane.on_search_terms_changed(None, "the")
        do_events_with_sleep()
        sortmode = pane.app_view.sort_methods_combobox.get_active_text()
        self.assertEqual(sortmode, "By Relevance")
        model = pane.app_view.tree_view.get_model()
        len1 = len(model)
        pane.on_search_terms_changed(None, "nosuchsearchtermforsure")
        do_events_with_sleep()
        len2 = len(model)
        self.assertTrue(len2 < len1)


if __name__ == "__main__":
    unittest.main()
