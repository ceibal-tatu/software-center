import unittest

from tests.utils import (
    setup_test_env,
)
setup_test_env()

from softwarecenter.db.application import Application
from tests.gtk3.windows import get_test_window_availablepane


class AvailablePaneTestCase(unittest.TestCase):

    def setUp(self):
        win = get_test_window_availablepane()
        self.addCleanup(win.destroy)
        self.pane = win.get_data("pane")
        self.vm = win.get_data("vm")

    def test_leave_page_stops_video(self):
        called = []

        self.pane.state.application = Application('', 'foo')
        self.vm.display_page(self.pane, self.pane.Pages.DETAILS, self.pane.state)
        assert self.pane.is_app_details_view_showing()

        self.pane.app_details_view.videoplayer.stop = \
            lambda: called.append('stop')

        self.pane.leave_page(self.pane.state)

        self.assertEqual(called, ['stop'])


if __name__ == "__main__":
    unittest.main()
