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

import gettext
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GLib
import logging
import xapian
import os

import softwarecenter.utils
import softwarecenter.ui.gtk3.dialogs as dialogs
from softwarecenter.ui.gtk3.models.appstore2 import AppListStore

from gettext import gettext as _

from softwarecenter.config import get_config
from softwarecenter.enums import (
    ActionButtons,
    NavButtons,
    NonAppVisibility,
    DEFAULT_SEARCH_LIMIT,
    TransactionTypes,
    PURCHASE_TRANSACTION_ID,
)
from softwarecenter.utils import (
    convert_desktop_file_to_installed_location,
    is_no_display_desktop_file,
    get_exec_line_from_desktop,
    get_file_path_from_iconname,
)
from softwarecenter.db.appfilter import AppFilter
from softwarecenter.db.database import Application

from softwarecenter.ui.gtk3.views.purchaseview import PurchaseView

from softwarecenter.ui.gtk3.views.lobbyview import LobbyView
from softwarecenter.ui.gtk3.views.catview import SubCategoryView
from softwarepane import SoftwarePane
from softwarecenter.ui.gtk3.session.viewmanager import get_viewmanager
from softwarecenter.ui.gtk3.session.appmanager import get_appmanager
from softwarecenter.utils import ExecutionTime

from softwarecenter.backend.channel import SoftwareChannel
from softwarecenter.backend.unitylauncher import (UnityLauncher,
                                                  UnityLauncherInfo)
from softwarecenter.backend.zeitgeist_logger import ZeitgeistLogger

LOG = logging.getLogger(__name__)


