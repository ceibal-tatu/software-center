import os
import unittest

from gi.repository import Gtk, GdkPixbuf, GLib
from gettext import gettext as _
from mock import Mock, patch

from tests.utils import (
    DATA_DIR,
    setup_test_env,
    do_events,
    do_events_with_sleep,
)
setup_test_env()

from softwarecenter.netstatus import (
    NetState,
    test_ping,
)

from softwarecenter.enums import PkgStates
from softwarecenter.utils import utf8
from softwarecenter.ui.gtk3.widgets import videoplayer
from softwarecenter.ui.gtk3.widgets.actionbar import ActionBar
from softwarecenter.ui.gtk3.widgets.imagedialog import SimpleShowImageDialog
from softwarecenter.ui.gtk3.widgets.labels import (
    HardwareRequirementsLabel, HardwareRequirementsBox)
from tests.gtk3.windows import (
    get_test_backforward_window,
    get_test_buttons_window,
    get_test_container_window,
    get_test_description_window,
    get_test_exhibits_window,
    get_test_reviews_window,
    get_test_searchentry_window,
    get_test_screenshot_thumbnail_window,
    get_test_spinner_window,
    get_test_stars_window,
    get_test_symbolic_icons_window,
    get_test_videoplayer_window,
    get_test_window,
    get_test_window_apptreeview,
)

# window destory timeout
TIMEOUT=100

class TestWidgets(unittest.TestCase):
    """ basic tests for the various gtk3 widget """

    def test_stars(self):
        win = get_test_stars_window()
        self.addCleanup(win.destroy)

    def test_actionbar(self):
        mock = Mock()
        actionbar = ActionBar()
        actionbar.add_button("id1", "label", mock)
        actionbar.add_button("id2", "label", mock)
        actionbar.remove_button("id2")
        win = get_test_window(child=actionbar)
        self.addCleanup(win.destroy)

    def test_backforward(self):
        win = get_test_backforward_window()
        self.addCleanup(win.destroy)

    def test_backforward_lp1034894(self):
        win = get_test_backforward_window(width=150, height=75)
        backforward = win.get_children()[0]
        style_context = backforward.get_style_context()
        self.assertTrue(style_context.has_class(Gtk.STYLE_CLASS_LINKED))
        self.addCleanup(win.destroy)
        GLib.timeout_add(TIMEOUT, Gtk.main_quit)
        Gtk.main()

    def test_containers(self):
        win = get_test_container_window()
        self.addCleanup(win.destroy)

    def test_description(self):
        win = get_test_description_window()
        self.addCleanup(win.destroy)

    def test_exhibits(self):
        win = get_test_exhibits_window()
        self.addCleanup(win.destroy)

    def test_show_image_dialog(self):
        f = os.path.join(DATA_DIR, "test_images", "fallback.png")
        pix = GdkPixbuf.Pixbuf.new_from_file(f)
        d = SimpleShowImageDialog("test caption", pix)
        GLib.timeout_add(TIMEOUT, lambda: d.destroy())
        d.run()

    def test_searchentry(self):
        win = get_test_searchentry_window()
        self.addCleanup(win.destroy)
        s = "foo"
        win.entry.insert_text(s, len(s))
        self.addCleanup(win.destroy)

    def test_spinner(self):
        win = get_test_spinner_window()
        self.addCleanup(win.destroy)

    def test_symbolic_icons(self):
        win = get_test_symbolic_icons_window()
        self.addCleanup(win.destroy)

    def test_buttons(self):
        win = get_test_buttons_window()
        self.addCleanup(win.destroy)

    def test_videoplayer(self):
        win = get_test_videoplayer_window()
        self.addCleanup(win.destroy)

    def test_apptreeview(self):
        win = get_test_window_apptreeview()
        self.addCleanup(win.destroy)

    @unittest.skipIf(test_ping() != NetState.NM_STATE_CONNECTED_GLOBAL,
                     "Need network for this test")
    def test_screenshot_thumbnail(self):
        win = get_test_screenshot_thumbnail_window()
        self.addCleanup(win.destroy)
        t = win.get_data("screenshot_thumbnail_widget")
        b = win.get_data("screenshot_thumbnail_cycle_test_button")
        for i in range(5):
            b.clicked()
            do_events_with_sleep(iterations=5)
            # ensure that either the big screeshot is visible or the loading
            # spinner
            self.assertTrue(t.main_screenshot.get_property("visible") or
                            t.spinner.get_property("visible"))



