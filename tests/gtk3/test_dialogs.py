import unittest

from mock import (
    Mock,
    patch,
)

from gi.repository import Gtk, GLib
from tests.utils import (
    get_test_gtk3_icon_cache,
    setup_test_env,
    FakedCache,
)
setup_test_env()

import softwarecenter.ui.gtk3.dialogs
from softwarecenter.db.application import Application
from softwarecenter.ui.gtk3.dialogs.dependency_dialogs import (
    confirm_remove,
    )
from tests.gtk3.windows import get_test_window_dependency_dialog

# window destory timeout
TIMEOUT=200


class TestDialogs(unittest.TestCase):
    """ basic tests for the various gtk3 dialogs """

    def get_test_window_dependency_dialog(self):
        dia = get_test_window_dependency_dialog()
        GLib.timeout_add(TIMEOUT,
                            lambda: dia.response(Gtk.ResponseType.ACCEPT))
        dia.run()

    def test_confirm_repair_broken_cache(self):
        datadir = softwarecenter.paths.datadir
        GLib.timeout_add(TIMEOUT, self._close_dialog)
        res = softwarecenter.ui.gtk3.dialogs.confirm_repair_broken_cache(
            parent=None, datadir=datadir)
        self.assertEqual(res, False)

    def test_error_dialog(self):
        GLib.timeout_add(TIMEOUT, self._close_dialog)
        res = softwarecenter.ui.gtk3.dialogs.error(
            parent=None, primary="primary", secondary="secondary")
        self.assertEqual(res, False)

    def test_accept_tos_dialog(self):
        GLib.timeout_add(TIMEOUT, self._close_dialog)
        res = softwarecenter.ui.gtk3.dialogs.show_accept_tos_dialog(
            parent=None)
        self.assertEqual(res, False)

    # helper
    def _close_dialog(self):
        softwarecenter.ui.gtk3.dialogs._DIALOG.response(0)


class TestDependencyDialog(unittest.TestCase):

    def setUp(self):
        self.parent = None
        self.db = Mock()
        self.db._aptcache = FakedCache()
        self.icons = get_test_gtk3_icon_cache()

    @patch("softwarecenter.ui.gtk3.dialogs.dependency_dialogs"
           "._get_confirm_internal_dialog")
    def test_removing_dependency_dialog_warning_on_ud(self, mock):
        app = Application("", "ubuntu-desktop")
        self.db._aptcache["ubuntu-desktop"] = Mock()
        confirm_remove(self.parent, app, self.db, self.icons)
        self.assertTrue(mock.called)

    @patch("softwarecenter.ui.gtk3.dialogs.dependency_dialogs"
           "._get_confirm_internal_dialog")
    def test_removing_dependency_dialog_warning_on_non_ud(self, mock):
        app = Application("Some random app", "meep")
        self.db._aptcache["meep"] = Mock()
        confirm_remove(self.parent, app, self.db, self.icons)
        self.assertFalse(mock.called)


if __name__ == "__main__":
    unittest.main()