class AvailablePane(SoftwarePane):
    """Widget that represents the available panel in software-center
       It contains a search entry and navigation buttons
    """

    class Pages():
        # page names, useful for debugging
        NAMES = ('lobby',
                 'subcategory',
                 'list',
                 'details',
                 'purchase',
                 )
        # actual page id's
        (LOBBY,
         SUBCATEGORY,
         LIST,
         DETAILS,
         PURCHASE,
         PREVIOUS_PURCHASES) = range(6)
        # the default page
        HOME = LOBBY

    __gsignals__ = {'available-pane-created': (GObject.SignalFlags.RUN_FIRST,
                                               None,
                                               ())}

    class TransactionDetails(object):
        """ Simple class to keep track of aptdaemon transaction details """
        def __init__(self, db, pkgname, appname, trans_id, trans_type):
            self.db = db
            self.app = Application(pkgname=pkgname, appname=appname)
            self.trans_id = trans_id
            self.trans_type = trans_type
            self.__app_details = None
            self.__real_desktop = None

            if trans_type != TransactionTypes.INSTALL:
                self.guess_final_desktop_file()

        @property
        def app_details(self):
            if not self.__app_details:
                self.__app_details = self.app.get_details(self.db)
            return self.__app_details

        @property
        def desktop_file(self):
            return self.app_details.desktop_file

        @property
        def final_desktop_file(self):
            return self.guess_final_desktop_file()

        def guess_final_desktop_file(self):
            if self.__real_desktop:
                return self.__real_desktop

            # convert the app-install desktop file location to the actual installed
            # desktop file location (or in the case of a purchased item from the
            # agent, generate the correct installed desktop file location)
            desktop_file = (
                convert_desktop_file_to_installed_location(self.desktop_file,
                                                           self.app.pkgname))
            # we only add items to the launcher that have a desktop file
            if not desktop_file:
                return
            # do not add apps that have no Exec entry in their desktop file
            # (e.g. wine, see LP: #848437 or ubuntu-restricted-extras,
            # see LP: #913756), also, don't add the item if NoDisplay is
            # specified (see LP: #1006483)
            if (os.path.exists(desktop_file) and
                    (not get_exec_line_from_desktop(desktop_file) or
                    is_no_display_desktop_file(desktop_file))):
                return

            self.__real_desktop = desktop_file
            return self.__real_desktop

    def __init__(self,
                 cache,
                 db,
                 distro,
                 icons,
                 navhistory_back_action,
                 navhistory_forward_action):
        # parent
        SoftwarePane.__init__(self, cache, db, distro, icons)
        self.searchentry.set_sensitive(False)
        # navigation history actions
        self.navhistory_back_action = navhistory_back_action
        self.navhistory_forward_action = navhistory_forward_action
        # configure any initial state attrs
        self.state.filter = AppFilter(db, cache)
        # the spec says we mix installed/not installed
        #self.apps_filter.set_not_installed_only(True)
        self.current_app_by_category = {}
        self.current_app_by_subcategory = {}
        self.pane_name = _("Get Software")

        # views to be created in init_view
        self.cat_view = None
        self.subcategories_view = None

        # integrate with the Unity launcher
        self.unity_launcher = UnityLauncher()

        # keep track of transactions
        self.transactions_queue = {}

    def init_view(self):
        if self.view_initialized:
            return

        self.show_appview_spinner()

        window = self.get_window()
        if window is not None:
            window.set_cursor(self.busy_cursor)

        with ExecutionTime("AvailablePane.init_view pending events"):
            while Gtk.events_pending():
                Gtk.main_iteration()

        with ExecutionTime("SoftwarePane.init_view()"):
            SoftwarePane.init_view(self)
        # set the AppTreeView model, available pane uses list models
        with ExecutionTime("create AppListStore"):
            liststore = AppListStore(self.db, self.cache, self.icons)
        #~ def on_appcount_changed(widget, appcount):
            #~ self.subcategories_view._append_appcount(appcount)
            #~ self.app_view._append_appcount(appcount)
        #~ liststore.connect('appcount-changed', on_appcount_changed)
        self.app_view.set_model(liststore)
        liststore.connect("needs-refresh",
            lambda helper, pkgname: self.app_view.queue_draw())

        # purchase view
        self.purchase_view = PurchaseView()
        app_manager = get_appmanager()
        app_manager.connect("purchase-requested",
            self.on_purchase_requested)
        self.purchase_view.connect("purchase-succeeded",
            self.on_purchase_succeeded)
        self.purchase_view.connect("purchase-failed",
            self.on_purchase_failed)
        self.purchase_view.connect("purchase-cancelled-by-user",
            self.on_purchase_cancelled_by_user)
        self.purchase_view.connect("terms-of-service-declined",
            self.on_terms_of_service_declined)
        self.purchase_view.connect("purchase-needs-spinner",
            self.on_purchase_needs_spinner)

        # categories, appview and details into the notebook in the bottom
        self.scroll_categories = Gtk.ScrolledWindow()
        self.scroll_categories.set_policy(Gtk.PolicyType.AUTOMATIC,
                                        Gtk.PolicyType.AUTOMATIC)
        with ExecutionTime("create LobbyView"):
            self.cat_view = LobbyView(
                self.cache, self.db, self.icons, self.apps_filter)
        self.scroll_categories.add(self.cat_view)
        self.notebook.append_page(self.scroll_categories,
            Gtk.Label(label="categories"))

        # sub-categories view
        with ExecutionTime("create SubCategoryView"):
            self.subcategories_view = SubCategoryView(
                self.cache, self.db, self.icons, self.apps_filter,
                root_category=self.cat_view.categories[0])
        self.subcategories_view.connect(
            "category-selected", self.on_subcategory_activated)
        self.subcategories_view.connect(
            "show-category-applist", self.on_show_category_applist)
        self.subcategories_view.connect(
            "application-activated", self.on_application_activated)
        self.scroll_subcategories = Gtk.ScrolledWindow()
        self.scroll_subcategories.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scroll_subcategories.add(self.subcategories_view)
        self.notebook.append_page(self.scroll_subcategories,
                                    Gtk.Label(label=NavButtons.SUBCAT))

        # app list
        self.notebook.append_page(self.box_app_list,
                                    Gtk.Label(label=NavButtons.LIST))

        self.cat_view.connect(
            "category-selected", self.on_category_activated)
        self.cat_view.connect(
            "application-activated", self.on_application_activated)

        # details
        self.notebook.append_page(self.scroll_details,
            Gtk.Label(label=NavButtons.DETAILS))

        # purchase view
        self.notebook.append_page(self.purchase_view,
            Gtk.Label(label=NavButtons.PURCHASE))

        # install backend
        # FIXME: move this out of the available pane really
        self.backend.connect("transaction-started",
            self.on_transaction_started)
        self.backend.connect("transactions-changed",
            self.on_transactions_changed)
        self.backend.connect("transaction-finished",
            self.on_transaction_complete)
        # a transaction error is treated the same as a cancellation
        self.backend.connect("transaction-stopped",
            self.on_transaction_cancelled)
        self.backend.connect("transaction-cancelled",
            self.on_transaction_cancelled)

        # now we are initialized
        self.searchentry.set_sensitive(True)
        self.emit("available-pane-created")
        self.show_all()
        self.hide_appview_spinner()

        # consider the view initialized here already as display_page()
        # may run into a endless recursion otherwise (it will call init_view())
        # again (LP: #851671)
        self.view_initialized = True

        # important to "seed" the initial history stack (LP: #1005104)
        vm = get_viewmanager()
        vm.display_page(self, self.Pages.LOBBY, self.state)

        if window is not None:
            window.set_cursor(None)

    def on_purchase_requested(self, appmanager, app, iconname, url):
        if self.purchase_view.initiate_purchase(app, iconname, url):
            vm = get_viewmanager()
            vm.display_page(self, self.Pages.PURCHASE, self.state)

    def on_purchase_needs_spinner(self, appmanager, active):
        vm = get_viewmanager()
        vm.set_spinner_active(active)

    def on_purchase_succeeded(self, widget):
        # switch to the details page to display the transaction is in progress
        self._return_to_appdetails_view()

    def on_purchase_failed(self, widget):
        self._return_to_appdetails_view()
        dialogs.error(None,
                      _("Failure in the purchase process."),
                      _("Sorry, something went wrong. Your payment "
                        "has been cancelled."))

    def on_purchase_cancelled_by_user(self, widget):
        self._return_to_appdetails_view()

    def on_terms_of_service_declined(self, widget):
        """ The Terms of Service dialog was declined by the user, so we just
            reset the purchase button in case they want another chance
        """
        if self.is_app_details_view_showing():
            self.app_details_view.pkg_statusbar.button.set_sensitive(True)
        elif self.is_applist_view_showing():
            self.app_view.tree_view.reset_action_button()

    def _return_to_appdetails_view(self):
        vm = get_viewmanager()
        vm.nav_back()
        # don't keep the purchase view in navigation history
        # as its contents are no longer valid
        vm.clear_forward_history()
        window = self.get_window()
        if window is not None:
            window.set_cursor(None)

    def get_query(self):
        """helper that gets the query for the current category/search mode"""
        # NoDisplay is a special case
        if self._in_no_display_category():
            return xapian.Query()
        # get current sub-category (or category, but sub-category wins)
        query = None

        if self.state.channel and self.state.channel.query:
            query = self.state.channel.query
        elif self.state.subcategory:
            query = self.state.subcategory.query
        elif self.state.category:
            query = self.state.category.query
        # mix channel/category with the search terms and return query
        return self.db.get_query_list_from_search_entry(
                            self.state.search_term, query)

    def _in_no_display_category(self):
        """return True if we are in a category with NoDisplay set in the XML"""
        return (self.state.category and
                self.state.category.dont_display and
                not self.state.subcategory and
                not self.state.search_term)

    def _get_header_for_view_state(self, view_state):
        channel = view_state.channel
        category = view_state.category
        subcategory = view_state.subcategory

        line1 = None
        line2 = None
        if channel is not None:
            name = channel.display_name or channel.name
            line1 = GLib.markup_escape_text(name)
        elif subcategory is not None:
            line1 = GLib.markup_escape_text(category.name)
            line2 = GLib.markup_escape_text(subcategory.name)
        elif category is not None:
            line1 = GLib.markup_escape_text(category.name)
        else:
            line1 = _("All Software")
        return line1, line2

    #~ def _show_hide_subcategories(self, show_category_applist=False):
        #~ # check if have subcategories and are not in a subcategory
        #~ # view - if so, show it
        #~ current_page = self.notebook.get_current_page()
        #~ if (current_page == self.Pages.LOBBY or
            #~ current_page == self.Pages.DETAILS):
            #~ return
        #~ if (not show_category_applist and
            #~ self.state.category and
            #~ self.state.category.subcategories and
            #~ not (self.state.search_term or self.state.subcategory)):
            #~ self.subcategories_view.set_subcategory(self.state.category,
                #~ num_items=len(self.app_view.get_model()))
            #~ self.notebook.set_current_page(self.Pages.SUBCATEGORY)
        #~ else:
            #~ self.notebook.set_current_page(self.Pages.LIST)

    def get_current_app(self):
        """return the current active application object"""
        if self.is_category_view_showing():
            return None
        else:
            if self.state.subcategory:
                return self.current_app_by_subcategory.get(
                    self.state.subcategory)
            else:
                return self.current_app_by_category.get(self.state.category)

    def get_current_category(self):
        """ return the current category that is in use or None """
        if self.state.subcategory:
            return self.state.subcategory
        elif self.state.category:
            return self.state.category

    def unset_current_category(self):
        """ unset the current showing category, but keep e.g. the current
            search
        """
        self.state.category = None
        self.state.subcategory = None
        # reset the non-global filters see (LP: #985389)
        if self.state.filter:
            self.state.filter.reset()

    def on_transaction_started(self, backend, pkgname, appname, trans_id,
                               trans_type):
        details = self.TransactionDetails(self.db, pkgname, appname, trans_id, trans_type)
        self.transactions_queue[pkgname] = details

        config = get_config()
        if (trans_type == TransactionTypes.INSTALL and
            trans_id != PURCHASE_TRANSACTION_ID and
                config.add_to_unity_launcher and
                softwarecenter.utils.is_unity_running()):
            if details.desktop_file is not None:
                self._add_application_to_unity_launcher(details)

    def on_transaction_cancelled(self, backend, result):
        """ handle a transaction that has been cancelled
        """
        if result.pkgname:
            self.unity_launcher.cancel_application_to_launcher(result.pkgname)
        if result.pkgname in self.transactions_queue:
            self.transactions_queue.pop(result.pkgname)

    def on_transactions_changed(self, backend, pending_transactions):
        """internal helper that keeps the action bar up-to-date by
           keeping track of the transaction-started signals
        """
        if self._is_custom_list_search(self.state.search_term):
            self._update_action_bar()

    def _add_application_to_unity_launcher(self, trans_details):
        # do not add apps that have no Exec entry in their desktop file
        # (e.g. wine, see LP: #848437 or ubuntu-restricted-extras,
        # see LP: #913756), also, don't add the item if NoDisplay is
        # specified (see LP: #1006483)
        if (os.path.exists(trans_details.desktop_file) and
                (not get_exec_line_from_desktop(trans_details.desktop_file) or
                 is_no_display_desktop_file(trans_details.desktop_file))):
            return

        # now gather up the unity launcher info items and send the app to the
        # launcher service
        launcher_info = self._get_unity_launcher_info(trans_details)
        self.unity_launcher.send_application_to_launcher(
            trans_details.app.pkgname, launcher_info)

    def on_transaction_complete(self, backend, result):
        """ handle a transaction that has completed successfully
        """
        if result.pkgname in self.transactions_queue:
            details = self.transactions_queue.pop(result.pkgname)

            if details.trans_type == TransactionTypes.INSTALL:
                ZeitgeistLogger(self.distro).log_install_event(details.final_desktop_file)
            elif details.trans_type == TransactionTypes.REMOVE:
                ZeitgeistLogger(self.distro).log_uninstall_event(details.final_desktop_file)

    def _get_unity_launcher_info(self, trans_details):
        (icon_size, icon_x, icon_y) = (
                self._get_onscreen_icon_details_for_launcher_service(trans_details.app))
        icon_path = get_file_path_from_iconname(
                                self.icons,
                                iconname=trans_details.app_details.icon)
        launcher_info = UnityLauncherInfo(trans_details.app.name,
                                          trans_details.app_details.icon,
                                          icon_path,
                                          icon_x,
                                          icon_y,
                                          icon_size,
                                          trans_details.desktop_file,
                                          trans_details.trans_id)
        return launcher_info

    def _get_onscreen_icon_details_for_launcher_service(self, app):
        if self.is_app_details_view_showing():
            return self.app_details_view.get_app_icon_details()
        elif self.is_applist_view_showing():
            return self.app_view.get_app_icon_details()
        else:
            # set a default, even though we cannot install from the other panes
            return (0, 0, 0)

    def on_app_list_changed(self, pane, length):
        """internal helper that keeps the status text and the action
           bar up-to-date by keeping track of the app-list-changed
           signals
        """
        LOG.debug("applist-changed %s %s" % (pane, length))
        super(AvailablePane, self).on_app_list_changed(pane, length)
        self._update_action_bar()

    def _update_action_bar(self):
        self._update_action_bar_buttons()

    def _update_action_bar_buttons(self):
        """Update buttons in the action bar to implement the custom package
           lists feature, see
           https://wiki.ubuntu.com/SoftwareCenter#Custom%20package%20lists
        """
        if self._is_custom_list_search(self.state.search_term):
            installable = []
            for doc in self.enquirer.get_documents():
                pkgname = self.db.get_pkgname(doc)
                if (pkgname in self.cache and
                        not self.cache[pkgname].is_installed and
                        not len(self.backend.pending_transactions) > 0):
                    app = Application(pkgname=pkgname)
                    installable.append(app)
            button_text = gettext.ngettext(
                "Install %(amount)s Item",
                "Install %(amount)s Items",
                len(installable)) % {'amount': len(installable)}
            button = self.action_bar.get_button(ActionButtons.INSTALL)
            if button and installable:
                # Install all already offered. Update offer.
                if button.get_label() != button_text:
                    button.set_label(button_text)
            elif installable:
                # Install all not yet offered. Offer.
                self.action_bar.add_button(ActionButtons.INSTALL, button_text,
                                           self._install_current_appstore)
            else:
                # Install offered, but nothing to install. Clear offer.
                self.action_bar.remove_button(ActionButtons.INSTALL)
        else:
            # Ensure button is removed.
            self.action_bar.remove_button(ActionButtons.INSTALL)

    def _install_current_appstore(self):
        '''
        Function that installs all applications displayed in the pane.
        '''
        apps = []
        iconnames = []
        self.action_bar.remove_button(ActionButtons.INSTALL)
        for doc in self.enquirer.get_documents():
            pkgname = self.db.get_pkgname(doc)
            if (pkgname in self.cache and
                    not self.cache[pkgname].is_installed and
                    pkgname not in self.backend.pending_transactions):
                apps.append(self.db.get_application(doc))
                # add iconnames
                iconnames.append(self.db.get_iconname(doc))
        self.backend.install_multiple(apps, iconnames)

    def _show_or_hide_search_combo_box(self, view_state):
        # show/hide the sort combobox headers if the category forces a
        # custom sort mode
        category = view_state.category
        allow_user_sort = category is None or not category.is_forced_sort_mode
        self.app_view.set_allow_user_sorting(allow_user_sort)

    def set_state(self, nav_item):
        pass

    def _clear_search(self):
        self.searchentry.clear_with_no_signal()
        self.apps_limit = 0
        self.apps_search_term = ""
        self.state.search_term = ""

    def _is_custom_list_search(self, search_term):
        return (search_term and
                ',' in search_term)

    # callbacks
    def on_cache_ready(self, cache):
        """ refresh the application list when the cache is re-opened """
        # just re-draw in the available pane, nothing but the
        # "is-installed" overlay icon will change when something
        # is installed or removed in the available pane
        self.app_view.queue_draw()

    def on_search_terms_changed(self, widget, new_text):
        """callback when the search entry widget changes"""
        LOG.debug("on_search_terms_changed: %s" % new_text)

        # reset the flag in the app_view because each new search should
        # reset the sort criteria
        self.app_view.reset_default_sort_mode()

        self.state.search_term = new_text

        # do not hide technical items for a custom list search
        if self._is_custom_list_search(self.state.search_term):
            self.nonapps_visible = NonAppVisibility.ALWAYS_VISIBLE

        vm = get_viewmanager()
        adj = self.app_view.tree_view_scroll.get_vadjustment()
        if adj:
            adj.set_value(0.0)

        # yeah for special cases - as discussed on irc, mpt
        # wants this to return to the category screen *if*
        # we are searching but we are not in any category or channel
        if not self.state.category and not self.state.channel and not new_text:
            # category activate will clear search etc
            self.state.reset()
            vm.display_page(self, self.Pages.LOBBY, self.state)
        elif self.state.subcategory and not new_text:
            vm.display_page(self, self.Pages.LIST, self.state)
        elif (self.state.category and
              self.state.category.subcategories and not new_text):
            vm.display_page(self, self.Pages.SUBCATEGORY, self.state)
        else:
            vm.display_page(self, self.Pages.LIST, self.state)

        return False

    def on_db_reopen(self, db):
        """Called when the database is reopened."""
        super(AvailablePane, self).on_db_reopen(db)
        self.refresh_apps()
        if self.app_details_view:
            self.app_details_view.refresh_app()

    def enter_page(self, page, state):
        if page == self.Pages.LIST:
            if state.search_term:
                self.display_search_page(state)
            else:
                self.display_app_view_page(state)
        elif page == self.Pages.SUBCATEGORY:
            self.display_subcategory_page(state)
        elif page == self.Pages.DETAILS:
            self.display_details_page(state)
        elif page == self.Pages.PURCHASE:
            self.display_purchase(state)
        elif page == self.Pages.SUBCATEGORY:
            self.display_subcategory_page(state)
        elif page == self.Pages.PREVIOUS_PURCHASES:
            self.display_previous_purchases(state)
        else:
            # page is self.Pages.LOBBY or unknown
            self.display_lobby_page(state)

    def leave_page(self, state):
        # if previous page is a list view, then store the scroll positions
        if self.is_applist_view_showing():
            # store last adjustment to use later
            v = self.app_view.tree_view_scroll.get_vadjustment()
            self.state.vadjustment = v.get_value()
        elif self.is_app_details_view_showing():
            self.app_details_view.videoplayer.stop()

    def display_lobby_page(self, view_state):
        self.state.reset()
        self.hide_appview_spinner()
        self.emit("app-list-changed", len(self.db))
        self._clear_search()
        self.action_bar.clear()
        return True

    def display_list_page(self, view_state):
        header_strings = self._get_header_for_view_state(view_state)
        self.app_view.set_header_labels(*header_strings)
        self._show_or_hide_search_combo_box(view_state)

        self.app_view.vadj = view_state.vadjustment

        self.refresh_apps()
        return True

    def display_search_page(self, view_state):
        new_text = view_state.search_term
        # DTRT if the search is reset
        if not new_text:
            self._clear_search()
        else:
            self.state.limit = DEFAULT_SEARCH_LIMIT

        return self.display_list_page(view_state)

    def display_subcategory_page(self, view_state):
        category = view_state.category
        self.set_category(category)
        if self.state.search_term or self.searchentry.get_text():
            self._clear_search()
            self.refresh_apps()

        query = self.get_query()
        n_matches = self.quick_query_len(query)
        self.subcategories_view.set_subcategory(category, n_matches)

        self.action_bar.clear()
        return True

    def display_app_view_page(self, view_state):
        category = view_state.category
        subcategory = view_state.subcategory
        self.set_category(category)
        self.set_subcategory(subcategory)

        result = self.display_list_page(view_state)

        if view_state.search_term:
            self._clear_search()

        return result

    def display_details_page(self, view_state):
        if self.searchentry.get_text() != self.state.search_term:
            self.searchentry.set_text_with_no_signal(self.state.search_term)

        self.action_bar.clear()

        SoftwarePane.display_details_page(self, view_state)
        return True

    def display_purchase(self, view_state):
        self.notebook.set_current_page(self.Pages.PURCHASE)
        self.action_bar.clear()

    def display_previous_purchases(self, view_state):
        self.nonapps_visible = NonAppVisibility.ALWAYS_VISIBLE
        header_strings = self._get_header_for_view_state(view_state)
        self.app_view.set_header_labels(*header_strings)
        self.notebook.set_current_page(self.Pages.LIST)
        # clear any search terms
        self._clear_search()
        self.refresh_apps()
        self.action_bar.clear()
        return True

    def on_subcategory_activated(self, subcat_view, category):
        LOG.debug("on_subcategory_activated: %s %s" % (
                category.name, category))
        self.state.subcategory = category
        self.state.application = None
        page = AvailablePane.Pages.LIST

        vm = get_viewmanager()
        vm.display_page(self, page, self.state)

    def on_category_activated(self, lobby_view, category):
        """ callback when a category is selected """
        LOG.debug("on_category_activated: %s %s" % (
                category.name, category))

        if category.subcategories:
            page = self.Pages.SUBCATEGORY
        else:
            page = self.Pages.LIST

        self.state.category = category
        self.state.subcategory = None
        self.state.application = None

        vm = get_viewmanager()
        vm.display_page(self, page, self.state)

    def on_application_activated(self, appview, app):
        """Callback for when an app is activated."""
        super(AvailablePane, self).on_application_activated(appview, app)
        if self.state.subcategory:
            self.current_app_by_subcategory[self.state.subcategory] = app
        else:
            self.current_app_by_category[self.state.category] = app

    def on_show_category_applist(self, widget):
        self._show_hide_subcategories(show_category_applist=True)

    def on_previous_purchases_activated(self, query):
        """ called to activate the previous purchases view """
        #print cat_view, name, query
        LOG.debug("on_previous_purchases_activated with query: %s" % query)
        self.state.channel = SoftwareChannel("Previous Purchases",
                                             "software-center-agent",
                                             None, channel_query=query)
        vm = get_viewmanager()
        vm.display_page(self, self.Pages.PREVIOUS_PURCHASES, self.state)

    def is_category_view_showing(self):
        """Return whether a category/sub-category page is being displayed."""
        current_page = self.notebook.get_current_page()
        return current_page in (self.Pages.LOBBY, self.Pages.SUBCATEGORY)

    def is_purchase_view_showing(self):
        """Return whether a purchase page is being displayed."""
        current_page = self.notebook.get_current_page()
        return current_page == self.Pages.PURCHASE

    def set_subcategory(self, subcategory):
        LOG.debug('set_subcategory: %s' % subcategory)
        self.state.subcategory = subcategory
        self._apply_filters_for_category_or_subcategory(subcategory)

    def set_category(self, category):
        LOG.debug('set_category: %s' % category)
        self.state.category = category
        self._apply_filters_for_category_or_subcategory(category)

    def _apply_filters_for_category_or_subcategory(self, category):
        # apply flags
        if category:
            if 'nonapps-visible' in category.flags:
                self.nonapps_visible = NonAppVisibility.ALWAYS_VISIBLE
            else:
                self.nonapps_visible = NonAppVisibility.MAYBE_VISIBLE

        # apply any category based filters
        if not self.state.filter:
            self.state.filter = AppFilter(self.db, self.cache)

        if (category and category.flags and
                'available-only' in category.flags):
            self.state.filter.set_available_only(True)
        else:
            self.state.filter.set_available_only(False)

        if (category and category.flags and
                'not-installed-only' in category.flags):
            self.state.filter.set_not_installed_only(True)
        else:
            self.state.filter.set_not_installed_only(False)

    def refresh_apps(self, query=None):
        SoftwarePane.refresh_apps(self, query)
        # tell the lobby to update its content
        if self.cat_view:
            self.cat_view.refresh_apps()
        # and the subcat view as well...
        if self.subcategories_view:
            self.subcategories_view.refresh_apps()
