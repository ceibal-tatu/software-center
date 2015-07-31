# Copyright (C) 2012 Canonical
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

import dbus
import dbus.service
import logging
import time

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

from gi.repository import GLib

from .categories import (
    CategoriesParser,
    get_category_by_name,
)
from .database import StoreDatabase
from .application import Application
from softwarecenter.backend.reviews import get_review_loader
from softwarecenter.db.utils import run_software_center_agent

# To test, run with e.g.
"""
dbus-send --session --type=method_call \
   --dest=com.ubuntu.SoftwareCenterDataProvider --print-reply \
   /com/ubuntu/SoftwareCenterDataProvider \
   com.ubuntu.SoftwareCenterDataProvider.GetAppDetails string:"" string:"apt"
"""


LOG = logging.getLogger(__file__)

DBUS_BUS_NAME = 'com.ubuntu.SoftwareCenterDataProvider'
DBUS_DATA_PROVIDER_IFACE = 'com.ubuntu.SoftwareCenterDataProvider'
DBUS_DATA_PROVIDER_PATH = '/com/ubuntu/SoftwareCenterDataProvider'


def update_activity_timestamp(fn):
    def wrapped(*args, **kwargs):
        self = args[0]
        self._update_activity_timestamp()
        return fn(*args, **kwargs)
    return wrapped


class SoftwareCenterDataProvider(dbus.service.Object):

    # 5 min by default
    IDLE_TIMEOUT = 60 * 5
    IDLE_CHECK_INTERVAL = 60

    def __init__(self, bus_name, object_path=DBUS_DATA_PROVIDER_PATH,
                 main_loop=None):
        dbus.service.Object.__init__(self, bus_name, object_path)
        self.bus_name = bus_name
        if main_loop is None:
            main_loop = GLib.MainLoop(GLib.main_context_default())
        self.main_loop = main_loop
        # the database
        self.db = StoreDatabase()
        self.db.open()
        self.db._aptcache.open(blocking=True)
        # categories
        self.categories = CategoriesParser(self.db).parse_applications_menu()
        # ensure reviews get refreshed
        self.review_loader = get_review_loader(self.db._aptcache, self.db)
        self.review_loader.refresh_review_stats()
        # ensure we query new applications
        run_software_center_agent(self.db)
        # setup inactivity timer
        self._update_activity_timestamp()
        self._idle_timeout = GLib.timeout_add_seconds(
            self.IDLE_CHECK_INTERVAL, self._check_inactivity)

    def stop(self):
        """ stop the dbus controller and remove from the bus """
        LOG.debug("stop() called")
        self.main_loop.quit()
        LOG.debug("exited")

    # internal helper
    def _check_inactivity(self):
        """ Check for activity """
        now = time.time()
        if (self._activity_timestamp + self.IDLE_TIMEOUT) < now:
            LOG.info("stopping after %s inactivity" % self.IDLE_TIMEOUT)
            self.stop()
        return True

    def _update_activity_timestamp(self):
        self._activity_timestamp = time.time()

    # public dbus methods with their implementations, the dbus decorator
    # does not like additional decorators so we use a separate function
    # for the actual implementation
    @dbus.service.method(DBUS_DATA_PROVIDER_IFACE,
                         in_signature='ss', out_signature='a{sv}')
    def GetAppDetails(self, appname, pkgname):
        LOG.debug("GetAppDetails() called with ('%s', '%s')" % (
                appname, pkgname))
        return self._get_app_details(appname, pkgname)

    @update_activity_timestamp
    def _get_app_details(self, appname, pkgname):
        app = Application(appname, pkgname)
        appdetails = app.get_details(self.db)
        return appdetails.as_dbus_property_dict()

    @dbus.service.method('com.ubuntu.SoftwareCenterDataProvider',
                         in_signature='', out_signature='as')
    def GetAvailableCategories(self):
        LOG.debug("GetAvailableCategories() called")
        return self._get_available_categories()

    @update_activity_timestamp
    def _get_available_categories(self):
        return [cat.name for cat in self.categories]

    @dbus.service.method(DBUS_DATA_PROVIDER_IFACE,
                         in_signature='s', out_signature='as')
    def GetAvailableSubcategories(self, category_name):
        LOG.debug("GetAvailableSubcategories() called")
        return self._get_available_subcategories(category_name)

    @update_activity_timestamp
    def _get_available_subcategories(self, category_name):
        cat = get_category_by_name(self.categories, category_name)
        return [subcat.name for subcat in cat.subcategories]

    @dbus.service.method('com.ubuntu.SoftwareCenterDataProvider',
                         in_signature='s', out_signature='a(ssss)')
    def GetItemsForCategory(self, category_name):
        LOG.debug("GetItemsForCategory() called with ('%s')" % category_name)
        return self._get_items_for_category(category_name)

    @update_activity_timestamp
    def _get_items_for_category(self, category_name):
        result = []
        cat = get_category_by_name(self.categories, category_name)
        for doc in cat.get_documents(self.db):
            result.append(
                (self.db.get_appname(doc),
                 self.db.get_pkgname(doc),
                 self.db.get_iconname(doc),
                 self.db.get_desktopfile(doc),
                 ))
        return result


def dbus_main(bus=None):
    if bus is None:
        bus = dbus.SessionBus()

    # apt needs the right locale for the translated package descriptions
    from softwarecenter.i18n import init_locale
    init_locale()

    main_context = GLib.main_context_default()
    main_loop = GLib.MainLoop(main_context)

    bus_name = dbus.service.BusName(DBUS_BUS_NAME, bus)
    data_provider = SoftwareCenterDataProvider(bus_name, main_loop=main_loop)
    data_provider  # pyflakes

    # run it
    main_loop.run()
