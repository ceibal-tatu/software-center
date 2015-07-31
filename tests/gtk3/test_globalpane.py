import unittest

from tests.utils import (
    do_events,
    setup_test_env,
)
setup_test_env()

from tests.gtk3.windows import get_test_window_globalpane


class TestGlobalPane(unittest.TestCase):

    def test_spinner_available(self):
        win = get_test_window_globalpane()
        self.addCleanup(win.destroy)
        pane = win.get_data("pane")
        self.assertNotEqual(pane.spinner, None)
        do_events()


if __name__ == "__main__":
    unittest.main()
