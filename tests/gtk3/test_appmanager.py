import unittest

from mock import (
    Mock,
    patch,
    )

from tests.utils import (
    do_events,
    get_test_db,
    get_test_gtk3_icon_cache,
    setup_test_env,
)
setup_test_env()

import softwarecenter.paths
from softwarecenter.db.application import Application
from softwarecenter.distro import get_distro
from softwarecenter.ui.gtk3.session.appmanager import (
    ApplicationManager, get_appmanager)


class TestAppManager(unittest.TestCase):
    """ tests the appmanager  """

    def setUp(self):
        # get required test stuff
        self.db = get_test_db()
        self.backend = Mock()
        self.distro = get_distro()
        self.datadir = softwarecenter.paths.datadir
        self.icons = get_test_gtk3_icon_cache()
        # create it once, it becomes global instance
        if get_appmanager() is None:
            ApplicationManager(
                self.db, self.backend, self.icons)

    def test_get_appmanager(self):
        app_manager = get_appmanager()
        self.assertNotEqual(app_manager, None)
        # test singleton
        app_manager2 = get_appmanager()
        self.assertEqual(app_manager, app_manager2)
        # test creating it twice raises a error
        self.assertRaises(
            ValueError, ApplicationManager, self.db, self.backend, self.icons)

    def test_appmanager(self):
        app_manager = get_appmanager()
        self.assertNotEqual(app_manager, None)
        # test interface
        app_manager.reload()
        app = Application("", "2vcard")
        # call and ensure the stuff is passed to the backend
        app_manager.install(app, [], [])
        self.assertTrue(self.backend.install.called)

        app_manager.remove(app, [], [])
        self.assertTrue(self.backend.remove.called)

        app_manager.upgrade(app, [], [])
        self.assertTrue(self.backend.upgrade.called)

        app_manager.apply_changes(app, [], [])
        self.assertTrue(self.backend.apply_changes.called)

        app_manager.enable_software_source(app)
        self.assertTrue(self.backend.enable_component.called)

        app_manager.reinstall_purchased(app)
        self.assertTrue(self.backend.add_repo_add_key_and_install_app.called)

        # buy is special as it needs help from the purchase view
        app_manager.connect("purchase-requested", self._on_purchase_requested)
        app_manager.buy_app(app)
        self.assertTrue(self._purchase_requested_signal)
        do_events()

    def _on_purchase_requested(self, *args):
        self._purchase_requested_signal = True

    def test_appmanager_requests_oauth_token(self):
        oauth_token = { "moo": "bar",
                        "lala": "la",
                        }
        # reset the global appmanager
        softwarecenter.ui.gtk3.session.appmanager._appmanager = None
        with patch("softwarecenter.ui.gtk3.session.appmanager.UbuntuSSO"
                   ".find_oauth_token_sync") as m:
            m.return_value = oauth_token
            app_manager = ApplicationManager(self.db, self.backend, self.icons)
            self.assertEqual(app_manager.oauth_token, oauth_token)


if __name__ == "__main__":
    unittest.main()
