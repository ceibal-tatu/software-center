#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import os
import platform
import subprocess
import time
import unittest

import dbus

from gi.repository import GLib

from tests.utils import (
    setup_test_env,
)
setup_test_env()

from softwarecenter.backend.installbackend_impl.aptd import AptdaemonBackend
from softwarecenter.db.application import Application
from softwarecenter.paths import APPORT_RECOVERABLE_ERROR

from defer import inline_callbacks
from mock import Mock, patch

import aptdaemon


class TestAptdaemon(unittest.TestCase):
    """ tests the AptdaemonBackend """

    def setUp(self):
        self.aptd = AptdaemonBackend()
        self.aptd.ui = Mock()
        # monkey patch
        self.aptd.aptd_client.install_packages = self._mock_aptd_client_install_packages
        self._pkgs_to_install = []

    def _mock_aptd_client_install_packages(self, pkgs, reply_handler, error_handler):
        self._pkgs_to_install.extend(pkgs)

    @inline_callbacks
    def test_add_license_key_home(self):
        data = "some-data"
        # test HOME
        target = "~/.fasfasdfsdafdfsdafdsfa"
        self.addCleanup(lambda: os.remove(os.path.expanduser(target)))
        pkgname = "2vcard"
        json_auth = ""
        yield self.aptd.add_license_key(data, target, json_auth, pkgname)
        self.assertEqual(open(os.path.expanduser(target)).read(), data)
        # ensure its not written twice
        data2 = "other-data"
        yield self.aptd.add_license_key(data2, target, json_auth, pkgname)
        self.assertEqual(open(os.path.expanduser(target)).read(), data)

    @unittest.skipIf(os.getuid() != 0, 
                     "test_add_license_key_opt test needs to run as root")
    @unittest.skipIf(not "SC_TEST_JSON" in os.environ,
                     "Need a SC_TEST_JSON environment with the credentials")
    def test_add_license_key_opt(self):
        # test /opt
        license_key = "some-data"
        pkgname = "hellox"
        path = "/opt/hellox/conf/license-key.txt"
        self.addCleanup(lambda: os.remove(path))
        json_auth = os.environ.get("SC_TEST_JSON") or "no-json-auth"
        def _error(*args):
            print "errror", args
        self.aptd.ui = Mock()
        self.aptd.LICENSE_KEY_SERVER = "ubuntu-staging"
        self.aptd.ui.error = _error
        @inline_callbacks
        def run():
            yield self.aptd.add_license_key(
                license_key, path, json_auth, pkgname)
            # ensure signals get delivered before quit()
            GLib.timeout_add(500, lambda: aptdaemon.loop.mainloop.quit())
        # run the callback
        run()
        aptdaemon.loop.mainloop.run()
        # give the daemon time to write the file
        time.sleep(0.5)
        self.assertTrue(os.path.exists(path))
        #self.assertEqual(open(os.path.expanduser(target)).read(), data)
        #os.remove(os.path.expanduser(target))

    def test_install_multiple(self):
        # FIXME: this test is not great, it should really
        #        test that there are multiple transactions, that the icons
        #        are correct etc - that needs some work in order to figure
        #        out how to best do that with aptdaemon/aptd.py
        pkgnames = ["7zip", "2vcard"]
        appnames = ["The 7 zip app", ""]
        iconnames = ["icon-7zip", ""]
        # need to yiel as install_multiple is a inline_callback (generator)
        yield self.aptd.install_multiple(pkgnames, appnames, iconnames)
        self.assertEqual(self._pkgs_to_install, ["7zip", "2vcard"])
        self._pkgs_to_install = []

    def _monkey_patched_add_vendor_key_from_keyserver(self, keyid,
                                                      *args, **kwargs):
        self.assertTrue(keyid.startswith("0x"))
        return Mock()

    def test_download_key_from_keyserver(self):
        keyid = "0EB12F05"
        keyserver = "keyserver.ubuntu.com"
        self.aptd.aptd_client.add_vendor_key_from_keyserver = self._monkey_patched_add_vendor_key_from_keyserver
        self.aptd.add_vendor_key_from_keyserver(keyid, keyserver)

    def test_apply_changes(self):
        pkgname = "gimp"
        appname = "The GIMP app"
        iconname = "icon-gimp"
        addons_install = ["gimp-data-extras", "gimp-gutenprint"]
        addons_remove = ["gimp-plugin-registry"]
        yield self.aptd.apply_changes(pkgname, appname ,iconname, addons_install, addons_remove)

    @unittest.skipIf(platform.dist()[2] == "precise", "needs quantal or later")
    def test_trans_error_ui_display(self):
        """ test if the right error ui is displayed for various dbus 
            errors
        """
        error = dbus.DBusException()
        dbus_name_mock = Mock()
        with patch.object(self.aptd.ui, "error") as error_ui_mock:
            for dbus_name, show_error_ui in [
                ("org.freedesktop.PolicyKit.Error.NotAuthorized", False),
                ("org.freedesktop.PolicyKit.Error.Failed", True),
                ("moo.baa.lalala", True),
                ]:
                error_ui_mock.reset()
                dbus_name_mock.return_value = dbus_name
                error.get_dbus_name = dbus_name_mock
                self.aptd._on_trans_error(error, Mock())
                self.assertEqual(error_ui_mock.called, show_error_ui)

    @inline_callbacks
    def _inline_add_repo_call(self):
        deb_line = "deb https://foo"
        signing_key_id = u"xxx"
        app = Application(u"Elementals: The Magic Key™", "pkgname")
        iconname = "iconname"
        yield self.aptd.add_repo_add_key_and_install_app(
            deb_line, signing_key_id, app, iconname, None, None)

    def test_add_repo_add_key_and_install_app(self):
        from mock import patch
        with patch.object(self.aptd._logger, "info") as mock:
            self._inline_add_repo_call()
            self.assertTrue(
                mock.call_args[0][0].startswith("add_repo_add_key"))

    @patch("softwarecenter.backend.installbackend_impl.aptd.Popen")
    def test_recoverable_error(self, mock_popen):
        mock_popen_instance = Mock()
        mock_popen_instance.communicate.return_value = ("stdout", "stderr")
        mock_popen_instance.returncode = 0
        mock_popen.return_value = mock_popen_instance
        self.aptd._call_apport_recoverable_error(
            "msg", "traceback-error", "custom:dupes:signature")
        mock_popen.assert_called_with(
            [APPORT_RECOVERABLE_ERROR], stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # check that we really send the right data 
        args, kwargs = mock_popen_instance.communicate.call_args
        self.assertEqual(
            kwargs["input"].split("\0"),
            [ 'DialogBody', 'msg',
              'Traceback', 'traceback-error',
              'DuplicateSignature', 'custom:dupes:signature',
            ])

    def test_ignore_bad_packages(self):
        mock_trans = Mock(aptdaemon.client.AptTransaction)
        mock_trans.error_code = aptdaemon.enums.ERROR_INVALID_PACKAGE_FILE
        with patch.object(self.aptd, "_call_apport_recoverable_error") as m:
            self.aptd._on_trans_error("some error", mock_trans)
            self.assertFalse(m.called)

    def test_ignore_dpkg_errors(self):
        mock_trans = Mock(aptdaemon.client.AptTransaction)
        mock_trans.error_code = aptdaemon.enums.ERROR_PACKAGE_MANAGER_FAILED
        with patch.object(self.aptd, "_call_apport_recoverable_error") as m:
            self.aptd._on_trans_error("some error", mock_trans)
            self.assertFalse(m.called)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
