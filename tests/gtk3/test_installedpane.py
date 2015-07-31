import unittest

from tests.utils import (
    do_events_with_sleep,
    setup_test_env,
)
setup_test_env()

from tests.gtk3.windows import get_test_window_installedpane


class TestInstalledPane(unittest.TestCase):

    def setUp(self):
        win = get_test_window_installedpane()
        self.addCleanup(win.destroy)
        self.pane = win.get_data("pane")

    def test_installedpane(self):
        do_events_with_sleep()
        # safe initial show/hide label for later
        initial_actionbar_label = self.pane.action_bar._label_text
        # do simple search
        self.pane.on_search_terms_changed(None, "foo")
        do_events_with_sleep()
        model = self.pane.app_view.tree_view.get_model()
        # FIXME: len(model) *only* counts the size of the top level
        #        (category) hits. thats still ok, as non-apps will
        #        add the "system" category
        len_only_apps = len(model)
        # set to show nonapps
        self.pane._show_nonapp_pkgs()
        do_events_with_sleep()
        len_with_nonapps = len(model)
        self.assertTrue(len_with_nonapps > len_only_apps)
        # set to hide nonapps again and ensure the size matches the
        # previous one
        self.pane._hide_nonapp_pkgs()
        do_events_with_sleep()
        self.assertEqual(len(model), len_only_apps)
        # clear sarch and ensure we get a expanded size again
        self.pane.on_search_terms_changed(None, "")
        do_events_with_sleep()
        all_apps = len(model)
        self.assertTrue(all_apps > len_only_apps)
        # ensure we have the same show/hide info as initially
        self.assertEqual(initial_actionbar_label,
                         self.pane.action_bar._label_text)

    def test_application_selected(self):
        the_app = object()
        self.pane.on_application_selected(appview=None, app=the_app)
        self.assertIs(self.pane.current_appview_selection, the_app)


if __name__ == "__main__":
    unittest.main()
