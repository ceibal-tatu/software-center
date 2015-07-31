# Copyright (C) 2009 Canonical
#
# Authors:
#  Matthew McGowan
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
from gi.repository import Gtk, GLib
import logging
import webbrowser
import xapian

from gettext import gettext as _

from softwarecenter.db.application import Application
from softwarecenter.enums import (
    TOP_RATED_CAROUSEL_LIMIT,
    WHATS_NEW_CAROUSEL_LIMIT,
)
from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.widgets.containers import (
                                        FramedHeaderBox,
                                        FramedBox,
                                        TileGrid)
from softwarecenter.ui.gtk3.widgets.exhibits import (
                                        ExhibitBanner, FeaturedExhibit)
from softwarecenter.ui.gtk3.widgets.recommendations import (
                                        RecommendationsPanelLobby)
from softwarecenter.ui.gtk3.widgets.buttons import LabelTile
from softwarecenter.db.appfilter import get_global_filter
from softwarecenter.db.enquire import AppEnquire
from softwarecenter.db.categories import (Category,
                                          CategoriesParser,
                                          get_category_by_name,
                                          categories_sorted_by_name)
from softwarecenter.distro import get_distro
from softwarecenter.backend.scagent import SoftwareCenterAgent
from softwarecenter.backend.reviews import get_review_loader


LOG = logging.getLogger(__name__)


from .catview import CategoriesView

_asset_cache = {}


