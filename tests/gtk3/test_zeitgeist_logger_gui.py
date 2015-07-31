import unittest

from mock import Mock, patch
from tests.utils import setup_test_env

setup_test_env()

from softwarecenter.db.application import Application

from softwarecenter.enums import TransactionTypes
from tests.gtk3.windows import get_test_window_availablepane


class TestZeitgeistLoggerGUI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # we can only have one instance of availablepane, so create it here
        cls.win = get_test_window_availablepane()
        cls.available_pane = cls.win.get_data("pane")

    @classmethod
    def tearDownClass(cls):
        cls.win.destroy()

    def setUp(self):
        zl = "softwarecenter.backend.zeitgeist_logger.ZeitgeistLogger";
        self.log_install_event = patch(zl + ".log_install_event").start()
        self.log_uninstall_event = patch(zl + ".log_uninstall_event").start()

    def __emit_backend_event(self, pkgname, event):
        mock_result = Mock()
        mock_result.pkgname = pkgname
        self.available_pane.backend.emit(event, mock_result)

    def __start_backend_transaction(self, pkgname, type=TransactionTypes.INSTALL):
        app = Application("", pkgname)
        self.available_pane.backend.emit("transaction-started",
                                         app.pkgname, app.appname,
                                         "testid101", type)

    def test_zeitgeist_logger_init_on_start(self):
        test_pkgname = "software-center"
        self.__start_backend_transaction(test_pkgname)
        self.assertFalse(self.log_install_event.called)
        self.assertFalse(self.log_uninstall_event.called)
        self.assertEqual(len(self.available_pane.transactions_queue), 1)
        self.assertTrue(test_pkgname in self.available_pane.transactions_queue)

    def test_zeitgeist_logger_cancel_on_cancel(self):
        test_pkgname = "software-center"
        self.__start_backend_transaction(test_pkgname)
        self.assertTrue(test_pkgname in self.available_pane.transactions_queue)

        self.__emit_backend_event(test_pkgname, "transaction-cancelled")
        self.assertEqual(len(self.available_pane.transactions_queue), 0)
        self.assertFalse(self.log_install_event.called)
        self.assertFalse(self.log_uninstall_event.called)

    def test_zeitgeist_logger_cancel_on_stop(self):
        test_pkgname = "software-center"
        self.__start_backend_transaction(test_pkgname)
        self.assertTrue(test_pkgname in self.available_pane.transactions_queue)

        self.__emit_backend_event(test_pkgname, "transaction-stopped")
        self.assertEqual(len(self.available_pane.transactions_queue), 0)
        self.assertFalse(self.log_install_event.called)
        self.assertFalse(self.log_uninstall_event.called)

    def test_zeitgeist_logger_logs_install_on_finished(self):
        test_pkgname = "software-center"
        self.__start_backend_transaction(test_pkgname)
        transaction = self.available_pane.transactions_queue[test_pkgname]

        self.__emit_backend_event(test_pkgname, "transaction-finished")
        self.assertTrue(self.log_install_event.called)
        self.assertFalse(self.log_uninstall_event.called)
        self.assertEqual(len(self.available_pane.transactions_queue), 0)
        [args] = self.log_install_event.call_args[0]
        self.assertEqual(args, transaction.real_desktop_file)

    def test_zeitgeist_logger_logs_uninstall_on_finished(self):
        test_pkgname = "software-center"
        self.__start_backend_transaction(test_pkgname, TransactionTypes.REMOVE)
        transaction = self.available_pane.transactions_queue[test_pkgname]

        self.__emit_backend_event(test_pkgname, "transaction-finished")
        self.assertFalse(self.log_install_event.called)
        self.assertTrue(self.log_uninstall_event.called)
        self.assertEqual(len(self.available_pane.transactions_queue), 0)
        [args] = self.log_uninstall_event.call_args[0]
        self.assertEqual(args, transaction.real_desktop_file)

if __name__ == "__main__":
    unittest.main()
