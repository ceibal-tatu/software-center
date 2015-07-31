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

import cairo
import gettext
from gi.repository import Gtk, GObject, GLib
import logging
import os
import xapian

from gettext import gettext as _

import softwarecenter.paths
from softwarecenter.enums import (
    NonAppVisibility,
    SortMethods,
    TOP_RATED_CAROUSEL_LIMIT,
)
from softwarecenter.utils import wait_for_apt_cache_ready
from softwarecenter.ui.gtk3.models.appstore2 import AppPropertiesHelper
from softwarecenter.ui.gtk3.widgets.viewport import Viewport
from softwarecenter.ui.gtk3.widgets.containers import (
    FramedHeaderBox,
    FramedBox,
    TileGrid)
from softwarecenter.ui.gtk3.widgets.recommendations import (
    RecommendationsPanelCategory)
from softwarecenter.ui.gtk3.widgets.buttons import CategoryTile
from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.db.appfilter import AppFilter, get_global_filter
from softwarecenter.db.enquire import AppEnquire
from softwarecenter.db.categories import (
    Category,
    categories_sorted_by_name)
from softwarecenter.distro import get_distro

LOG = logging.getLogger(__name__)


_asset_cache = {}


class CategoriesView(Viewport):

    __gsignals__ = {
        "category-selected": (GObject.SignalFlags.RUN_LAST,
                              None,
                              (GObject.TYPE_PYOBJECT, ),
                              ),

        "application-activated": (GObject.SignalFlags.RUN_LAST,
                                  None,
                                  (GObject.TYPE_PYOBJECT, ),
                                  ),

        "show-category-applist": (GObject.SignalFlags.RUN_LAST,
                                  None,
                                  (),)
    }

    SPACING = PADDING = 3

    # art stuff
    STIPPLE = os.path.join(softwarecenter.paths.datadir,
                           "ui/gtk3/art/stipple.png")

    def __init__(self,
                 cache,
                 db,
                 icons,
                 apps_filter=None,  # FIXME: kill this, its not needed anymore?
                 apps_limit=0):

        """ init the widget, takes

        db - a Database object
        icons - a Gtk.IconTheme
        apps_filter - ?
        apps_limit - the maximum amount of items to display to query for
        """
        self.cache = cache
        self.db = db
        self.icons = icons
        self.properties_helper = AppPropertiesHelper(
            self.db, self.cache, self.icons)
        self.section = None

        Viewport.__init__(self)
        self.set_name("category-view")

        # setup base widgets
        # we have our own viewport so we know when the viewport grows/shrinks
        # setup widgets

        self.vbox = Gtk.VBox()
        self.add(self.vbox)

        # atk stuff
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Departments"))

        # appstore stuff
        self.categories = []
        self.header = ""
        #~ self.apps_filter = apps_filter
        self.apps_limit = apps_limit
        # for comparing on refreshes
        self._supported_only = False

        # more stuff
        self._poster_sigs = []
        self._allocation = None

        self._cache_art_assets()
        #~ assets = self._cache_art_assets()
        #~ self.vbox.connect("draw", self.on_draw, assets)
        self._prev_alloc = None
        self.connect("size-allocate", self.on_size_allocate)
        return

    def on_size_allocate(self, widget, _):
        a = widget.get_allocation()
        prev = self._prev_alloc
        if prev is None or a.width != prev.width or a.height != prev.height:
            self._prev_alloc = a
            self.queue_draw()
        return

    def _cache_art_assets(self):
        global _asset_cache
        if _asset_cache:
            return _asset_cache
        assets = _asset_cache
        # cache the bg pattern
        surf = cairo.ImageSurface.create_from_png(self.STIPPLE)
        ptrn = cairo.SurfacePattern(surf)
        ptrn.set_extend(cairo.EXTEND_REPEAT)
        assets["stipple"] = ptrn
        return assets

    def on_application_activated(self, btn, app):
        """ pass the application-activated signal along when an application
            is clicked-through in one of the tiles
        """
        def timeout_emit():
            self.emit("application-activated", app)
            return False

        GLib.timeout_add(50, timeout_emit)

    def on_category_clicked(self, btn, cat):
        """emit the category-selected signal when a category was clicked"""
        def timeout_emit():
            self.emit("category-selected", cat)
            return False

        GLib.timeout_add(50, timeout_emit)

    def do_draw(self, cr):
        cr.save()
        cr.set_source(_asset_cache["stipple"])
        cr.paint_with_alpha(0.5)
        cr.restore()
        for child in self:
            self.propagate_draw(child, cr)

    def set_section(self, section):
        self.section = section

    def refresh_apps(self):
        raise NotImplementedError


