import dbus
import os
import subprocess
import time
import unittest

from gi.repository import GLib

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

from mock import (
    Mock,
    patch,
    )

from tests.utils import (
    kill_process,
    setup_test_env,
    start_dbus_daemon,
)
setup_test_env()

from softwarecenter.db.application import AppDetails
from softwarecenter.db.dataprovider import (
    SoftwareCenterDataProvider,
    DBUS_BUS_NAME,
    DBUS_DATA_PROVIDER_IFACE,
    DBUS_DATA_PROVIDER_PATH,
    )


def start_data_provider_daemon(dbus_address):
    """Start the dbus data provider as a subprocess"""
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = dbus_address
    testdir = os.path.dirname(__file__)
    basedir = os.path.abspath(os.path.join(testdir, ".."))
    data_provider_bin = os.path.join(basedir, "software-center-dbus")
    stderr = open(os.devnull, "w")
    # uncomment this for a flurry of debug output
    #stderr = None
    # this is more reliable than e.g. threading.Thead or multiprocess.Process
    p = subprocess.Popen([data_provider_bin], stderr=stderr)
    return p


class DbusForRealTestCase(unittest.TestCase):
    """Test the dataprovider over a real dbus bus"""

    @classmethod
    def setUpClass(cls):
        cls.dbus_daemon_proc, dbus_address = start_dbus_daemon()
        cls.bus = dbus.bus.BusConnection(dbus_address)
        cls.data_provider_proc = start_data_provider_daemon(dbus_address)
        time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        kill_process(cls.data_provider_proc)
        kill_process(cls.dbus_daemon_proc)

    def setUp(self):
        obj = self.bus.get_object(bus_name=DBUS_BUS_NAME,
                         object_path=DBUS_DATA_PROVIDER_PATH,
                         follow_name_owner_changes=True)
        self.proxy = dbus.Interface(object=obj,
                               dbus_interface=DBUS_DATA_PROVIDER_IFACE)

    def test_dbus_on_real_bus(self):
        result = self.proxy.GetAppDetails("", "gimp")
        self.assertEqual(result["pkgname"], "gimp")
        self.assertEqual(result["icon"], "gimp")


class PropertyDictExceptionsTestCase(unittest.TestCase):
    """Test that the exceptions in the AppDetails for the dbus properties
       are handled correctly
    """

    def setUp(self):
        self.mock_app_details = Mock(AppDetails)

    def test_simple(self):
        self.mock_app_details.name = "fake-app"
        properties = AppDetails.as_dbus_property_dict(self.mock_app_details)
        self.assertEqual(properties["name"], "fake-app")

    def test_empty_dict_set(self):
        self.mock_app_details.empty_set = set()
        self.mock_app_details.empty_dict = {}
        properties = AppDetails.as_dbus_property_dict(self.mock_app_details)
        self.assertEqual(properties["empty_set"], "")
        self.assertEqual(properties["empty_dict"], "")

    def test_normal_dict(self):
        self.mock_app_details.non_empty_dict = { "moo" : "bar" }
        properties = AppDetails.as_dbus_property_dict(self.mock_app_details)
        self.assertEqual(properties["non_empty_dict"], { "moo" : "bar" })

    def test_normal_set(self):
        self.mock_app_details.non_empty_set = set(["foo", "bar", "baz"])
        properties = AppDetails.as_dbus_property_dict(self.mock_app_details)
        self.assertEqual(
            sorted(properties["non_empty_set"]), ["bar", "baz", "foo"])


class DataProviderTestCase(unittest.TestCase):
    """ Test the methods of the dataprovider """

    @classmethod
    def setUpClass(cls):
        cls.proc, dbus_address = start_dbus_daemon()
        cls.bus = dbus.bus.BusConnection(dbus_address)
        bus_name = dbus.service.BusName(
            'com.ubuntu.SoftwareCenterDataProvider', cls.bus)
        # get the provider
        cls.provider = SoftwareCenterDataProvider(bus_name)

    @classmethod
    def tearDownClass(cls):
        cls.provider.stop()
        kill_process(cls.proc)

    def test_have_data_in_db(self):
        self.assertTrue(len(self.provider.db) > 100)

    # details
    def test_get_details(self):
        result = self.provider.GetAppDetails("", "gedit")
        self.assertEqual(result["component"], "main")
        self.assertEqual(result["icon"], "accessories-text-editor")
        self.assertEqual(result["name"], "gedit")
        self.assertEqual(result["pkgname"], "gedit")
        self.assertEqual(result["price"], "Free")
        self.assertEqual(result["raw_price"], "")
        # this will only work *if* the ubuntu-desktop pkg is actually installed
        if self.provider.db._aptcache["ubuntu-desktop"].is_installed:
            self.assertEqual(result["is_desktop_dependency"], True)

    def test_get_details_non_desktop(self):
        result = self.provider.GetAppDetails("", "apache2")
        self.assertEqual(result["is_desktop_dependency"], False)

    # get available categories/subcategories
    def test_get_categories(self):
        result = self.provider.GetAvailableCategories()
        self.assertTrue("Internet" in result)

    def test_get_subcategories(self):
        result = self.provider.GetAvailableSubcategories("Internet")
        self.assertTrue("Chat" in result)

    # get category
    def test_get_category_internet(self):
        result = self.provider.GetItemsForCategory("Internet")
        self.assertTrue(
            ("Firefox Web Browser",  # app
             "firefox",  # pkgname
             "firefox",  # iconname
             "/usr/share/app-install/desktop/firefox:firefox.desktop",
             ) in result)

    def test_get_category_top_rated(self):
        result = self.provider.GetItemsForCategory("Top Rated")
        self.assertEqual(len(result), 100)

    def test_get_category_whats_new(self):
        result = self.provider.GetItemsForCategory(u"What\u2019s New")
        self.assertEqual(len(result), 20)


class IdleTimeoutTestCase(unittest.TestCase):

    def setUp(self):
        self.loop = GLib.MainLoop(GLib.main_context_default())

        # setup bus
        dbus_service_name = DBUS_BUS_NAME
        proc, dbus_address = start_dbus_daemon()
        bus = dbus.bus.BusConnection(dbus_address)
        # run the checks
        self.bus_name = dbus.service.BusName(dbus_service_name, bus)

    def tearDown(self):
        self.loop.quit()

    @patch.object(SoftwareCenterDataProvider, "IDLE_TIMEOUT")
    @patch.object(SoftwareCenterDataProvider, "IDLE_CHECK_INTERVAL")
    def test_idle_timeout(self, mock_timeout, mock_interval):
        mock_timeout = 1
        mock_timeout  # pyflakes
        mock_interval = 1
        mock_interval  # pyflakes

        now = time.time()
        provider = SoftwareCenterDataProvider(
            self.bus_name, main_loop=self.loop)
        provider  # pyflakes
        self.loop.run()
        # ensure this exited within a reasonable timeout
        self.assertTrue((time.time() - now) < 5)

    def test_idle_timeout_updates(self):
        provider = SoftwareCenterDataProvider(
            self.bus_name, main_loop=self.loop)
        t1 = provider._activity_timestamp
        time.sleep(0.1)
        provider.GetAvailableCategories()
        t2 = provider._activity_timestamp
        self.assertTrue(t1 < t2)


if __name__ == "__main__":
    #import logging
    #logging.basicConfig(level=logging.DEBUG)
    os.environ.pop("LANGUAGE", None)
    os.environ.pop("LANG", None)
    unittest.main()
