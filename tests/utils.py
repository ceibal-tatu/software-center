# Copyright (C) 2011 Canonical
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

import copy
import os
import subprocess
import sys
import tempfile
import time

from collections import defaultdict
from functools import wraps
from urllib2 import urlopen

import xapian

from gi.repository import GLib, Gtk
from mock import Mock

import softwarecenter.paths

from softwarecenter.backend.installbackend import get_install_backend
from softwarecenter.db.categories import CategoriesParser
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.enquire import AppEnquire
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.ui.gtk3.session.viewmanager import (
    ViewManager,
    get_viewmanager,
)
from softwarecenter.ui.gtk3.utils import get_sc_icon_theme
from softwarecenter.ui.gtk3.models.appstore2 import AppPropertiesHelper
from softwarecenter.utils import get_uuid
from softwarecenter.db.update import update_from_app_install_data


m_dbus = m_polkit = m_aptd = None

REAL_DATA_DIR = os.path.abspath(os.path.join('.', 'data'))
DATA_DIR = os.path.abspath(os.path.join('.', 'tests', 'data'))
UTILS_DIR = os.path.abspath(os.path.join('.', 'utils'))


def url_accessable(url, needle):
    """Return true if needle is found in the url

    This is useful as a unittest.skip decorator
    """
    f = urlopen(url)
    content = f.read()
    f.close()
    return needle in content


def start_dbus_daemon():
    proc = subprocess.Popen(["dbus-daemon",
                             "--session",
                             "--nofork",
                             "--print-address"],
                            stdout=subprocess.PIPE)
    dbus_address = proc.stdout.readline().strip()
    return proc, dbus_address


def kill_process(proc):
    """Takes a subprocess process and kills it"""
    do_events_with_sleep()
    proc.kill()
    proc.wait()


def start_dummy_backend():
    global m_dbus, m_polkit, m_aptd
    # get and store address
    m_dbus, bus_address = start_dbus_daemon()
    os.environ["SOFTWARE_CENTER_APTD_FAKE"] = bus_address
    # start fake polkit from python-aptdaemon.test
    env = {"DBUS_SESSION_BUS_ADDRESS": bus_address,
           "DBUS_SYSTEM_BUS_ADDRESS": bus_address,
          }
    m_polkit = subprocess.Popen(
        ["/usr/share/aptdaemon/tests/fake-polkitd.py",
         "--allowed-actions=all"],
        env=env)
    # start aptd in dummy mode
    m_aptd = subprocess.Popen(
        ["/usr/sbin/aptd", "--dummy", "--session-bus", "--disable-timeout"],
        env=env)
    # the sleep here is not ideal, but we need to wait a little bit
    # to ensure that the fake daemon and fake polkit is ready
    import dbus
    bus = dbus.bus.BusConnection(bus_address)
    for i in range(10):
        time.sleep(0.5)
        if "org.debian.apt" in bus.list_names():
            break
    else:
        raise Exception("Failed to see 'org.debian.apt' on the bus")
        


def stop_dummy_backend():
    global m_dbus, m_polkit, m_aptd
    m_aptd.terminate()
    m_aptd.wait()
    m_polkit.terminate()
    m_polkit.wait()
    m_dbus.terminate()
    m_dbus.wait()


def get_test_gtk3_viewmanager():
    vm = get_viewmanager()
    if not vm:
        notebook = Gtk.Notebook()
        vm = ViewManager(notebook)
        vm.view_to_pane = {None: None}
    return vm


def get_test_db():
    cache = get_pkg_info()
    cache.open()
    db = StoreDatabase(softwarecenter.paths.XAPIAN_PATH, cache)
    db.open()
    return db


def get_test_db_from_app_install_data(datadir):
    db = xapian.inmemory_open()
    cache = get_pkg_info()
    cache.open()
    res = update_from_app_install_data(db, cache, datadir)
    if res is False:
        raise AssertionError("Failed to build db from '%s'" % datadir)
    return db


def get_test_install_backend():
    backend = get_install_backend()
    return backend


def get_test_gtk3_icon_cache():
    icons = get_sc_icon_theme()
    return icons


def get_test_pkg_info():
    cache = get_pkg_info()
    cache.open()
    return cache


def get_test_datadir():
    return softwarecenter.paths.datadir


def get_test_categories(db):
    parser = CategoriesParser(db)
    cats = parser.parse_applications_menu()
    return cats


def get_test_enquirer_matches(db, query=None, limit=20, sortmode=0):
    if query is None:
        query = xapian.Query("")
    enquirer = AppEnquire(db._aptcache, db)
    enquirer.set_query(query,
                       sortmode=sortmode,
                       limit=limit,
                       nonblocking_load=False)
    return enquirer.matches


