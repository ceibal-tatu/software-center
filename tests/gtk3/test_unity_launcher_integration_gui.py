import unittest

from gi.repository import Gtk
from mock import Mock, patch

from tests.utils import (
    do_events,
    do_events_with_sleep,
    setup_test_env,
)

setup_test_env()

from softwarecenter.backend.unitylauncher import UnityLauncherInfo
from softwarecenter.config import get_config
from softwarecenter.db.application import Application

from softwarecenter.enums import TransactionTypes
from softwarecenter.ui.gtk3.panes.availablepane import AvailablePane
from tests.gtk3.windows import get_test_window_availablepane

# Tests for Ubuntu Software Center's integration with the Unity launcher,
# see https://wiki.ubuntu.com/SoftwareCenter#Learning%20how%20to%20launch%20an%20application


class TestUnityLauncherIntegrationGUI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # we can only have one instance of availablepane, so create it here
        cls.win = get_test_window_availablepane()
        cls.available_pane = cls.win.get_data("pane")

        # get the global config
        cls.config = get_config()

        # patch is_unity_running so that the test works inside a e.g.
        # ADT
        patch("softwarecenter.utils.is_unity_running").start().return_value = True
        patch("softwarecenter.backend.unitylauncher.UnityLauncher"
              "._get_launcher_dbus_iface").start().return_value = Mock()

    @classmethod
    def tearDownClass(cls):
        cls.win.destroy()

    def _simulate_install_events(self, app,
                                 result_event="transaction-finished"):
        # pretend we started an install
        self.available_pane.backend.emit("transaction-started",
                                    app.pkgname, app.appname,
                                    "testid101",
                                    TransactionTypes.INSTALL)
        do_events_with_sleep()
        # send the signal to complete the install
        mock_result = Mock()
        mock_result.pkgname = app.pkgname
        self.available_pane.backend.emit(result_event,
                                    mock_result)
        do_events_with_sleep()

    def _install_from_list_view(self, pkgname):
        self.available_pane.notebook.set_current_page(AvailablePane.Pages.LIST)

        do_events()
        self.available_pane.on_search_terms_changed(None,
            "ark,artha,software-center")
        do_events()

        # select the first item in the list
        self.available_pane.app_view.tree_view.set_cursor(Gtk.TreePath(0),
                                                            None, False)
        # ok to just use the test app here
        app = Application("", pkgname)
        do_events()
        self._simulate_install_events(app)

    def _navigate_to_appdetails_and_install(self, pkgname):
        app = Application("", pkgname)
        self.available_pane.app_view.emit("application-activated",
                                     app)
        do_events()
        self._simulate_install_events(app)

    def _check_send_application_to_launcher_args(self,
                                                 pkgname, launcher_info):
        self.assertEqual(pkgname, self.expected_pkgname)
        self.assertEqual(launcher_info.name, self.expected_launcher_info.name)
        self.assertEqual(launcher_info.icon_name,
                         self.expected_launcher_info.icon_name)

        # mvo: this will fail in xvfb-run so we need to disable it for now
        #self.assertTrue(launcher_info.icon_x > 5)
        #self.assertTrue(launcher_info.icon_y > 5)

        # check that the icon size is one of either 32 pixels (for the
        # list view case) or 96 pixels (for the details view case)
        self.assertTrue(launcher_info.icon_size == 32 or
                        launcher_info.icon_size == 96)
        self.assertEqual(launcher_info.installed_desktop_file_path,
                self.expected_launcher_info.installed_desktop_file_path)
        self.assertEqual(launcher_info.trans_id,
                self.expected_launcher_info.trans_id)

    @patch('softwarecenter.ui.gtk3.panes.availablepane.UnityLauncher'
           '.send_application_to_launcher')
    def test_unity_launcher_integration_list_view(self,
                                         mock_send_application_to_launcher):
        # test the automatic add to launcher enabled functionality when
        # installing an app from the list view
        self.config.add_to_unity_launcher = True
        test_pkgname = "software-center"
        self.expected_pkgname = test_pkgname
        self.expected_launcher_info = UnityLauncherInfo("software-center",
                "softwarecenter",
                0, 0, 0, 0, # these values are set in availablepane
                "/usr/share/app-install/desktop/software-center:ubuntu-software-center.desktop",
                "testid101")
        self._install_from_list_view(test_pkgname)
        self.assertTrue(mock_send_application_to_launcher.called)
        args, kwargs = mock_send_application_to_launcher.call_args
        self._check_send_application_to_launcher_args(*args, **kwargs)


    @patch('softwarecenter.ui.gtk3.panes.availablepane.UnityLauncher'
           '.send_application_to_launcher')
    def test_unity_launcher_integration_details_view(self,
                                         mock_send_application_to_launcher):
        # test the automatic add to launcher enabled functionality when
        # installing an app from the details view
        self.config.add_to_unity_launcher = True
        test_pkgname = "software-center"
        self.expected_pkgname = test_pkgname
        self.expected_launcher_info = UnityLauncherInfo("software-center",
                "softwarecenter",
                0, 0, 0, 0, # these values are set in availablepane
                "/usr/share/app-install/desktop/software-center:ubuntu-software-center.desktop",
                "testid101")
        self._navigate_to_appdetails_and_install(test_pkgname)
        self.assertTrue(mock_send_application_to_launcher.called)
        args, kwargs = mock_send_application_to_launcher.call_args
        self._check_send_application_to_launcher_args(*args, **kwargs)

    @patch('softwarecenter.ui.gtk3.panes.availablepane.UnityLauncher'
           '.send_application_to_launcher')
    def test_unity_launcher_integration_disabled(self,
                                         mock_send_application_to_launcher):
        # test the case where automatic add to launcher is disabled
        self.config.add_to_unity_launcher = False
        test_pkgname = "software-center"
        self._navigate_to_appdetails_and_install(test_pkgname)
        self.assertFalse(mock_send_application_to_launcher.called)

    @patch('softwarecenter.ui.gtk3.panes.availablepane.UnityLauncher'
           '.send_application_to_launcher')
    def test_unity_launcher_integration_launcher(self,
                mock_send_application_to_launcher):
        # this is a 3-tuple of (pkgname, desktop-file, expected_result)
        TEST_CASES = (
            # normal app
            ("software-center", "/usr/share/app-install/desktop/"\
                 "software-center:ubuntu-software-center.desktop", True),
            # NoDisplay=True line
            ("wine1.4", "/usr/share/app-install/desktop/"\
                 "wine1.4:wine.desktop", False),
            # No Exec= line
            ("bzr", "/usr/share/app-install/desktop/"\
                 "bzr.desktop", False)
            )
        # run the test over all test-cases
        self.config.add_to_unity_launcher = True
        for test_pkgname, app_install_desktop_file_path, res in TEST_CASES:
            # this is the tofu of the test
            self._navigate_to_appdetails_and_install(test_pkgname)
            # verify
            self.assertEqual(
                mock_send_application_to_launcher.called, 
                res,
                "expected %s for pkg: %s but got: %s" % (
                    res, test_pkgname, 
                    mock_send_application_to_launcher.called))
            # and reset again to ensure we don't get the call info from
            # the previous call(s)
            mock_send_application_to_launcher.reset_mock()

    @patch('softwarecenter.ui.gtk3.panes.availablepane.UnityLauncher'
           '.cancel_application_to_launcher')
    def test_unity_launcher_integration_cancelled_install(self,
                                         mock_cancel_launcher):
        # test the automatic add to launcher enabled functionality when
        # installing an app from the details view, and then cancelling
        # the install (see LP: #1027209)
        self.config.add_to_unity_launcher = True
        test_pkgname = "software-center"
        app = Application("", test_pkgname)
        self.available_pane.app_view.emit("application-activated",
                                     app)
        do_events()
        self._simulate_install_events(app,
                                      result_event="transaction-cancelled")
        # ensure that we cancel the send
        self.assertTrue(
            mock_cancel_launcher.called)

    @patch('softwarecenter.ui.gtk3.panes.availablepane.UnityLauncher'
           '.cancel_application_to_launcher')
    def test_unity_launcher_integration_installation_failure(self,
                                         mock_cancel_launcher):
        # test the automatic add to launcher enabled functionality when
        # a failure is detected during the transaction (aptd emits a
        # "transaction-stopped" signal for this case)
        self.config.add_to_unity_launcher = True
        test_pkgname = "software-center"
        app = Application("", test_pkgname)
        self.available_pane.app_view.emit("application-activated",
                                     app)
        do_events()
        # aptd will emit a "transaction-stopped" signal if a transaction
        # error is encountered
        self._simulate_install_events(app,
                                      result_event="transaction-stopped")
        # ensure that we cancel the send
        self.assertTrue(
            mock_cancel_launcher.called)


if __name__ == "__main__":
    unittest.main()
