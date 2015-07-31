# Copyright (C) 2010 Canonical
#
# Authors:
#  Michael Vogt
#  Gary Lasker
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import logging
import os

from gi.repository import WebKit as webkit
from gi.repository import Gtk
from gi.repository import Pango
import urlparse

from softwarecenter.i18n import get_language
from softwarecenter.paths import SOFTWARE_CENTER_CACHE_DIR
from softwarecenter.enums import WEBKIT_USER_AGENT_SUFFIX
from softwarecenter.utils import get_oem_channel_descriptor

from gi.repository import Soup
from gi.repository import WebKit


LOG = logging.getLogger(__name__)


def global_webkit_init():
    """ this sets the defaults for webkit, its important that this gets
        run if you want a secure webkit session
    """
    session = WebKit.get_default_session()
    # add security by default (see bugzilla #666280 and #666276)
    # enable certificates validation in webkit views unless specified otherwise
    if not "SOFTWARE_CENTER_FORCE_DISABLE_CERTS_CHECK" in os.environ:
        session = webkit.get_default_session()
        session.set_property(
            "ssl-ca-file", "/etc/ssl/certs/ca-certificates.crt")
    else:
        # WARN the user!! Do not remove this
        LOG.warning("SOFTWARE_CENTER_FORCE_DISABLE_CERTS_CHECK " +
                    "has been specified, all purchase transactions " +
                    "are now INSECURE and UNENCRYPTED!!")
    # cookies by default
    fname = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "cookies.txt")
    # clear cookies again in a new session, see #1018347 comment #4
    # there is no "logout" support right now on any of the USC pages
    try:
        os.remove(fname)
    except OSError:
        pass
    cookie_jar = Soup.CookieJarText.new(fname, False)
    session.add_feature(cookie_jar)
    # optional session debugging
    if "SOFTWARE_CENTER_DEBUG_WEBKIT" in os.environ:
        # alternatively you can use HEADERS, BODY here
        logger = Soup.Logger.new(Soup.LoggerLogLevel.BODY, -1)
        logger.attach(session)
# ALWAYS run this or get insecurity by default
global_webkit_init()


class SoftwareCenterWebView(webkit.WebView):
    """ A customized version of the regular webview

    It will:
    - send Accept-Language headers from the users language
    - disable plugins
    - send a custom user-agent string
    - auto-fill in id_email in login.ubuntu.com
    """

    # javascript to auto fill email login on login.ubuntu.com
    AUTO_FILL_SERVER = "https://login.ubuntu.com"
    AUTO_FILL_EMAIL_JS = """
document.getElementById("id_email").value="%s";
document.getElementById("id_password").focus();
"""

    def __init__(self):
        # actual webkit init
        webkit.WebView.__init__(self)
        self.connect("resource-request-starting",
                     self._on_resource_request_starting)
        self.connect("notify::load-status",
            self._on_load_status_changed)
        settings = self.get_settings()
        settings.set_property("enable-plugins", False)
        settings.set_property("user-agent", self._get_user_agent_string())
        self._auto_fill_email = ""

    def set_auto_insert_email(self, email):
        self._auto_fill_email = email

    def _get_user_agent_string(self):
        settings = self.get_settings()
        user_agent_string = settings.get_property("user-agent")
        user_agent_string += " %s " % WEBKIT_USER_AGENT_SUFFIX
        user_agent_string += get_oem_channel_descriptor()
        return user_agent_string

    def _on_resource_request_starting(self, view, frame, res, req, resp):
        lang = get_language()
        if lang:
            message = req.get_message()
            if message:
                headers = message.get_property("request-headers")
                headers.append("Accept-Language", lang)
        #def _show_header(name, value, data):
        #    print name, value
        #headers.foreach(_show_header, None)

    def _maybe_auto_fill_in_username(self):
        uri = self.get_uri()
        if self._auto_fill_email and uri.startswith(self.AUTO_FILL_SERVER):
            self.execute_script(
                self.AUTO_FILL_EMAIL_JS % self._auto_fill_email)
            # ensure that we have the keyboard focus
            self.grab_focus()

    def _on_load_status_changed(self, view, pspec):
        prop = pspec.name
        status = view.get_property(prop)
        if status == webkit.LoadStatus.FINISHED:
            self._maybe_auto_fill_in_username()


class ScrolledWebkitWindow(Gtk.VBox):

    def __init__(self, include_progress_ui=False):
        super(ScrolledWebkitWindow, self).__init__()
        # get webkit
        self.webkit = SoftwareCenterWebView()
        # add progress UI if needed
        if include_progress_ui:
            self._add_progress_ui()
        # create main webkitview
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC,
                               Gtk.PolicyType.AUTOMATIC)
        self.pack_start(self.scroll, True, True, 0)
        # embed the webkit view in a scrolled window
        self.scroll.add(self.webkit)
        self.show_all()

    def _add_progress_ui(self):
        # create toolbar box
        self.header = Gtk.HBox()
        # add spinner
        self.spinner = Gtk.Spinner()
        self.header.pack_start(self.spinner, False, False, 6)
        # add a url to the toolbar
        self.url = Gtk.Label()
        self.url.set_ellipsize(Pango.EllipsizeMode.END)
        self.url.set_alignment(0.0, 0.5)
        self.url.set_text("")
        self.header.pack_start(self.url, True, True, 0)
        # frame around the box
        self.frame = Gtk.Frame()
        self.frame.set_border_width(3)
        self.frame.add(self.header)
        self.pack_start(self.frame, False, False, 6)
        # connect the webkit stuff
        self.webkit.connect("notify::uri", self._on_uri_changed)
        self.webkit.connect("notify::load-status",
            self._on_load_status_changed)

    def _on_uri_changed(self, view, pspec):
        prop = pspec.name
        uri = view.get_property(prop)
        # the full uri is irrelevant for the purchase view, but it is
        # interesting to know what protocol/netloc is in use so that the
        # user can verify its https on sites he is expecting
        scheme, netloc, path, params, query, frag = urlparse.urlparse(uri)
        if scheme == "file" and netloc == "":
            self.url.set_text("")
        else:
            self.url.set_text("%s://%s" % (scheme, netloc))
        # start spinner when the uri changes
        #self.spinner.start()

    def _on_load_status_changed(self, view, pspec):
        prop = pspec.name
        status = view.get_property(prop)
        #print status
        if status == webkit.LoadStatus.PROVISIONAL:
            self.spinner.start()
            self.spinner.show()
        if (status == webkit.LoadStatus.FINISHED or
                status == webkit.LoadStatus.FAILED):
            self.spinner.stop()
            self.spinner.hide()
