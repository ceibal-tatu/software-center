import unittest

import dbus

from tests.utils import (
    do_events_with_sleep,
    setup_test_env,
    start_dummy_backend,
    stop_dummy_backend,
    get_mock_app_properties_helper,
    url_accessable,
)
setup_test_env()

from softwarecenter.db.application import Application
from softwarecenter.backend.installbackend_impl.aptd import get_dbus_bus


class DummyBackendTestUtilsTestCase(unittest.TestCase):

    def setUp(self):
        start_dummy_backend()

    def tearDown(self):
        stop_dummy_backend()

    def test_start_stop_dummy_backend(self):
        bus = get_dbus_bus()
        system_bus = dbus.SystemBus()
        session_bus = dbus.SessionBus()
        self.assertNotEqual(bus, system_bus)
        self.assertNotEqual(bus, session_bus)
        # get names and ...
        names = bus.list_names()
        # ensure we have the  following:
        #  org.freedesktop.DBus,
        #  org.freedesktop.PolicyKit1
        #  org.debian.apt
        # (and :1.0, :1.1)
        for name in ["org.freedesktop.PolicyKit1", "org.debian.apt"]:
            self.assertTrue(name in names,
                            "Expected name '%s' not in '%s'" % (name, names))

    def test_fake_aptd(self):
        from softwarecenter.backend.installbackend import get_install_backend
        backend = get_install_backend()
        backend.install(Application("2vcard", ""), iconname="")
        do_events_with_sleep()


class TestUtilsTestCase(unittest.TestCase):

    def test_app_properties_helper_mock_with_defaults(self):
        app_properties_helper = get_mock_app_properties_helper()
        self.assertEqual(
            app_properties_helper.get_pkgname(None), "apkg")

    def test_app_properties_helper_mock_with_custom_values(self):
        my_defaults = {'pkgname': 'diemoldau',
                      }
        app_properties_helper = get_mock_app_properties_helper(my_defaults)
        self.assertEqual(
            app_properties_helper.get_pkgname(None), "diemoldau")

    def test_url_accessable(self):
        self.assertTrue(
            url_accessable("http://archive.ubuntu.com/ubuntu/", "dists/"))
        self.assertFalse(
            url_accessable("http://archive.ubuntu.com/ubuntu/",
                           "mooobaalalala"))
    

if __name__ == "__main__":
    unittest.main()
