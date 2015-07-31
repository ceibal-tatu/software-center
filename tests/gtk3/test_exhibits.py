import os
import unittest

from mock import patch, Mock

from tests.utils import (
    FakedCache,
    ObjectWithSignals,
    setup_test_env,
)
setup_test_env()


from softwarecenter.db.database import StoreDatabase
from softwarecenter.ui.gtk3.views import lobbyview
from softwarecenter.ui.gtk3.widgets.exhibits import (
    _HtmlRenderer,
    )


class ExhibitsTestCase(unittest.TestCase):
    """The test suite for the exhibits carousel."""

    def setUp(self):
        self.cache = FakedCache()
        self.db = StoreDatabase(cache=self.cache)
        self.lobby = lobbyview.LobbyView(cache=self.cache, db=self.db,
                                         icons=None, apps_filter=None)
        self.addCleanup(self.lobby.destroy)

    def _get_banner_from_lobby(self):
        return self.lobby.vbox.get_children()[-1].get_child()

    def test_featured_exhibit_by_default(self):
        """Show the featured exhibit before querying the remote service."""
        self.lobby._append_banner_ads()

        banner = self._get_banner_from_lobby()
        self.assertEqual(1, len(banner.exhibits))
        self.assertIsInstance(banner.exhibits[0], lobbyview.FeaturedExhibit)

    def test_no_exhibit_if_not_available(self):
        """The exhibit should not be shown if the package is not available."""
        exhibit = Mock()
        exhibit.package_names = u'foobarbaz'

        sca = ObjectWithSignals()
        sca.query_exhibits = lambda: sca.emit('exhibits', sca, [exhibit])

        with patch.object(lobbyview, 'SoftwareCenterAgent', lambda: sca):
            self.lobby._append_banner_ads()

        banner = self._get_banner_from_lobby()
        self.assertEqual(1, len(banner.exhibits))
        self.assertIsInstance(banner.exhibits[0], lobbyview.FeaturedExhibit)

    def test_exhibit_if_available(self):
        """The exhibit should be shown if the package is available."""
        exhibit = Mock()
        exhibit.package_names = u'foobarbaz'
        exhibit.banner_urls = ['banner']
        exhibit.title_translated = ''

        self.cache[u'foobarbaz'] = Mock()

        sca = ObjectWithSignals()
        sca.query_exhibits = lambda: sca.emit('exhibits', sca, [exhibit])

        with patch.object(lobbyview, 'SoftwareCenterAgent', lambda: sca):
            self.lobby._append_banner_ads()

        banner = self._get_banner_from_lobby()
        self.assertEqual(1, len(banner.exhibits))
        self.assertIs(banner.exhibits[0], exhibit)

    def test_exhibit_if_mixed_availability(self):
        """The exhibit should be shown even if some are not available."""
        # available exhibit
        exhibit = Mock()
        exhibit.package_names = u'foobarbaz'
        exhibit.banner_urls = ['banner']
        exhibit.title_translated = ''

        self.cache[u'foobarbaz'] = Mock()

        # not available exhibit
        other = Mock()
        other.package_names = u'not-there'

        sca = ObjectWithSignals()
        sca.query_exhibits = lambda: sca.emit('exhibits', sca,
                                              [exhibit, other])

        with patch.object(lobbyview, 'SoftwareCenterAgent', lambda: sca):
            self.lobby._append_banner_ads()

        banner = self._get_banner_from_lobby()
        self.assertEqual(1, len(banner.exhibits))
        self.assertIs(banner.exhibits[0], exhibit)

    def test_exhibit_with_url(self):
        # available exhibit
        exhibit = Mock()
        exhibit.package_names = ''
        exhibit.click_url = 'http://example.com'
        exhibit.banner_urls = ['banner']
        exhibit.title_translated = ''

        sca = ObjectWithSignals()
        sca.query_exhibits = lambda: sca.emit('exhibits', sca,
                                              [exhibit])

        with patch.object(lobbyview, 'SoftwareCenterAgent', lambda: sca):
            # add the banners
            self.lobby._append_banner_ads()
            # fake click
            alloc = self.lobby.exhibit_banner.get_allocation()
            mock_event = Mock()
            mock_event.x = alloc.x
            mock_event.y = alloc.y
            with patch.object(self.lobby.exhibit_banner, 'emit') as mock_emit:
                self.lobby.exhibit_banner.on_button_press(None, mock_event)
                self.lobby.exhibit_banner.on_button_release(None, mock_event)
                mock_emit.assert_called()
                signal_name = mock_emit.call_args[0][0]
                call_exhibit = mock_emit.call_args[0][1]
                self.assertEqual(signal_name, "show-exhibits-clicked")
                self.assertEqual(call_exhibit.click_url, "http://example.com")

    def test_exhibit_with_featured_exhibit(self):
        """ regression test for bug #1023777 """
        sca = ObjectWithSignals()
        sca.query_exhibits = lambda: sca.emit('exhibits', sca,
                                              [lobbyview.FeaturedExhibit()])

        with patch.object(lobbyview, 'SoftwareCenterAgent', lambda: sca):
            # add the banners
            self.lobby._append_banner_ads()
            # fake click
            alloc = self.lobby.exhibit_banner.get_allocation()
            mock_event = Mock()
            mock_event.x = alloc.x
            mock_event.y = alloc.y
            with patch.object(self.lobby, 'emit') as mock_emit:
                self.lobby.exhibit_banner.on_button_press(None, mock_event)
                self.lobby.exhibit_banner.on_button_release(None, mock_event)
                mock_emit.assert_called()
                signal_name = mock_emit.call_args[0][0]
                call_category = mock_emit.call_args[0][1]
                self.assertEqual(signal_name, "category-selected")
                self.assertEqual(call_category.name, "Our star apps")


class HtmlRendererTestCase(unittest.TestCase):

    def test_multiple_images(self):
        downloader = ObjectWithSignals()
        downloader.download_file = lambda *args, **kwargs: downloader.emit(
            "file-download-complete", downloader, os.path.basename(args[0]))

        with patch("softwarecenter.ui.gtk3.widgets.exhibits."
                   "SimpleFileDownloader", lambda: downloader):
            renderer = _HtmlRenderer()
            mock_exhibit = Mock()
            mock_exhibit.banner_urls = [
                "http://example.com/path1/banner1.png",
                "http://example.com/path2/banner2.png",
                ]
            mock_exhibit.html = "url('/path1/banner1.png')#"\
                                "url('/path2/banner2.png')"

            renderer.set_exhibit(mock_exhibit)
            # assert the stuff we expected to get downloaded got downloaded
            self.assertEqual(
                renderer._downloaded_banner_images,
                ["banner1.png", "banner2.png"])
            # test that the path mangling worked
            self.assertEqual(
                mock_exhibit.html, "url('banner1.png')#url('banner2.png')")

if __name__ == "__main__":
    unittest.main()
