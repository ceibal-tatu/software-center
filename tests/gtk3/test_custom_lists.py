import unittest

from tests.utils import (
    do_events_with_sleep,
    setup_test_env,
)
setup_test_env()

from softwarecenter.enums import XapianValues, ActionButtons
from tests.gtk3.windows import get_test_window_availablepane


class TestCustomLists(unittest.TestCase):

    def assertPkgInListAtIndex(self, index, model, needle):
        doc_name = model[index][0].get_value(XapianValues.PKGNAME)
        msg = "Expected %r at index %r, and custom list contained: %r"
        self.assertEqual(doc_name, needle, msg % (needle, index, doc_name))

    @unittest.skip('by relevance sort too unstable for proper test')
    def test_custom_lists(self):
        win = get_test_window_availablepane()
        self.addCleanup(win.destroy)
        pane = win.get_data("pane")
        do_events_with_sleep()
        pane.on_search_terms_changed(None, "ark,artha,software-center")
        do_events_with_sleep()
        model = pane.app_view.tree_view.get_model()

        # custom list should return three items
        self.assertTrue(len(model) == 3)

        # check package names, ordering is default "by relevance"
        self.assertPkgInListAtIndex(0, model, "ark")
        self.assertPkgInListAtIndex(1, model, "artha")
        self.assertPkgInListAtIndex(2, model, "software-center")

        # check that the status bar offers to install the packages
        install_button = pane.action_bar.get_button(ActionButtons.INSTALL)
        self.assertNotEqual(install_button, None)


if __name__ == "__main__":
    unittest.main()
