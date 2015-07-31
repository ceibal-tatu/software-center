import unittest

from gi.repository import (
    GLib,
    Soup,
    WebKit,
    )

from mock import patch

from tests.utils import (
    setup_test_env,
)
setup_test_env()

from softwarecenter.enums import WEBKIT_USER_AGENT_SUFFIX
from softwarecenter.ui.gtk3.widgets.webkit import SoftwareCenterWebView


class TestWebkit(unittest.TestCase):

    def test_have_cookie_jar(self):
        # ensure we have a cookie jar available
        session = WebKit.get_default_session()
        cookie_jars = [feature 
                for feature in  session.get_features(Soup.SessionFeature)
                if isinstance(feature, Soup.CookieJar)]
        self.assertEqual(len(cookie_jars), 1)
    
    def test_user_agent_string(self):
        webview = SoftwareCenterWebView()
        settings = webview.get_settings()
        self.assertTrue(
            WEBKIT_USER_AGENT_SUFFIX in settings.get_property("user-agent"))

    @patch("softwarecenter.ui.gtk3.widgets.webkit.get_oem_channel_descriptor")
    def test_user_agent_oem_channel_descriptor(self, mock_oem_channel):
        canary = "she-loves-you-yeah-yeah-yeah"
        mock_oem_channel.return_value = canary
        webview = SoftwareCenterWebView()
        settings = webview.get_settings()
        self.assertTrue(
            canary in settings.get_property("user-agent"))
        
    def test_auto_fill_in_email(self):
        def _load_status_changed(view, status):
            if view.get_property("load-status") == WebKit.LoadStatus.FINISHED:
                loop.quit()
        loop =  GLib.MainLoop(GLib.main_context_default())       
        webview = SoftwareCenterWebView()
        email = "foo@bar"
        webview.set_auto_insert_email(email)
        with patch.object(webview, "execute_script") as mock_execute_js:
            webview.connect("notify::load-status", _load_status_changed)
            webview.load_uri("https://login.ubuntu.com")
            loop.run()
            mock_execute_js.assert_called()
            mock_execute_js.assert_called_with(
                SoftwareCenterWebView.AUTO_FILL_EMAIL_JS % email)


if __name__ == "__main__":
    unittest.main()
