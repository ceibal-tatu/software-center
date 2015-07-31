import unittest

from mock import Mock, patch

from tests.utils import (
    do_events_with_sleep,
    get_mock_options,
    setup_test_env,
)
setup_test_env()

from softwarecenter.ui.gtk3.views import purchaseview
from softwarecenter.ui.gtk3.app import SoftwareCenterAppGtk3
from softwarecenter.ui.gtk3.panes.availablepane import AvailablePane
from tests.gtk3.windows import get_test_window_purchaseview


class TestPurchase(unittest.TestCase):

    def test_purchase_view_log_cleaner(self):
        win = get_test_window_purchaseview()
        self.addCleanup(win.destroy)
        do_events_with_sleep()
        # get the view
        view = win.get_data("view")
        # install the mock
        purchaseview.LOG = mock = Mock()
        # run a "harmless" log message and ensure its logged normally
        view.wk.webkit.execute_script('console.log("foo")')
        self.assertTrue("foo" in mock.debug.call_args[0][0])
        mock.reset_mock()

        # run a message that contains token info
        s = ('http://sca.razorgirl.info/subscriptions/19077/checkout_complete/'
            ' @10: {"token_key": "hiddenXXXXXXXXXX", "consumer_secret": '
            '"hiddenXXXXXXXXXXXX", "api_version": 2.0, "subscription_id": '
            '19077, "consumer_key": "rKhNPBw", "token_secret": '
            '"hiddenXXXXXXXXXXXXXXX"}')
        view.wk.webkit.execute_script("console.log('%s')" % s)
        self.assertTrue("skipping" in mock.debug.call_args[0][0])
        self.assertFalse("consumer_secret" in mock.debug.call_args[0][0])
        mock.reset_mock()

    def test_purchase_view_tos(self):
        win = get_test_window_purchaseview()
        self.addCleanup(win.destroy)
        view = win.get_data("view")
        # install the mock
        mock_config = Mock()
        mock_config.user_accepted_tos = False
        view.config = mock_config
        func = "softwarecenter.ui.gtk3.views.purchaseview.show_accept_tos_dialog"
        with patch(func) as mock_func:
            mock_func.return_value = False
            res = view.initiate_purchase(None, None)
            self.assertFalse(res)
            self.assertTrue(mock_func.called)

    def test_spinner_emits_signals(self):
        win = get_test_window_purchaseview()
        self.addCleanup(win.destroy)
        do_events_with_sleep()
        # get the view
        view = win.get_data("view")
        # ensure "purchase-needs-spinner" signals are send
        signal_mock = Mock()
        view.connect("purchase-needs-spinner", signal_mock)
        view.wk.webkit.load_uri("http://www.ubuntu.com/")
        do_events_with_sleep()
        self.assertTrue(signal_mock.called)


class PreviousPurchasesTestCase(unittest.TestCase):

    @patch("softwarecenter.backend.ubuntusso.UbuntuSSO"
           ".find_oauth_token_sync")
    def test_reinstall_previous_purchase_display(self, mock_find_token):
        mock_find_token.return_value = { 'not': 'important' }
        mock_options = get_mock_options()
        app = SoftwareCenterAppGtk3(mock_options)
        self.addCleanup(app.destroy)
        # real app opens cache async
        app.cache.open()
        # .. and now pretend we clicked on the menu item
        app.window_main.show_all()
        app.available_pane.init_view()
        do_events_with_sleep()
        app.on_menuitem_reinstall_purchases_activate(None)
        # it can take a bit until the sso client is ready
        for i in range(10):
            if (app.available_pane.get_current_page() ==
                AvailablePane.Pages.LIST):
                break
            do_events_with_sleep()
        self.assertEqual(app.available_pane.get_current_page(),
                         AvailablePane.Pages.LIST)


if __name__ == "__main__":
    unittest.main()