class TestHWRequirements(unittest.TestCase):

    HW_TEST_RESULT = { 'hardware::gps' : 'yes',
                       'hardware::xxx' : 'unknown',
                       'hardware::input:mouse' : 'no',
                       }

    def test_hardware_requirements_label(self):
        label = HardwareRequirementsLabel()
        label.set_hardware_requirement('hardware::gps', 'yes')
        self.assertEqual(
            label.get_label(),
            u"%sGPS" % HardwareRequirementsLabel.SUPPORTED_SYM["yes"])
        # test the gtk bits
        self.assertEqual(type(label.get_children()[0]), Gtk.Label)
        # test setting it again
        label.set_hardware_requirement('hardware::video:opengl', 'yes')
        self.assertEqual(len(label.get_children()), 1)

    # regression test for bug #967036
    @patch("softwarecenter.ui.gtk3.widgets.labels.get_hw_short_description")
    def test_hardware_requirements_label_utf8(self, mock_get_hw):
        magic_marker = u" \u1234 GPS"
        mock_get_hw.return_value = utf8(magic_marker)
        label = HardwareRequirementsLabel()
        label.set_hardware_requirement('hardware::gps', 'yes')
        self.assertEqual(
            label.get_label(),
            u"%s%s" % (HardwareRequirementsLabel.SUPPORTED_SYM["yes"],
                       magic_marker))

    def test_hardware_requirements_box(self):
        box = HardwareRequirementsBox()
        # test empty
        box.set_hardware_requirements({})
        # test sensible
        box.set_hardware_requirements(self.HW_TEST_RESULT)
        # its 2 because we do not display "unknown" currently
        self.assertEqual(len(box.hw_labels), 2)
        # test the gtk bits
        self.assertEqual(len(box.get_children()), 2)
        # no trailing ","
        self.assertEqual(
            box.get_children()[0].get_label(),
            u"%smouse," % HardwareRequirementsLabel.SUPPORTED_SYM["no"])
        self.assertEqual(
            box.get_children()[1].get_label(),
            u"%sGPS" % HardwareRequirementsLabel.SUPPORTED_SYM["yes"])

        # test seting it again
        box.set_hardware_requirements(self.HW_TEST_RESULT)
        self.assertEqual(len(box.get_children()), 2)


class TestUIReviewsList(unittest.TestCase):

    def setUp(self):
        self.win = get_test_reviews_window()
        self.addCleanup(self.win.destroy)
        self.rl = self.win.get_children()[0]

    def assertComboBoxTextIncludes(self, combo, option):
        store = combo.get_model()
        self.assertTrue(option in [x[0] for x in store])

    def assertEmbeddedMessageLabel(self, title, message):
        markup = self.rl.vbox.get_children()[1].label.get_label()
        self.assertTrue(title in markup)
        self.assertTrue(message in markup)

    def test_reviews_includes_any_language(self):
        review_language = self.rl.review_language
        self.assertComboBoxTextIncludes(review_language, _('Any language'))

    def test_reviews_offers_to_relax_language(self):
        # No reviews found, but there are some in other languages:
        self.rl.clear()
        self.rl.global_review_stats = Mock()
        self.rl.global_review_stats.ratings_total = 4
        self.rl.configure_reviews_ui()
        do_events()

        self.assertEmbeddedMessageLabel(
            _("This app has not been reviewed yet in your language"),
            _('Try selecting a different language, or even "Any language"'
            ' in the language dropdown'))

    @patch('softwarecenter.ui.gtk3.widgets.reviews.network_state_is_connected')
    def test_reviews_no_reviews_but_app_not_installed(self, mock_connected):
        mock_connected.return_value = True
        # No reviews found, and the app isn't installed
        self.rl.clear()
        self.rl.configure_reviews_ui()
        do_events()

        self.assertEmbeddedMessageLabel(
            _("This app has not been reviewed yet"),
            _('You need to install this before you can review it'))

    @patch('softwarecenter.ui.gtk3.widgets.reviews.network_state_is_connected')
    def test_reviews_no_reviews_offer_to_write_one(self, mock_connected):
        mock_connected.return_value = True
        # No reviews found, and the app is installed
        self.rl.clear()
        self.rl._parent.app_details.pkg_state = PkgStates.INSTALLED
        self.rl.configure_reviews_ui()
        do_events()

        self.assertEmbeddedMessageLabel(
            _('Got an opinion?'),
            _('Be the first to contribute a review for this application'))


class VideoPlayerTestCase(unittest.TestCase):

    def setUp(self):
        super(VideoPlayerTestCase, self).setUp()
        self.webkit_uri = None
        self.vp = videoplayer.VideoPlayer()
        self.vp.webkit.load_uri = lambda uri: setattr(self, 'webkit_uri', uri)
        self.vp.webkit.get_uri = lambda: self.webkit_uri
        self.addCleanup(self.vp.destroy)

    def test_uri(self):
        self.assertEqual(self.vp.uri, '')

        expected_uri = 'file://test'
        self.vp.uri = expected_uri

        self.assertEqual(self.vp.uri, expected_uri)
        self.assertEqual(self.vp.webkit.get_uri(), self.vp.uri)

    def test_stop(self):
        self.vp.uri = 'http://foo.bar.baz'
        self.vp.stop()

        self.assertEqual(self.vp.webkit.get_uri(), '')


if __name__ == "__main__":
    unittest.main()
