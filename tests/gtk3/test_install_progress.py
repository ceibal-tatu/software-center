import unittest

from tests.utils import (
    setup_test_env,
    start_dummy_backend,
    stop_dummy_backend,
)
setup_test_env()


from softwarecenter.db.application import Application
from tests.gtk3.windows import get_test_window_appdetails


class TestViews(unittest.TestCase):

    def setUpNo(self):
        start_dummy_backend()
        self.addCleanup(stop_dummy_backend)

    def test_install_appdetails(self):
        win = get_test_window_appdetails()
        self.addCleanup(win.destroy)
        view = win.get_data("view")
        view.show_app(Application("", "2vcard"))
        view.backend.emit('transaction-progress-changed',
            view.app_details.pkgname, 10)
        self.assertTrue(view.pkg_statusbar.progress.get_property("visible"))


if __name__ == "__main__":
    unittest.main()
