import unittest

from gi.repository import (
    GLib,
    Gtk,
    )

from tests.utils import setup_test_env
setup_test_env()

from tests.gtk3.windows import get_test_window_recommendations


# FIXME: the code from test_catview that tests the lobby widget should
#        move here as it should be fine to test it in isolation

TIMEOUT=300
class TestRecommendationsWidgets(unittest.TestCase):

    def _on_size_allocate(self, widget, allocation):
        print widget, allocation.width, allocation.height

    def test_recommendations_lobby(self):
        win = get_test_window_recommendations(panel_type="lobby")
        child = win.get_children()[0]
        child.connect("size-allocate", self._on_size_allocate)
        self.addCleanup(win.destroy)
        GLib.timeout_add(TIMEOUT, Gtk.main_quit)
        Gtk.main()

    def test_recommendations_category(self):
        win = get_test_window_recommendations(panel_type="category")
        self.addCleanup(win.destroy)
        GLib.timeout_add(TIMEOUT, Gtk.main_quit)
        Gtk.main()

    def test_recommendations_details(self):
        win = get_test_window_recommendations(panel_type="details")
        self.addCleanup(win.destroy)
        GLib.timeout_add(TIMEOUT, Gtk.main_quit)
        Gtk.main()


if __name__ == "__main__":
    unittest.main()