def do_events():
    main_loop = GLib.main_context_default()
    while main_loop.pending():
        main_loop.iteration()


def do_events_with_sleep(iterations=5, sleep=0.1):
    for i in range(iterations):
        do_events()
        time.sleep(sleep)


def get_mock_app_from_real_app(real_app):
    """ take a application and return a app where the details are a mock
        of the real details so they can easily be modified
    """
    app = copy.copy(real_app)
    db = get_test_db()
    details = app.get_details(db)
    details_mock = Mock(details)
    for a in dir(details):
        if a.startswith("_"):
            continue
        setattr(details_mock, a, getattr(details, a))
    app.details = details_mock
    app.get_details = lambda db: app.details
    return app


def get_mock_options():
    """Return a mock suitable to act as SoftwareCenterAppGtk3's options."""
    mock_options = Mock()
    mock_options.display_navlog = False
    mock_options.disable_apt_xapian_index = False
    mock_options.disable_buy = False

    return mock_options


def get_mock_app_properties_helper(override_values={}):
    """Return a mock suitable as a AppPropertiesHelper.

    It can be passed a "values" dict for customization. But it will
    return always the same data for each "doc" document (it will
    not even look at doc)
    """
    # provide some defaults
    values = {
        'appname': 'some Appname',
        'pkgname': 'apkg',
        'categories': 'cat1,cat2,lolcat',
        'ratings_average': 3.5,
        'ratings_total': 12,
        'icon': None,
        'display_price': '',
        }
    # override
    values.update(override_values)
    # do it
    mock_property_helper = Mock(AppPropertiesHelper)
    mock_property_helper.get_appname.return_value = values["appname"]
    mock_property_helper.get_pkgname.return_value = values["pkgname"]
    mock_property_helper.get_categories.return_value = values["categories"]
    mock_property_helper.get_display_price.return_value = values[
        "display_price"]

    mock_property_helper.db = Mock()
    mock_property_helper.db._aptcache = FakedCache()
    mock_property_helper.db.get_pkgname.return_value = values["pkgname"]
    mock_property_helper.db.get_appname.return_value = values["appname"]

    mock_ratings = Mock()
    mock_ratings.ratings_average = values["ratings_average"]
    mock_ratings.ratings_total = values["ratings_total"]

    mock_property_helper.get_review_stats.return_value = mock_ratings
    mock_property_helper.get_icon_at_size.return_value = values["icon"]
    mock_property_helper.icons = Mock()
    mock_property_helper.icons.load_icon.return_value = values["icon"]
    return mock_property_helper


def setup_test_env():
    """ Setup environment suitable for running the test/* code in a checkout.
        This includes PYTHONPATH, sys.path and softwarecenter.paths.datadir.
    """
    basedir = os.path.dirname(__file__)
    while not os.path.exists(
        os.path.join(basedir, "softwarecenter", "__init__.py")):
        basedir = os.path.abspath(os.path.join(basedir, ".."))
    #print basedir, __file__, os.path.realpath(__file__)
    sys.path.insert(0, basedir)
    os.environ["PYTHONPATH"] = basedir
    softwarecenter.paths.datadir = os.path.join(basedir, "data")
    softwarecenter.paths.SOFTWARE_CENTER_CACHE_DIR = tempfile.mkdtemp()


# factory stuff for the agent
def make_software_center_agent_app_dict(override_dict={}):
    app_dict = {
        u'archive_root': 'http://private-ppa.launchpad.net/',
        u'archive_id': u'commercial-ppa-uploaders/photobomb',
        u'description': u"Easy and Social Image Editor\nPhotobomb "
                        u"give you easy access to images in your "
                        u"social networking feeds, pictures on ...",
        u'name': u'Photobomb',
        u'package_name': u'photobomb',
        u'signing_key_id': u'1024R/75254D99',
        u'screenshot_url': 'http://software-center.ubuntu.com/site_media/'\
                           'screenshots/2011/08/Screenshot.png',
        u'license': 'Proprietary',
        u'support_url': 'mailto:support@example.com',
        u'series': {'oneiric': ['i386', 'amd64'],
                     'natty': ['i386', 'amd64'],
                   },
        u'channel': 'For Purchase',
        u'icon_url': 'http://software-center.ubuntu.com/site_media/icons/'\
                      '2011/08/64_Chainz.png',
        u'categories': 'Game;LogicGame',
        }
    app_dict.update(override_dict)
    return app_dict