class SubCategoryView(CategoriesView):

    def __init__(self, cache, db, icons,
                 apps_filter, apps_limit=0, root_category=None):
        CategoriesView.__init__(self, cache, db, icons, apps_filter,
                                apps_limit)
        # state
        self._built = False
        # data
        self.root_category = root_category
        self.enquire = AppEnquire(self.cache, self.db)
        self.properties_helper = AppPropertiesHelper(
            self.db, self.cache, self.icons)

        # sections
        self.current_category = None
        self.departments = None
        self.top_rated = None
        self.recommended_for_you_in_cat = None
        self.appcount = None

        # widgetry
        self.vbox.set_margin_left(StockEms.MEDIUM - 2)
        self.vbox.set_margin_right(StockEms.MEDIUM - 2)
        self.vbox.set_margin_top(StockEms.MEDIUM)
        return

    def _get_sub_top_rated_content(self, category):
        app_filter = AppFilter(self.db, self.cache)
        self.enquire.set_query(category.query,
                               limit=TOP_RATED_CAROUSEL_LIMIT,
                               sortmode=SortMethods.BY_TOP_RATED,
                               filter=app_filter,
                               nonapps_visible=NonAppVisibility.ALWAYS_VISIBLE,
                               nonblocking_load=False)
        return self.enquire.get_documents()

    @wait_for_apt_cache_ready  # be consistent with new apps
    def _update_sub_top_rated_content(self, category):
        self.top_rated.remove_all()
        # FIXME: should this be m = "%s %s" % (_(gettext text), header text) ??
        # TRANSLATORS: %s is a category name, like Internet or Development
        # Tools
        m = _('Top Rated %(category)s') % {
            'category': GLib.markup_escape_text(self.header)}
        self.top_rated_frame.set_header_label(m)
        docs = self._get_sub_top_rated_content(category)
        self.top_rated.add_tiles(self.properties_helper,
                                 docs,
                                 TOP_RATED_CAROUSEL_LIMIT)
        return

    def _append_sub_top_rated(self):
        self.top_rated = TileGrid()
        self.top_rated.connect("application-activated",
                               self.on_application_activated)
        self.top_rated.set_row_spacing(6)
        self.top_rated.set_column_spacing(6)
        self.top_rated_frame = FramedHeaderBox()
        self.top_rated_frame.pack_start(self.top_rated, True, True, 0)
        self.vbox.pack_start(self.top_rated_frame, False, True, 0)
        return

    def _update_recommended_for_you_in_cat_content(self, category):
        if (self.recommended_for_you_in_cat and
                self.recommended_for_you_in_cat.get_parent()):
            self.recommended_for_you_in_cat.disconnect_by_func(
                    self.on_application_activated)
            self.vbox.remove(self.recommended_for_you_in_cat)
        self.recommended_for_you_in_cat = RecommendationsPanelCategory(
                self.db,
                self.properties_helper,
                category)
        self.recommended_for_you_in_cat.connect("application-activated",
                                                self.on_application_activated)
        self.recommended_for_you_in_cat.connect(
                'more-button-clicked',
                self.on_category_clicked)
        # only show the panel in the categories view when the user
        # is opted in to the recommender service
        # FIXME: this is needed vs. a simple hide() on the widget because
        #        we do a show_all on the view
        if self.recommended_for_you_in_cat.recommender_agent.is_opted_in():
            self.vbox.pack_start(self.recommended_for_you_in_cat,
                                        False, False, 0)

    def _update_subcat_departments(self, category, num_items):
        self.departments.remove_all()

        # set the subcat header
        m = "<b><big>%s</big></b>"
        self.subcat_label.set_markup(m % GLib.markup_escape_text(
            self.header))

        # sort Category.name's alphabetically
        sorted_cats = categories_sorted_by_name(self.categories)
        enquire = xapian.Enquire(self.db.xapiandb)
        app_filter = AppFilter(self.db, self.cache)
        distro = get_distro()
        supported_only = get_global_filter().supported_only
        for cat in sorted_cats:
            # add the subcategory if and only if it is non-empty
            if supported_only:
                enquire.set_query(xapian.Query(xapian.Query.OP_AND,
                                    cat.query,
                                    distro.get_supported_query()))
            else:
                enquire.set_query(cat.query)
            if len(enquire.get_mset(0, 1)):
                tile = CategoryTile(cat.name, cat.iconname)
                tile.connect('clicked', self.on_category_clicked, cat)
                self.departments.add_child(tile)

        # partially work around a (quite rare) corner case
        if num_items == 0:
            enquire.set_query(xapian.Query(xapian.Query.OP_AND,
                                category.query,
                                xapian.Query("ATapplication")))
            # assuming that we only want apps is not always correct ^^^
            tmp_matches = enquire.get_mset(0, len(self.db), None, app_filter)
            num_items = tmp_matches.get_matches_estimated()

        # append an additional button to show all of the items in the category
        all_cat = Category("All", _("All"), "category-show-all",
            category.query)
        name = GLib.markup_escape_text('%s %s' % (_("All"), num_items))
        tile = CategoryTile(name, "category-show-all")
        tile.connect('clicked', self.on_category_clicked, all_cat)
        self.departments.add_child(tile)
        self.departments.queue_draw()
        return num_items

    def _append_subcat_departments(self):
        self.subcat_label = Gtk.Label()
        self.subcat_label.set_alignment(0, 0.5)
        self.departments = TileGrid(paint_grid_pattern=False)
        self.departments.set_row_spacing(StockEms.SMALL)
        self.departments.set_column_spacing(StockEms.SMALL)
        self.departments_frame = FramedBox(spacing=StockEms.MEDIUM,
                                           padding=StockEms.MEDIUM)
        # set x/y-alignment and x/y-expand
        self.departments_frame.set(0.5, 0.0, 1.0, 1.0)
        self.departments_frame.pack_start(self.subcat_label, False, False, 0)
        self.departments_frame.pack_start(self.departments, True, True, 0)
        # append the departments section to the page
        self.vbox.pack_start(self.departments_frame, False, True, 0)
        return

    def _update_appcount(self, appcount):
        text = gettext.ngettext("%(amount)s item available",
                                "%(amount)s items available",
                                appcount) % {'amount': appcount}
        self.appcount.set_text(text)
        return

    def _append_appcount(self):
        self.appcount = Gtk.Label()
        self.appcount.set_alignment(0.5, 0.5)
        self.appcount.set_margin_top(1)
        self.appcount.set_margin_bottom(4)
        self.vbox.pack_end(self.appcount, False, False, 0)
        return

    def _build_subcat_view(self):
        # these methods add sections to the page
        # changing order of methods changes order that they appear in the page
        self._append_subcat_departments()
        self._append_sub_top_rated()
        # NOTE that the recommended for you in category view is built and added
        # in the _update_recommended_for_you_in_cat method (and so is not
        # needed here)
        self._append_appcount()
        self._built = True
        return

    def _update_subcat_view(self, category, num_items=0):
        num_items = self._update_subcat_departments(category, num_items)
        self._update_sub_top_rated_content(category)
        self._update_recommended_for_you_in_cat_content(category)
        self._update_appcount(num_items)
        self.show_all()
        return

    def set_subcategory(self, root_category, num_items=0):
        # nothing to do
        if (root_category is None or
                self.categories == root_category.subcategories):
            return
        self._set_subcategory(root_category, num_items)

    def _set_subcategory(self, root_category, num_items):
        self.current_category = root_category
        self.header = root_category.name
        self.categories = root_category.subcategories

        if not self._built:
            self._build_subcat_view()
        self._update_subcat_view(root_category, num_items)

        GLib.idle_add(self.queue_draw)
        return

    def refresh_apps(self):
        supported_only = get_global_filter().supported_only
        if (self.current_category is None or
                self._supported_only == supported_only):
            return
        self._supported_only = supported_only

        if not self._built:
            self._build_subcat_view()
        self._update_subcat_view(self.current_category)
        GLib.idle_add(self.queue_draw)
        return