class LobbyView(CategoriesView):

    def __init__(self, cache, db, icons,
                 apps_filter, apps_limit=0):
        CategoriesView.__init__(self, cache, db, icons, apps_filter,
                                apps_limit=0)
        self.top_rated = None
        self.exhibit_banner = None

        # sections
        self.departments = None
        self.appcount = None

        # get categories
        self.categories_parser = CategoriesParser(db)
        self.categories = self.categories_parser.parse_applications_menu()

        # build before connecting the signals to avoid race
        self.build()

        # ensure that on db-reopen we refresh the whats-new titles
        self.db.connect("reopen", self._on_db_reopen)

        # ensure that updates to the stats are reflected in the UI
        self.reviews_loader = get_review_loader(self.cache)
        self.reviews_loader.connect(
            "refresh-review-stats-finished", self._on_refresh_review_stats)

    def _on_db_reopen(self, db):
        self._update_whats_new_content()

    def _on_refresh_review_stats(self, reviews_loader, review_stats):
        self._update_top_rated_content()

    def _build_homepage_view(self):
        # these methods add sections to the page
        # changing order of methods changes order that they appear in the page
        self._append_banner_ads()

        self.top_hbox = Gtk.HBox(spacing=StockEms.SMALL)
        top_hbox_alignment = Gtk.Alignment()
        top_hbox_alignment.set_padding(0, 0, StockEms.MEDIUM - 2,
            StockEms.MEDIUM - 2)
        top_hbox_alignment.add(self.top_hbox)
        self.vbox.pack_start(top_hbox_alignment, False, False, 0)

        self._append_departments()

        self.right_column = Gtk.Box.new(Gtk.Orientation.VERTICAL, self.SPACING)
        self.top_hbox.pack_start(self.right_column, True, True, 0)
        self.bottom_hbox = Gtk.HBox(spacing=StockEms.SMALL)
        bottom_hbox_alignment = Gtk.Alignment()
        bottom_hbox_alignment.set_padding(
            StockEms.SMALL, 0,
            StockEms.MEDIUM - 2,
            StockEms.MEDIUM - 2)
        bottom_hbox_alignment.add(self.bottom_hbox)
        self.vbox.pack_start(bottom_hbox_alignment, False, False, 0)

        self._append_whats_new()
        self._append_top_rated()
        self._append_recommended_for_you()
        self._append_appcount()

    def _on_show_exhibits(self, exhibit_banner, exhibit):
        pkgs = exhibit.package_names.split(",")
        url = exhibit.click_url
        if url:
            webbrowser.open_new_tab(url)
        elif len(pkgs) == 1:
            app = Application("", pkgs[0])
            self.emit("application-activated", app)
        else:
            query = self.db.get_query_for_pkgnames(pkgs)
            title = exhibit.title_translated
            untranslated_name = exhibit.package_names
            # create a temp query
            cat = Category(untranslated_name, title, None, query,
                           flags=['nonapps-visible'])
            self.emit("category-selected", cat)

    def _filter_and_set_exhibits(self, sca_client, exhibit_list):
        result = []
        # filter out those exhibits that are not available in this run
        for exhibit in exhibit_list:
            if not exhibit.package_names:
                result.append(exhibit)
            else:
                available = all(self.db.is_pkgname_known(p) for p in
                                exhibit.package_names.split(','))
                if available:
                    result.append(exhibit)
                else:
                    LOG.warn("skipping exhibit for: '%r' not available" % (
                            exhibit.package_names))

        # its ok if result is empty, since set_exhibits() will ignore
        # empty lists
        self.exhibit_banner.set_exhibits(result)

    def _append_banner_ads(self):
        self.exhibit_banner = ExhibitBanner()
        self.exhibit_banner.set_exhibits([FeaturedExhibit()])
        self.exhibit_banner.connect(
            "show-exhibits-clicked", self._on_show_exhibits)

        # query using the agent
        scagent = SoftwareCenterAgent()
        scagent.connect("exhibits", self._filter_and_set_exhibits)
        scagent.query_exhibits()

        a = Gtk.Alignment()
        a.set_padding(0, StockEms.SMALL, 0, 0)
        a.add(self.exhibit_banner)
        self.vbox.pack_start(a, False, False, 0)

    def _append_departments(self):
        # set the departments section to use the label markup we have just
        # defined
        cat_vbox = FramedBox(Gtk.Orientation.VERTICAL)
        self.top_hbox.pack_start(cat_vbox, False, False, 0)

        # sort Category.name's alphabetically
        sorted_cats = categories_sorted_by_name(self.categories)

        mrkup = "<small>%s</small>"
        for cat in sorted_cats:
            if 'carousel-only' in cat.flags:
                continue
            category_name = mrkup % GLib.markup_escape_text(cat.name)
            label = LabelTile(category_name, None)
            label.label.set_margin_left(StockEms.SMALL)
            label.label.set_margin_right(StockEms.SMALL)
            label.label.set_alignment(0.0, 0.5)
            label.label.set_use_markup(True)
            label.connect('clicked', self.on_category_clicked, cat)
            cat_vbox.pack_start(label, False, False, 0)
        return

    # FIXME: _update_{top_rated,whats_new,recommended_for_you}_content()
    #        duplicates a lot of code
    def _update_top_rated_content(self):
        # remove any existing children from the grid widget
        self.top_rated.remove_all()
        # get top_rated category and docs
        top_rated_cat = get_category_by_name(
            self.categories, u"Top Rated")  # untranslated name
        if top_rated_cat:
            docs = top_rated_cat.get_documents(self.db)
            self.top_rated.add_tiles(self.properties_helper,
                                     docs,
                                     TOP_RATED_CAROUSEL_LIMIT)
            self.top_rated.show_all()
        return top_rated_cat

    def _append_top_rated(self):
        self.top_rated = TileGrid()
        self.top_rated.connect("application-activated",
                               self.on_application_activated)
        #~ self.top_rated.row_spacing = StockEms.SMALL
        self.top_rated_frame = FramedHeaderBox()
        self.top_rated_frame.set_header_label(_("Top Rated"))
        self.top_rated_frame.add(self.top_rated)
        self.bottom_hbox.pack_start(self.top_rated_frame, True, True, 0)
        top_rated_cat = self._update_top_rated_content()
        # only display the 'More' LinkButton if we have top_rated content
        if top_rated_cat is not None:
            self.top_rated_frame.header_implements_more_button()
            self.top_rated_frame.more.connect('clicked',
                               self.on_category_clicked, top_rated_cat)

    def _update_whats_new_content(self):
        # remove any existing children from the grid widget
        self.whats_new.remove_all()
        # get top_rated category and docs
        whats_new_cat = get_category_by_name(
            self.categories, u"What\u2019s New")  # untranslated name
        if whats_new_cat:
            docs = whats_new_cat.get_documents(self.db)
            self.whats_new.add_tiles(self.properties_helper,
                                     docs,
                                     WHATS_NEW_CAROUSEL_LIMIT)
            self.whats_new.show_all()
        return whats_new_cat

    def _append_whats_new(self):
        self.whats_new = TileGrid()
        self.whats_new.connect("application-activated",
                               self.on_application_activated)
        self.whats_new_frame = FramedHeaderBox()
        self.whats_new_frame.set_header_label(_(u"What\u2019s New"))
        self.whats_new_frame.add(self.whats_new)

        whats_new_cat = self._update_whats_new_content()
        if whats_new_cat is not None:
            # only add to the visible right_frame if we actually have it
            self.right_column.pack_start(self.whats_new_frame, True, True, 0)
            self.whats_new_frame.header_implements_more_button()
            self.whats_new_frame.more.connect(
                'clicked', self.on_category_clicked, whats_new_cat)

    def _update_recommended_for_you_content(self):
        if (self.recommended_for_you_panel and
                self.recommended_for_you_panel.get_parent()):
            # disconnect listeners
            self.recommended_for_you_panel.disconnect_by_func(
                    self.on_application_activated)
            self.recommended_for_you_panel.disconnect_by_func(
                    self.on_category_clicked)
            # and remove the panel
            self.right_column.remove(self.recommended_for_you_panel)
        self.recommended_for_you_panel = RecommendationsPanelLobby(
                self.db,
                self.properties_helper)
        self.recommended_for_you_panel.connect("application-activated",
                                               self.on_application_activated)
        self.recommended_for_you_panel.connect(
                'more-button-clicked',
                self.on_category_clicked)
        # until bug #1048912 with the testcase in
        #    tests/gtk3/test_lp1048912.py
        # is fixed this workaround for the drawing code in FramedHeaderBox
        # is needed
        self.recommended_for_you_panel.connect(
            "size-allocate", self._on_recommended_for_you_panel_size_allocate)
        self.right_column.pack_start(self.recommended_for_you_panel,
                                    True, True, 0)

    def _on_recommended_for_you_panel_size_allocate(self, rec_panel, stuff):
        """This workaround can go once the root cause for bug #1048912 is
           found, see also tests/gtk3/test_lp1048912.py
        """
        self.queue_draw()

    def _append_recommended_for_you(self):
        # update will (re)create the widget from scratch
        self.recommended_for_you_panel = None
        self._update_recommended_for_you_content()

    def _update_appcount(self):
        enq = AppEnquire(self.cache, self.db)

        distro = get_distro()
        if get_global_filter().supported_only:
            query = distro.get_supported_query()
        else:
            query = xapian.Query('')

        length = enq.get_estimated_matches_count(query)
        text = gettext.ngettext("%(amount)s item", "%(amount)s items", length
                                ) % {'amount': length}
        self.appcount.set_text(text)

    def _append_appcount(self):
        self.appcount = Gtk.Label()
        self.appcount.set_alignment(0.5, 0.5)
        self.appcount.set_margin_top(1)
        self.appcount.set_margin_bottom(4)
        self.vbox.pack_start(self.appcount, False, True, 0)
        self._update_appcount()
        return

    def build(self):
        self.header = _('Departments')
        self._build_homepage_view()
        self.show_all()
        return

    def refresh_apps(self):
        supported_only = get_global_filter().supported_only
        if (self._supported_only == supported_only):
            return
        self._supported_only = supported_only

        self._update_top_rated_content()
        self._update_whats_new_content()
        self._update_recommended_for_you_content()
        self._update_appcount()
        return