def make_software_center_agent_subscription_dict(app_dict):
    subscription_dict = {
        u'application': app_dict,
        u'deb_line': u'deb https://some.user:ABCDEFGHIJKLMNOP@'
                     u'private-ppa.launchpad.net/commercial-ppa-uploaders/'
                     u'photobomb/ubuntu natty main',
        u'distro_series': {u'code_name': u'natty', u'version': u'11.04'},
        u'failures': [],
        u'open_id': u'https://login.ubuntu.com/+id/ABCDEF',
        u'purchase_date': u'2011-09-16 06:37:52',
        u'purchase_price': u'2.99',
        u'state': u'Complete',
        }
    return subscription_dict


def make_recommender_agent_recommend_me_dict():
    # best to have a list of likely not-installed items
    app_dict = {
        u'data': [
            {
                u'package_name': u'clementine'
            },
            {
                u'package_name': u'hedgewars'
            },
            {
                u'package_name': u'mangler'
            },
            {
                u'package_name': u'nexuiz'
            },
            {
                u'package_name': u'fgo'
            },
            {
                u'package_name': u'musique'
            },
            {
                u'package_name': u'pybik'
            },
            {
                u'package_name': u'radiotray'
            },
            {
                u'package_name': u'cherrytree'
            },
            {
                u'package_name': u'phlipple'
            },
            {
                u'package_name': u'psi'
            },
            {
                u'package_name': u'midori'
            }
            ]
        }
    return app_dict


def make_recommender_profile_upload_data():
    recommender_uuid = get_uuid()
    profile_upload_data = [
        {
            'uuid': recommender_uuid,
            'package_list': [
                u'clementine',
                u'hedgewars',
                u'mangler',
                u'nexuiz',
                u'fgo',
                u'musique',
                u'pybik',
                u'radiotray',
                u'cherrytree',
                u'phlipple',
                u'psi',
                u'midori'
            ]
        }
    ]
    return profile_upload_data


def make_recommend_app_data():
    recommend_app_data = {
        u'rid': u'265c0bb1dece93a96c5a528e7ea5dd75',
        u'data': [
            {u'rating': 4.0, u'package_name': u'kftpgrabber'},
            {u'rating': 4.0, u'package_name': u'sugar-emulator-0.90'},
            {u'rating': 3.0, u'package_name': u'wakeup'},
            {u'rating': 3.0, u'package_name': u'xvidcap'},
            {u'rating': 2.0, u'package_name': u'airstrike'},
            {u'rating': 2.0, u'package_name': u'pixbros'},
            {u'rating': 2.0, u'package_name': u'bomber'},
            {u'rating': 2.0, u'package_name': u'ktron'},
            {u'rating': 2.0, u'package_name': u'gnome-mousetrap'},
            {u'rating': 1.5, u'package_name': u'tucan'}],
        u'app': u'pitivi'}
    return recommend_app_data


def patch_datadir(newdir):

    def middle(f):

        @wraps(f)
        def inner(*args, **kwars):
            original = softwarecenter.paths.datadir
            softwarecenter.paths.datadir = newdir
            try:
                result = f(*args, **kwars)
            finally:
                softwarecenter.paths.datadir = original
            return result

        return inner

    return middle


class ObjectWithSignals(object):
    """A faked object that you can connect to and emit signals."""

    def __init__(self, *a, **kw):
        super(ObjectWithSignals, self).__init__()
        self._callbacks = defaultdict(list)

    def connect(self, signal, callback):
        """Connect a signal with a callback."""
        self._callbacks[signal].append(callback)

    def disconnect(self, signal, callback):
        """Connect a signal with a callback."""
        self._callbacks[signal].remove(callback)
        if len(self._callbacks[signal]) == 0:
            self._callbacks.pop(signal)

    def disconnect_by_func(self, callback):
        """Disconnect 'callback' from every signal."""
        # do not use iteritems since we may change the dict inside the for
        for signal, callbacks in self._callbacks.items():
            if callback in callbacks:
                self.disconnect(signal, callback)

    def emit(self, signal, *args, **kwargs):
        """Emit 'signal' passing *args, **kwargs to every callback."""
        for callback in self._callbacks[signal]:
            callback(*args, **kwargs)


class FakedCache(ObjectWithSignals, dict):
    """A faked cache."""

    def __init__(self, *a, **kw):
        super(FakedCache, self).__init__()
        self.ready = False

    def open(self):
        """Open this cache."""
        self.ready = True

    def component_available(self, distro_codename, component):
        """Return whether 'component' is available in 'distro_codename'."""

    def get_addons(self, pkgname):
        """Return (recommended, suggested) addons for 'pkgname'."""
        return ([], [])

    def query_total_size_on_install(self, pkgname, addons_to_install,
                                  addons_to_remove, archive_suite):
        """Emit a fake signal "query-total-size-on-install-done" """
        self.emit("query-total-size-on-install-done", None, "", 0, 0)

    def get_packages_removed_on_remove(self, pkgname):
        return []
