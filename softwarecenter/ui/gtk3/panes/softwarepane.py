# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
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

from gi.repository import Atk
import gettext
from gi.repository import GObject
from gi.repository import Gtk, Gdk
#~ from gi.repository import Cairo
import logging
import xapian

from softwarecenter.backend.installbackend import get_install_backend
from softwarecenter.db.enquire import AppEnquire
from softwarecenter.enums import (
    DEFAULT_SEARCH_LIMIT,
    NonAppVisibility,
    SOFTWARE_CENTER_DEBUG_TABS,
    SortMethods,
)
from softwarecenter.utils import (
    ExecutionTime,
    wait_for_apt_cache_ready,
)

from softwarecenter.ui.gtk3.session.viewmanager import get_viewmanager
from softwarecenter.ui.gtk3.widgets.actionbar import ActionBar
from softwarecenter.ui.gtk3.widgets.spinner import SpinnerNotebook
from softwarecenter.ui.gtk3.widgets.searchaid import SearchAid

from softwarecenter.ui.gtk3.views.appview import AppView

from softwarecenter.ui.gtk3.session.displaystate import DisplayState

from basepane import BasePane

LOG = logging.getLogger(__name__)


class SoftwarePane(Gtk.VBox, BasePane):
    """ Common base class for AvailablePane and InstalledPane"""

    class Pages:
        NAMES = ('appview', 'details', 'spinner')
        APPVIEW = 0
        DETAILS = 1
        SPINNER = 2

    __gsignals__ = {
        "app-list-changed": (GObject.SignalFlags.RUN_LAST,
                             None,
                             (int,),
                             ),
    }
    PADDING = 6

    def __init__(self, cache, db, distro, icons, show_ratings=True):

        Gtk.VBox.__init__(self)
        BasePane.__init__(self)

        # other classes we need
        self.enquirer = AppEnquire(cache, db)
        self._query_complete_handler = self.enquirer.connect(
                            "query-complete", self.on_query_complete)

        self.cache = cache
        self.db = db
        self.distro = distro
        self.icons = icons
        self.show_ratings = show_ratings
        self.backend = get_install_backend()
        self.nonapps_visible = NonAppVisibility.MAYBE_VISIBLE
        # refreshes can happen out-of-bound so we need to be sure
        # that we only set the new model (when its available) if
        # the refresh_seq_nr of the ready model matches that of the
        # request (e.g. people click on ubuntu channel, get impatient, click
        # on partner channel)
        self.refresh_seq_nr = 0
        # this should be initialized
        self.apps_search_term = ""
        # Create the basic frame for the common view
        self.state = DisplayState()
        vm = get_viewmanager()
        self.searchentry = vm.get_global_searchentry()
        self.back_forward = vm.get_global_backforward()
        # a notebook below
        self.notebook = Gtk.Notebook()
        if not SOFTWARE_CENTER_DEBUG_TABS:
            self.notebook.set_show_tabs(False)
        self.notebook.set_show_border(False)
        # make a spinner view to display while the applist is loading
        self.spinner_notebook = SpinnerNotebook(self.notebook)
        self.pack_start(self.spinner_notebook, True, True, 0)

        # add a bar at the bottom (hidden by default) for contextual actions
        self.action_bar = ActionBar()
        self.pack_start(self.action_bar, False, True, 0)

        # cursor
        self.busy_cursor = Gdk.Cursor.new(Gdk.CursorType.WATCH)

        # views to be created in init_view
        self.app_view = None
        self.app_details_view = None

    def init_view(self):
        """
        Initialize those UI components that are common to all subclasses of
        SoftwarePane.  Note that this method is intended to be called by
        the subclass itself at the start of its own init_view() implementation.
        """
        # common UI elements (applist and appdetails)
        # its the job of the Child class to put it into a good location
        # list
        self.box_app_list = Gtk.VBox()

        # search aid
        self.search_aid = SearchAid(self)
        self.box_app_list.pack_start(self.search_aid, False, False, 0)

        with ExecutionTime("SoftwarePane.AppView"):
            self.app_view = AppView(self.db, self.cache,
                                    self.icons, self.show_ratings)
        self.app_view.connect("sort-method-changed",
            self.on_app_view_sort_method_changed)

        self.init_atk_name(self.app_view, "app_view")
        self.box_app_list.pack_start(self.app_view, True, True, 0)
        self.app_view.connect("application-selected",
                              self.on_application_selected)
        self.app_view.connect("application-activated",
                              self.on_application_activated)

        # details
        self.scroll_details = Gtk.ScrolledWindow()
        self.scroll_details.set_policy(Gtk.PolicyType.AUTOMATIC,
                                        Gtk.PolicyType.AUTOMATIC)
        # delayed import gives ~1s speedup until visible on the raspi
        with ExecutionTime("import AppDetailsView"):
            from softwarecenter.ui.gtk3.views.appdetailsview import (
                    AppDetailsView)
        with ExecutionTime("SoftwarePane.AppDetailsView"):
            self.app_details_view = AppDetailsView(self.db,
                                                   self.distro,
                                                   self.icons,
                                                   self.cache)
        self.app_details_view.connect(
            "different-application-selected", self.on_application_activated)
        self.scroll_details.add(self.app_details_view)
        # when the cache changes, refresh the app list
        self.cache.connect("cache-ready", self.on_cache_ready)

        # connect signals
        self.connect("app-list-changed", self.on_app_list_changed)

        # db reopen
        if self.db:
            self.db.connect("reopen", self.on_db_reopen)

    def init_atk_name(self, widget, name):
        """ init the atk name for a given gtk widget based on parent-pane
            and variable name (used for the mago tests)
        """
        name = self.__class__.__name__ + "." + name
        Atk.Object.set_name(widget.get_accessible(), name)

    def on_cache_ready(self, cache):
        """Refresh the application list when the cache is re-opened."""
        LOG.debug("on_cache_ready")

    @wait_for_apt_cache_ready
    def on_application_activated(self, appview, app):
        """Callback when an app is clicked."""
        LOG.debug("%r.on_application_activated: %r",
                  self.__class__.__name__, app)

        self.state.application = app

        vm = get_viewmanager()
        # self.Pages will access the Page definition of each child correctly
        vm.display_page(self, self.Pages.DETAILS, self.state)

    def on_application_selected(self, widget, app):
        """Stub implementation."""
        LOG.debug("%r.on_application_selected: %r",
                  self.__class__.__name__, app)

    def enter_page(self, page, state):
        if page == self.page.DETAILS:
            self.display_details_page(state)

    def is_applist_view_showing(self):
        """Return True if we are in the applist view """
        list_page = getattr(self.Pages, 'LIST', -1)
        return self.notebook.get_current_page() == list_page

    def is_app_details_view_showing(self):
        """Return True if we are in the app_details view."""
        details_page = getattr(self.Pages, 'DETAILS', -1)
        return self.notebook.get_current_page() == details_page

    def show_app(self, app):
        self.on_application_activated(None, app)

    def on_query_complete(self, enquirer):
        self.emit("app-list-changed", len(enquirer.matches))
        self.app_view.display_matches(enquirer.matches,
                                      self._is_in_search_mode())
        self.hide_appview_spinner()

    def on_app_view_sort_method_changed(self, app_view, combo):
        if app_view.get_sort_mode() == self.enquirer.sortmode:
            return

        self.show_appview_spinner()
        app_view.clear_model()
        query = self.get_query()
        self._refresh_apps_with_apt_cache(query)

    def _is_in_search_mode(self):
        return (self.state.search_term and
                len(self.state.search_term) >= 2)

    def show_appview_spinner(self):
        """ display the spinner in the appview panel """
        LOG.debug("show_appview_spinner")
        # FIXME: totally the wrong place!
        if not self.state.search_term:
            self.action_bar.clear()
        self.spinner_notebook.show_spinner()

    def hide_appview_spinner(self):
        """ hide the spinner and display the appview in the panel """
        LOG.debug("hide_appview_spinner")
        self.spinner_notebook.hide_spinner()

    def set_section(self, section):
        self.section = section
        self.app_details_view.set_section(section)

    def section_sync(self):
        self.app_details_view.set_section(self.section)

    def on_app_list_changed(self, pane, length):
        """internal helper that keeps the the action bar up-to-date by
           keeping track of the app-list-changed signals
        """

        self.show_nonapps_if_required(len(self.enquirer.matches))
        self.search_aid.update_search_help(self.state)

    def hide_nonapps(self):
        """ hide non-applications control in the action bar """
        self.action_bar.unset_label()

    def show_nonapps_if_required(self, length):
        """
        update the state of the show/hide non-applications control
        in the action_bar
        """

        enquirer = self.enquirer
        n_apps = enquirer.nr_apps
        n_pkgs = enquirer.nr_pkgs

        # calculate the number of apps/pkgs
        if enquirer.limit > 0 and enquirer.limit < n_pkgs:
            n_apps = min(enquirer.limit, n_apps)
            n_pkgs = min(enquirer.limit - n_apps, n_pkgs)

        if not (n_apps and n_pkgs):
            self.hide_nonapps()
            return

        LOG.debug("nonapps_visible value=%s (always visible: %s)" % (
                self.nonapps_visible,
                self.nonapps_visible == NonAppVisibility.ALWAYS_VISIBLE))

        self.action_bar.unset_label()
        if self.nonapps_visible == NonAppVisibility.ALWAYS_VISIBLE:
            LOG.debug('non-apps-ALWAYS-visible')
            # TRANSLATORS: the text in between the underscores acts as a link
            # In most/all languages you will want the whole string as a link
            label = gettext.ngettext("_Hide %(amount)i technical item_",
                                     "_Hide %(amount)i technical items_",
                                     n_pkgs) % {'amount': n_pkgs}
            self.action_bar.set_label(
                        label, link_result=self._hide_nonapp_pkgs)
        else:
            label = gettext.ngettext("_Show %(amount)i technical item_",
                                     "_Show %(amount)i technical items_",
                                     n_pkgs) % {'amount': n_pkgs}
            self.action_bar.set_label(
                        label, link_result=self._show_nonapp_pkgs)

    def _show_nonapp_pkgs(self):
        self.nonapps_visible = NonAppVisibility.ALWAYS_VISIBLE
        self.refresh_apps()
        return True

    def _hide_nonapp_pkgs(self):
        self.nonapps_visible = NonAppVisibility.MAYBE_VISIBLE
        self.refresh_apps()
        return True

    def get_query(self):
        channel_query = None
        #name = self.pane_name
        if self.channel:
            channel_query = self.channel.query
            #name = self.channel.display_name

        # search terms
        if self.apps_search_term:
            query = self.db.get_query_list_from_search_entry(
                self.apps_search_term, channel_query)

            return query
        # overview list
        # if we are in a channel, limit to that
        if channel_query:
            return channel_query
        # ... otherwise show all
        return xapian.Query("")

    def refresh_apps(self, query=None):
        """refresh the applist and update the navigation bar """
        LOG.debug("refresh_apps")

        # FIXME: make this available for all panes
        if query is None:
            query = self.get_query()

        # this can happen e.g. when opening a deb file, see bug #951238
        if not self.app_view:
            return
        self.app_view.clear_model()
        self.search_aid.reset()
        self.show_appview_spinner()
        self._refresh_apps_with_apt_cache(query)

    def quick_query_len(self, query):
        """ do a blocking query that only returns the amount of
            matches from this query
        """
        with ExecutionTime("enquirer.set_query() quick query"):
            self.enquirer.set_query(
                                query,
                                limit=self.get_app_items_limit(),
                                nonapps_visible=self.nonapps_visible,
                                nonblocking_load=False,
                                filter=self.state.filter)
        return len(self.enquirer.matches)

    @wait_for_apt_cache_ready
    def _refresh_apps_with_apt_cache(self, query):
        LOG.debug("softwarepane query: %s" % query)

        self.app_view.configure_sort_method(self._is_in_search_mode())

        # a nonblocking query calls on_query_complete once finished
        with ExecutionTime("enquirer.set_query()"):
            self.enquirer.set_query(
                                query,
                                limit=self.get_app_items_limit(),
                                sortmode=self.get_sort_mode(),
                                exact=self.is_custom_list(),
                                nonapps_visible=self.nonapps_visible,
                                filter=self.state.filter)

    def display_details_page(self, view_state):
        self.app_details_view.show_app(view_state.application)
        self.action_bar.unset_label()
        return True

    def is_custom_list(self):
        return self.apps_search_term and ',' in self.apps_search_term

    def get_current_page(self):
        return self.notebook.get_current_page()

    def get_app_items_limit(self):
        if self.state.search_term:
            return DEFAULT_SEARCH_LIMIT
        elif self.state.subcategory and self.state.subcategory.item_limit > 0:
            return self.state.subcategory.item_limit
        elif self.state.category and self.state.category.item_limit > 0:
            return self.state.category.item_limit
        return 0

    def get_sort_mode(self):
        # if the category sets a custom sort order, that wins, this
        # is required for top-rated and whats-new
        if (self.state.category and
                self.state.category.sortmode != SortMethods.BY_ALPHABET):
            return self.state.category.sortmode
        # ask the app_view for the sort-mode
        return self.app_view.get_sort_mode()

    def on_search_entry_key_press_event(self, event):
        """callback when a key is pressed in the search entry widget"""
        if not self.is_applist_view_showing():
            return
        if ((event.keyval == Gdk.keyval_from_name("Down") or
                 event.keyval == Gdk.keyval_from_name("KP_Down")) and
                self.is_applist_view_showing() and
                len(self.app_view.tree_view.get_model()) > 0):
            # select the first item in the applist search result
            self.app_view.tree_view.grab_focus()
            self.app_view.tree_view.set_cursor(Gtk.TreePath(),
                                                   None, False)

    def on_search_terms_changed(self, terms):
        """Stub implementation."""

    def on_db_reopen(self, db):
        """Stub implementation."""
        LOG.debug("%r: on_db_reopen (db is %r).", self.__class__.__name__, db)

    def get_current_category(self):
        """Stub implementation."""

    def unset_current_category(self):
        """Stub implementation."""
