import apt
import os
import re
import tempfile
import time
import unittest
import xapian

from gi.repository import GLib
from piston_mini_client import PistonResponseObject
from mock import Mock, patch

from tests.utils import (
    DATA_DIR,
    get_test_db,
    get_test_db_from_app_install_data,
    get_test_pkg_info,
    do_events,
    make_software_center_agent_subscription_dict,
    make_software_center_agent_app_dict,
    setup_test_env,
)
setup_test_env()

import softwarecenter.paths
import softwarecenter.distro

from softwarecenter.db.application import Application, AppDetails
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.enquire import AppEnquire
from softwarecenter.db.database import parse_axi_values_file
from softwarecenter.db.pkginfo import get_pkg_info, _Version
from softwarecenter.db.update import (
    update_from_app_install_data,
    update_from_var_lib_apt_lists,
    update_from_appstream_xml,
    update_from_json_string,
    update_from_software_center_agent,
    SCAPurchasedApplicationParser,
    SCAApplicationParser,
    )
from softwarecenter.db.utils import (
    get_installed_package_list,
    get_installed_apps_list,
)
from softwarecenter.enums import (
    NonAppVisibility,
    PkgStates,
    XapianValues,
    )
from softwarecenter.region import (
    REGION_BLACKLIST_TAG,
    REGION_WHITELIST_TAG,
    REGIONTAG,
    )

PKD_DIR = os.path.join(DATA_DIR, 'appdetails', 'var', 'lib', 'dpkg', 'status')
TEST_DB = os.path.join(DATA_DIR, "test.db")


class TestDatabase(unittest.TestCase):
    """ tests the store database """

    def setUp(self):
        apt.apt_pkg.config.set("Dir::State::status", PKD_DIR)
        self.cache = get_pkg_info()
        self.cache.open()

    def test_multiple_versions_sorting(self):
        db = get_test_db()
        app = Application("", "software-center")
        details = AppDetails(db, application=app)
        details._pkg = Mock()
        details._pkg.installed = Mock()
        details._pkg.installed.version  = "2.0"
        self.assertEqual(details.version, "2.0")
        v0 = { "version" : None, }
        v1 = { "version" : "1.0", }
        v2 = { "version" : "2.0", }
        v3 = { "version" : "3.0", }
        screenshots_list = [ v0, v1, v2, v3 ]
        res = details._sort_screenshots_by_best_version(screenshots_list)
        self.assertEqual(res, [ v2, v1, v0 ])


    def _get_db_from_test_app_install_data(self):
        db = xapian.inmemory_open()
        res = update_from_app_install_data(db, self.cache,
            datadir=os.path.join(DATA_DIR, "desktop"))
        self.assertTrue(res)
        self.assertEqual(db.get_doccount(), 5)
        return db

    def test_update_from_desktop_file(self):
        # ensure we index with german locales to test i18n
        os.environ["LANGUAGE"] = "de"
        datadir = os.path.join(DATA_DIR, "desktop")
        db = get_test_db_from_app_install_data(datadir)
        # test if Name[de] was picked up
        i=0
        for it in db.postlist("AAUbuntu Software Zentrum"):
            i+=1

    def test_update_includes_scope_files(self):
        datadir = os.path.join(DATA_DIR, "desktop")
        db = get_test_db_from_app_install_data(datadir)
        for it in db.postlist("APMunity_lens_music"):
            doc = db.get_document(it.docid)
            self.assertEqual(
                doc.get_value(XapianValues.APPNAME), "Music (Banshee)")
            break
        else:
            self.fail("Did not find scope file in Xapian database")

    def test_regression_index_terms(self):
        """ this tests for a regression that we had in the term indexer
            that would index hundrets of size 1 terms due to a bug
            in AppInfoParserBase._set_doc_from_key
        """
        db = xapian.WritableDatabase(TEST_DB,
                                     xapian.DB_CREATE_OR_OVERWRITE)
        update_from_app_install_data(db, self.cache,
            datadir=os.path.join(DATA_DIR, "desktop"))
        for it in db.postlist("APsoftware-center"):
            docid = it.docid
            break
        # this is the important part, ensure no signle char terms
        for t in db.termlist(docid):
            self.assertFalse(len(t.term) == 1)

    def test_update_from_appstream_xml(self):
        db = xapian.inmemory_open()
        res = update_from_appstream_xml(db, self.cache,
            os.path.join(DATA_DIR, "app-info"))
        self.assertTrue(res)
        self.assertEqual(db.get_doccount(), 1)
        # FIXME: improve tests
        for p in db.postlist(""):
            doc = db.get_document(p.docid)
            for term in doc.termlist():
                self.assertIsInstance(term, xapian.TermListItem)
                self.assertIsInstance(term.term, basestring)
            for value in doc.values():
                self.assertIsInstance(value, xapian.ValueItem)
                self.assertIsInstance(value.num, long)
                self.assertIsInstance(value.value, basestring)

    @unittest.skip("Unreliable: incorrect indices get downloaded")
    def test_update_from_var_lib_apt_lists(self):
        # ensure we index with german locales to test i18n
        os.environ["LANGUAGE"] = "de"
        db = xapian.inmemory_open()
        res = update_from_var_lib_apt_lists(db, self.cache,
            listsdir=os.path.join(DATA_DIR, "app-info"))
        self.assertTrue(res)
        self.assertEqual(db.get_doccount(), 1)
        # test if Name-de was picked up
        i=0
        for it in db.postlist("AAFestplattenbelegung analysieren"):
            i+=1
        self.assertEqual(i, 1)
        # test if gettext worked
        found_gettext_translation = False
        for it in db.postlist("AAFestplattenbelegung analysieren"):
            doc = db.get_document(it.docid)
            for term_iter in doc.termlist():
                # a german term from the app-info file to ensure that
                # it got indexed in german
                if term_iter.term == "festplattenbelegung":
                    found_gettext_translation = True
                    break
        self.assertTrue(found_gettext_translation)

    def test_update_from_json_string(self):
        db = xapian.inmemory_open()
        cache = apt.Cache()
        p = os.path.join(DATA_DIR, "app-info-json", "apps.json")
        res = update_from_json_string(db, cache, open(p).read(), origin=p)
        self.assertTrue(res)
        self.assertEqual(db.get_doccount(), 1)

    @patch("softwarecenter.backend.ubuntusso.UbuntuSSO"
           ".find_oauth_token_sync")
    def test_build_from_software_center_agent(self, mock_find_oauth):
        # pretend we have no token
        mock_find_oauth.return_value = None
        db = xapian.inmemory_open()
        cache = apt.Cache()
        # monkey patch distro to ensure we get data
        distro = softwarecenter.distro.get_distro()
        distro.get_codename = lambda: "natty"
        # we test against the real https://software-center.ubuntu.com here
        # so we need network
        res = update_from_software_center_agent(db, cache, ignore_cache=True)
        # check results
        self.assertTrue(res)
        self.assertTrue(db.get_doccount() > 1)
        for p in db.postlist(""):
            doc = db.get_document(p.docid)
            ppa = doc.get_value(XapianValues.ARCHIVE_PPA)
            self.assertTrue(ppa.startswith("commercial-ppa") and
                            ppa.count("/") == 1,
                            "ARCHIVE_PPA value incorrect, got '%s'" % ppa)
            self.assertTrue(
                "-icon-" in doc.get_value(XapianValues.ICON))
            # check support url in the DB
            url=doc.get_value(XapianValues.SUPPORT_SITE_URL)
            if url:
                self.assertTrue(url.startswith("http") or
                                url.startswith("mailto:"))

    def test_license_string_data_from_software_center_agent(self):
        #os.environ["SOFTWARE_CENTER_DEBUG_HTTP"] = "1"
        #os.environ["SOFTWARE_CENTER_AGENT_HOST"] = "http://sc.staging.ubuntu.com/"
        # staging does not have a valid cert
        os.environ["PISTON_MINI_CLIENT_DISABLE_SSL_VALIDATION"] = "1"
        cache = get_test_pkg_info()
        db = xapian.WritableDatabase(TEST_DB,
                                     xapian.DB_CREATE_OR_OVERWRITE)
        res = update_from_software_center_agent(db, cache, ignore_cache=True)
        self.assertTrue(res)
        for p in db.postlist(""):
            doc = db.get_document(p.docid)
            license = doc.get_value(XapianValues.LICENSE)
            self.assertNotEqual(license, "")
            self.assertNotEqual(license, None)
        #del os.environ["SOFTWARE_CENTER_AGENT_HOST"]

    def test_application(self):
        db = StoreDatabase("/var/cache/software-center/xapian", self.cache)
        # fail if AppDetails(db) without document= or application=
        # is run
        self.assertRaises(ValueError, AppDetails, db)

    def test_application_details(self):
        db = xapian.WritableDatabase(TEST_DB,
                                     xapian.DB_CREATE_OR_OVERWRITE)
        res = update_from_app_install_data(db, self.cache,
            datadir=os.path.join(DATA_DIR, "desktop"))
        self.assertTrue(res)
        db = StoreDatabase(TEST_DB, self.cache)
        db.open(use_axi=False, use_agent=False)
        self.assertEqual(len(db), 6)
        # test details
        app = Application("Ubuntu Software Center Test", "software-center")
        details = app.get_details(db)
        self.assertNotEqual(details, None)
        # mvo: disabled, we can reenable this once there is a static
        #      apt rootdir and we do not rely on the test system to
        #      have software-center from the main archive and not from
        #      e.g. a custom repo like the ADT environment
        #self.assertEqual(details.component, "main")
        self.assertEqual(details.pkgname, "software-center")
        # get the first document
        for doc in db:
            if doc.get_data() == "Ubuntu Software Center Test":
                appdetails = AppDetails(db, doc=doc)
                break
        # test get_appname and get_pkgname
        self.assertEqual(db.get_appname(doc), "Ubuntu Software Center Test")
        self.assertEqual(db.get_pkgname(doc), "software-center")
        # test appdetails
        self.assertEqual(appdetails.name, "Ubuntu Software Center Test")
        self.assertEqual(appdetails.pkgname, "software-center")
        # FIXME: add a dekstop file with a real channel to test
        #        and monkey-patch/modify the APP_INSTALL_CHANNELS_PATH
        self.assertEqual(appdetails.channelname, None)
        self.assertEqual(appdetails.channelfile, None)
        self.assertNotEqual(appdetails.pkg, None)
        # from the fake test/data/appdetails/var/lib/dpkg/status
        self.assertEqual(appdetails.pkg.is_installed, True)
        self.assertTrue(appdetails.pkg_state in (PkgStates.INSTALLED,
                                                 PkgStates.UPGRADABLE))
        # FIXME: test description for unavailable pkg
        self.assertTrue(
            appdetails.description.startswith("Ubuntu Software Center lets you"))
        # FIXME: test appdetails.website
        self.assertEqual(appdetails.icon, "softwarecenter")
        # crude, crude
        self.assertTrue(len(appdetails.version) > 2)
        # FIXME: screenshots will only work on ubuntu
        self.assertTrue(re.match(
                "http://screenshots.ubuntu.com/screenshot-with-version/software-center/[\d.]+",
                appdetails.screenshot))
        self.assertTrue(re.match(
                "http://screenshots.ubuntu.com/thumbnail-with-version/software-center/[\d.]+",
                appdetails.thumbnail))
        # FIXME: add document that has a price
        self.assertEqual(appdetails.price, "Free")
        self.assertEqual(appdetails.raw_price, "")
        # mvo: disabled, we can reenable this once there is a static
        #      apt rootdir and we do not rely on the test system to
        #      have software-center from the main archive and not from
        #      e.g. a custom repo like the ADT environment
        #self.assertEqual(appdetails.license, "Open source")
        # test lazy history loading for installation date
        self.ensure_installation_date_and_lazy_history_loading(appdetails)
        # test apturl replacements
        # $kernel
        app = Application("", "linux-headers-$kernel", "channel=$distro-partner")
        self.assertEqual(app.pkgname, 'linux-headers-'+os.uname()[2])
        # $distro
        details = app.get_details(db)
        distro = softwarecenter.distro.get_distro().get_codename()
        self.assertEqual(app.request, 'channel=' + distro + '-partner')

    def ensure_installation_date_and_lazy_history_loading(self, appdetails):
        # we run two tests, the first is to ensure that we get a
        # result from installation_data immediately (at this point the
        # history is not loaded yet) so we expect "None"
        self.assertEqual(appdetails.installation_date, None)
        # then we need to wait until the history is loaded in the idle
        # handler
        context = GLib.main_context_default()
        while context.pending():
            context.iteration()
        # ... and finally we test that its really there
        # FIXME: this will only work if software-center is installed
        self.assertNotEqual(appdetails.installation_date, None)

    def test_package_states(self):
        db = xapian.WritableDatabase(TEST_DB,
                                     xapian.DB_CREATE_OR_OVERWRITE)
        res = update_from_app_install_data(db, self.cache,
            datadir=os.path.join(DATA_DIR, "desktop"))
        self.assertTrue(res)
        db = StoreDatabase(TEST_DB, self.cache)
        db.open(use_axi=False)
        # test PkgStates.INSTALLED
        # FIXME: this will only work if software-center is installed
        app = Application("Ubuntu Software Center Test", "software-center")
        appdetails = app.get_details(db)
        self.assertTrue(appdetails.pkg_state in (PkgStates.INSTALLED,
                                                  PkgStates.UPGRADABLE))
        # test PkgStates.UNINSTALLED
        # test PkgStates.UPGRADABLE
        # test PkgStates.REINSTALLABLE
        # test PkgStates.INSTALLING
        # test PkgStates.REMOVING
        # test PkgStates.UPGRADING
        # test PkgStates.NEEDS_SOURCE
        app = Application("Zynjacku Test", "zynjacku-fake")
        appdetails = app.get_details(db)
        self.assertEqual(appdetails.pkg_state, PkgStates.NEEDS_SOURCE)
        # test PkgStates.NEEDS_PURCHASE
        app = Application("The expensive gem", "expensive-gem")
        appdetails = app.get_details(db)
        self.assertEqual(appdetails.pkg_state, PkgStates.NEEDS_PURCHASE)
        self.assertEqual(appdetails.icon_url,
                         "http://www.google.com/favicon.ico")
        self.assertEqual(appdetails.icon, "expensive-gem-icon-favicon")
        # test PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED
        # test PkgStates.UNKNOWN
        app = Application("Scintillant Orange", "scintillant-orange")
        appdetails = app.get_details(db)
        self.assertEqual(appdetails.pkg_state, PkgStates.NOT_FOUND)
        expected = ['use::converting', 'role::program', 'implemented-in::perl']
        self.assertEqual(appdetails.tags, set(expected))

    def test_packagename_is_application(self):
        db = StoreDatabase("/var/cache/software-center/xapian", self.cache)
        db.open()
        # apt has no app
        self.assertEqual(db.get_apps_for_pkgname("apt"), set())
        # but software-center has
        self.assertEqual(len(db.get_apps_for_pkgname("software-center")), 1)

    @unittest.skipIf(not os.path.exists("/var/lib/apt-xapian-index/index"),
                     "Need populated apt-xapian-index for this test")
    def test_whats_new(self):
        db = StoreDatabase("/var/cache/software-center/xapian", self.cache)
        db.open()
        query = xapian.Query("")
        enquire = xapian.Enquire(db.xapiandb)
        enquire.set_query(query)
        value_time = db._axi_values["catalogedtime"]
        enquire.set_sort_by_value(value_time, reverse=True)
        matches = enquire.get_mset(0, 20)
        last_time = 0
        for m in matches:
            doc = m.document
            doc.get_value(value_time) >= last_time
            last_time = doc.get_value(value_time)

    @patch("softwarecenter.backend.ubuntusso.UbuntuSSO"
           ".find_oauth_token_sync")
    def test_for_purchase_apps_date_published(self, mock_find_oauth):
        # pretend we have no token
        mock_find_oauth.return_value = None
        #os.environ["SOFTWARE_CENTER_DEBUG_HTTP"] = "1"
        #os.environ["SOFTWARE_CENTER_AGENT_HOST"] = "http://sc.staging.ubuntu.com/"
        # staging does not have a valid cert
        os.environ["PISTON_MINI_CLIENT_DISABLE_SSL_VALIDATION"] = "1"
        cache = get_test_pkg_info()
        db = xapian.inmemory_open()
        res = update_from_software_center_agent(db, cache, ignore_cache=True)
        self.assertTrue(res)

        for p in db.postlist(""):
            doc = db.get_document(p.docid)
            date_published = doc.get_value(XapianValues.DATE_PUBLISHED)
            # make sure that a date_published value is provided
            self.assertNotEqual(date_published, "")
            self.assertNotEqual(date_published, None)
        #del os.environ["SOFTWARE_CENTER_AGENT_HOST"]

    def test_hardware_requirements_satisfied(self):
        with patch.object(AppDetails, 'hardware_requirements') as mock_hw:
            # setup env
            db = get_test_db()
            app = Application("", "software-center")
            mock_hw.__get__ = Mock()
            # not good
            mock_hw.__get__.return_value={
                'hardware::gps' : 'no',
                'hardware::video:opengl' : 'yes',
                }
            details = AppDetails(db, application=app)
            self.assertFalse(details.hardware_requirements_satisfied)
            # this if good
            mock_hw.__get__.return_value={
                'hardware::video:opengl' : 'yes',
                }
            self.assertTrue(details.hardware_requirements_satisfied)
            # empty is satisfied
            mock_hw.__get__.return_value={}
            self.assertTrue(details.hardware_requirements_satisfied)

    @patch("softwarecenter.db.application.get_region_cached")
    def test_region_requirements_satisfied(self, mock_region_discover):
        mock_region_discover.return_value = {
            'country' : 'Germany',
            'countrycode' : 'DE',
            }
        with patch.object(AppDetails, 'tags') as mock_tags:
            # setup env
            db = get_test_db()
            app = Application("", "software-center")
            mock_tags.__get__ = Mock()
            # not good
            mock_tags.__get__.return_value = [REGIONTAG+"ZM"]
            details = AppDetails(db, application=app)
            self.assertFalse(details.region_requirements_satisfied)
            # this if good
            mock_tags.__get__.return_value = [REGIONTAG+"DE"]
            self.assertTrue(details.region_requirements_satisfied)
            # empty is satisfied
            mock_tags.__get__.return_value=["other::tag"]
            self.assertTrue(details.region_requirements_satisfied)

    def test_parse_axi_values_file(self):
        s = """
# This file contains the mapping between names of numeric values indexed in the
# APT Xapian index and their index
#
# Xapian allows to index numeric values as well as keywords and to use them for
# all sorts of useful querying tricks.  However, every numeric value needs to
# have a unique index, and this configuration file is needed to record which
# indices are allocated and to provide a mnemonic name for them.
#
# The format is exactly like /etc/services with name, number and optional
# aliases, with the difference that the second column does not use the
# "/protocol" part, which would be meaningless here.

version	0	# package version
catalogedtime	1	# Cataloged timestamp
installedsize	2	# installed size
packagesize	3	# package size
app-popcon	4	# app-install .desktop popcon rank
"""
        fname = "axi-test-values"
        with open(fname, "w") as f:
            f.write(s)
        self.addCleanup(os.remove, fname)

        #db = StoreDatabase("/var/cache/software-center/xapian", self.cache)
        axi_values = parse_axi_values_file(fname)
        self.assertNotEqual(axi_values, {})
        #print axi_values

    @unittest.skipIf(os.path.exists("/var/lib/debtags/package-tags"), 
                     "a-x-i will has not run apttags.py plugin")
    def test_appdetails(self):
        db = get_test_db()
        # see "apt-cache show casper|grep ^Tag"
        details = AppDetails(db, application=Application("", "casper"))
        self.assertTrue(len(details.tags) > 2)

    def test_app_enquire(self):
        db = StoreDatabase(cache=self.cache)
        db.open()
        # test the AppEnquire engine
        enquirer = AppEnquire(self.cache, db)
        enquirer.set_query(xapian.Query("a"),
                           nonblocking_load=False)
        self.assertTrue(len(enquirer.get_docids()) > 0)
        # FIXME: test more of the interface

    def test_is_pkgname_known(self):
        db = StoreDatabase(cache=self.cache)
        db.open()
        self.assertTrue(db.is_pkgname_known("apt"))
        self.assertFalse(db.is_pkgname_known("i+am-not-a-pkg"))


class UtilsTestCase(unittest.TestCase):

    def test_utils_get_installed_package_list(self):
        installed_pkgs = get_installed_package_list()
        self.assertTrue(len(installed_pkgs) > 0)

    def test_utils_get_installed_apps_list(self):
        db = get_test_db()
        # installed pkgs
        installed_pkgs = get_installed_package_list()
        # the installed apps
        installed_apps = get_installed_apps_list(db)
        self.assertTrue(len(installed_apps) > 0)
        self.assertTrue(len(installed_pkgs) > len(installed_apps))


def make_purchased_app_details(db=None, supported_series=None):
    """Return an AppDetail instance with the required attributes."""
    app = make_software_center_agent_app_dict()
    subscription = make_software_center_agent_subscription_dict(app)

    if supported_series != None:
        subscription['application']['series'] = supported_series
    else:
        # If no supportod_series kwarg was provided, we ensure the
        # current series/arch is supported.
        distro = softwarecenter.distro.get_distro()
        subscription['application']['series'] = {
            distro.get_codename(): [distro.get_architecture()]
            }

    item = PistonResponseObject.from_dict(subscription)
    parser = SCAPurchasedApplicationParser(item)

    if db is None:
        db = get_test_db()

    doc = parser.make_doc(db._aptcache)
    app_details = AppDetails(db, doc)
    return app_details


class AppDetailsSCAApplicationParser(unittest.TestCase):

    def setUp(self):
        self.db = get_test_db()

    def _get_app_details_from_override(self, override_dict):
        app_dict = make_software_center_agent_app_dict()
        app_dict.update(override_dict)
        app_details =  self._get_app_details_from_app_dict(app_dict)
        return app_details

    def _get_app_details_from_app_dict(self, app_dict):
        item = PistonResponseObject.from_dict(app_dict)
        parser = SCAApplicationParser(item)
        doc = parser.make_doc(self.db._aptcache)
        app_details = AppDetails(self.db, doc)
        return app_details

    def test_currency(self):
        app_details = self._get_app_details_from_override({
                "price": "24.95"})
        self.assertEqual("US$", app_details.currency)
        self.assertEqual("24.95", app_details.raw_price)

    @patch('os.path.exists')
    def test_channel_detection_partner(self, mock):
        # we need to patch os.path.exists as "AppDetails.channelname" will
        # check if there is a matching channel description file on disk
        os.path.exists.return_value = True
        app_details = self._get_app_details_from_override({
                "archive_root": "http://archive.canonical.com/"})
        # ensure that archive.canonical.com archive roots are detected
        # as the partner channel
        dist = softwarecenter.distro.get_distro().get_codename()
        self.assertEqual(app_details.channelname, "%s-partner" % dist)

    @patch('os.path.exists')
    def test_channel_detection_extras(self, mock):
        # we need to patch os.path.exists as "AppDetails.channelname" will
        # check if there is a matching channel description file on disk
        os.path.exists.return_value = True
        # setup dict
        app_details = self._get_app_details_from_override({
                "archive_root": "http://extras.ubuntu.com/"})
        # ensure that archive.canonical.com archive roots are detected
        # as the partner channel
        self.assertEqual(app_details.channelname, "ubuntu-extras")

    def test_date_no_published(self):
        app_details = self._get_app_details_from_override({
                "date_published": "None"})
        # ensure that archive.canonical.com archive roots are detected
        # as the partner channel
        self.assertEqual(app_details.date_published, "")
        # and again
        app_details = self._get_app_details_from_override({
                "date_published": "2012-01-21 02:15:10.358926"})
        # ensure that archive.canonical.com archive roots are detected
        # as the partner channel
        self.assertEqual(app_details.date_published, "2012-01-21 02:15:10")

    @patch("softwarecenter.db.update.get_region_cached")
    def test_no_region_tags_passes(self, get_region_cached_mock):
        """Do not skip apps with no white or blacklist tags."""
        get_region_cached_mock.return_value = { "countrycode" : "es",
                                              }
        app_dict = make_software_center_agent_app_dict({
                "debtags": []})
        item = PistonResponseObject.from_dict(app_dict)
        parser = SCAApplicationParser(item)
        doc = parser.make_doc(self.db._aptcache)
        self.assertNotEqual(doc, None)

    @patch("softwarecenter.db.update.get_region_cached")
    def test_region_blacklist(self, get_region_cached_mock):
        """Test that the region blacklist ignores blacklisted locations"""
        get_region_cached_mock.return_value = { "countrycode" : "es",
                                              }
        app_dict = make_software_center_agent_app_dict({
                "debtags": ["%s%s" % (REGION_BLACKLIST_TAG, "es")]})
        item = PistonResponseObject.from_dict(app_dict)
        parser = SCAApplicationParser(item)
        doc = parser.make_doc(self.db._aptcache)
        self.assertEqual(doc, None)

    @patch("softwarecenter.db.update.get_region_cached")
    def test_region_blacklist_blacklists(self, get_region_cached_mock):
        """Test that the region blacklist adds non-blacklisted locations"""
        get_region_cached_mock.return_value = { "countrycode" : "de",
                                              }
        app_dict = make_software_center_agent_app_dict({
                "debtags": ["%s%s" % (REGION_BLACKLIST_TAG, "ES")]})
        item = PistonResponseObject.from_dict(app_dict)
        parser = SCAApplicationParser(item)
        doc = parser.make_doc(self.db._aptcache)
        self.assertNotEqual(doc, None)

    @patch("softwarecenter.db.update.get_region_cached")
    def test_region_whitelist_whitelists(self, get_region_cached_mock):
        """Test that the whitelist adds whitelisted locations"""
        get_region_cached_mock.return_value = { "countrycode" : "es",
                                              }
        app_dict = make_software_center_agent_app_dict({
                "debtags": ["%s%s" % (REGION_WHITELIST_TAG, "ES"),
                            "%s%s" % (REGION_BLACKLIST_TAG, "CA"),
                            "%s%s" % (REGION_WHITELIST_TAG, "US")]})
        item = PistonResponseObject.from_dict(app_dict)
        parser = SCAApplicationParser(item)
        doc = parser.make_doc(self.db._aptcache)
        self.assertNotEqual(doc, None)

    @patch("softwarecenter.db.update.get_region_cached")
    def test_region_whitelist_blacklists(self, get_region_cached_mock):
        """Test that the whitelist ignores non-whitelist locations"""
        get_region_cached_mock.return_value = { "countrycode" : "de",
                                              }
        app_dict = make_software_center_agent_app_dict({
                "debtags": ["%s%s" % (REGION_WHITELIST_TAG, "ES"),
                            "%s%s" % (REGION_BLACKLIST_TAG, "CA"),
                            "%s%s" % (REGION_WHITELIST_TAG, "US")]})
        # see _get_app_details_from_app_dict
        item = PistonResponseObject.from_dict(app_dict)
        parser = SCAApplicationParser(item)
        doc = parser.make_doc(self.db._aptcache)
        self.assertEqual(doc, None)

    @patch("softwarecenter.db.update.get_region_cached")
    def test_region_whiteandblack_blacklists(self, get_region_cached_mock):
        """Ignore regions that are in both black and whitelists."""
        get_region_cached_mock.return_value = { "countrycode" : "de",
                                              }
        app_dict = make_software_center_agent_app_dict({
                "debtags": ["%s%s" % (REGION_WHITELIST_TAG, "DE"),
                            "%s%s" % (REGION_BLACKLIST_TAG, "DE"),
                            "%s%s" % (REGION_BLACKLIST_TAG, "US"),
                            "%s%s" % (REGION_WHITELIST_TAG, "ES")]})
        # see _get_app_details_from_app_dict
        item = PistonResponseObject.from_dict(app_dict)
        parser = SCAApplicationParser(item)
        doc = parser.make_doc(self.db._aptcache)
        self.assertEqual(doc, None)


class AppDetailsPkgStateTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Set these as class attributes as we don't modify either
        # during the tests.
        cls.distro = softwarecenter.distro.get_distro()
        cls.db = get_test_db()

    def test_package_state_purchased_enable_repo(self):
        # If the current series is supported by the app, the state should
        # be PURCHASED_BUT_REPO_MUST_BE_ENABLED.
        app_details = make_purchased_app_details(self.db,
            supported_series={
                'current-1': ['i386', 'amd64'],
                self.distro.get_codename(): [self.distro.get_architecture()]
                })

        state = app_details.pkg_state

        self.assertEqual(
            PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED,
            state)

    def test_package_state_purchased_not_available(self):
        # If the current series is NOT supported by the app, the state should
        # be PURCHASED_BUT_NOT_AVAILABLE_FOR_SERIES.
        app_details = make_purchased_app_details(self.db,
            supported_series={
                'current-1': ['i386', 'amd64'],
                self.distro.get_codename(): ['newarch', 'amdm128'],
                })

        state = app_details.pkg_state

        self.assertEqual(
            PkgStates.PURCHASED_BUT_NOT_AVAILABLE_FOR_SERIES,
            state)

    def test_package_state_no_series(self):
        # Until the fix for bug 917109 is deployed on production, we
        # should default to the current (broken) behaviour of
        # indicating that the repo just needs enabling.
        app_details = make_purchased_app_details(self.db, supported_series=None)

        state = app_details.pkg_state

        self.assertEqual(
            PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED,
            state)

    def test_package_state_arch_any(self):
        # In the future the supported arches returned by sca will include
        # any - let's not break when that happens.
        app_details = make_purchased_app_details(self.db,
            supported_series={
                'current-1': ['i386', 'amd64'],
                self.distro.get_codename(): ['newarch', 'any'],
                })

        state = app_details.pkg_state

        self.assertEqual(
            PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED,
            state)


class MultipleVersionsSupportTestCase(unittest.TestCase):

    def _make_version(self, not_automatic):
        ver = Mock(_Version)
        ver.description ="not_automatic: %s" % not_automatic
        ver.summary ="summary not_automatic: %s" % not_automatic
        ver.version = "version not_automatic: %s" % not_automatic
        mock_origin = Mock()
        if not_automatic:
            mock_origin.archive = "precise-backports"
        else:
            mock_origin.archive = "precise"
        ver.origins = [ mock_origin ]
        ver.not_automatic = not_automatic
        return ver

    def test_not_automatic_channel_support(self):
        db = get_test_db()
        app = Application("", "software-center")
        details = app.get_details(db)
        versions = [
            self._make_version(not_automatic=True),
            self._make_version(not_automatic=False) ]
        details._pkg.versions = versions
        details._pkg.candidate = versions[1]
        self.assertEqual(
            details.get_not_automatic_archive_versions(),
            [  (versions[1].version, "precise"),
               (versions[0].version, "precise-backports") ])

    def test_multiple_version_pkg_states(self):
        db = get_test_db()
        app = Application("", "software-center")
        details = app.get_details(db)
        normal_version = self._make_version(not_automatic=False)
        not_automatic_version = self._make_version(not_automatic=True)
        details._pkg.versions = [normal_version, not_automatic_version]
        details._pkg.installed = normal_version
        details._pkg.is_installed = True
        # disabled for now
        #details._pkg.is_upgradable = True
        self.assertEqual(details.pkg_state, PkgStates.INSTALLED)
        app.archive_suite = not_automatic_version
        self.assertEqual(details.pkg_state, PkgStates.FORCE_VERSION)

    def test_not_automatic_version(self):
        db = get_test_db()
        app = Application("", "software-center")
        details = app.get_details(db)
        normal_version = self._make_version(not_automatic=False)
        not_automatic_version = self._make_version(not_automatic=True)
        details._pkg.versions = [normal_version, not_automatic_version]
        # force not-automatic with invalid data
        self.assertRaises(
            ValueError, details.force_not_automatic_archive_suite, "random-string")
        # force not-automatic with valid data
        self.assertTrue(details.force_not_automatic_archive_suite(
                not_automatic_version.origins[0].archive))
        # ensure we get the description of the not-automatic version
        self.assertEqual(details.description,
                         not_automatic_version.description)
        self.assertEqual(details.summary,
                         not_automatic_version.summary)
        self.assertEqual(details.version,
                         not_automatic_version.version)
        self.assertEqual(app.archive_suite,
                         not_automatic_version.origins[0].archive)
        # clearing works
        details.force_not_automatic_archive_suite("")
        self.assertEqual(app.archive_suite, "")


class XapianQueryParserWorkarounds(unittest.TestCase):
    """This TestCase demonstrates the issues around the query
       parser wildcard support if the "-" char is part of the 
       pkgname and tests the workaround for this

       (http://trac.xapian.org/ticket/128)
    """

    def setUp(self):
        datadir = os.path.join(DATA_DIR, "desktop")
        self.db = get_test_db_from_app_install_data(datadir)

    def test_name_mangling_for_query_parser(self):
        # test that pkgnames with "-" get added in a mangled form
        i=0
        for it in self.db.postlist("APMsoftware_center"):
            i+=1
        self.assertEqual(i, 1)

    def test_query_parser_wildcard(self):
        enquire = xapian.Enquire(self.db)
        parser = xapian.QueryParser()
        parser.set_database(self.db)
        parser.add_prefix("pkg_wildcard", "AP")
        # this demonstrates the xapian bug with the query parser 
        # and "-" special chars, note that once this test fails (i.e.
        # the returned mset is "1" we can remove this workaround
        query = parser.parse_query(
            "pkg_wildcard:software-*", xapian.QueryParser.FLAG_WILDCARD)
        enquire.set_query(query)
        mset = enquire.get_mset(0, 100)
        self.assertEqual(len(mset), 0)
        # and the workaround
        parser.add_prefix("pkg_wildcard", "APM")
        query = parser.parse_query(
            "pkg_wildcard:software_*", xapian.QueryParser.FLAG_WILDCARD)
        enquire.set_query(query)
        mset = enquire.get_mset(0, 100)
        self.assertEqual(len(mset), 1)


class TrackDBTestCase(unittest.TestCase):

    def test_track_db_open(self):
        tmpdir = tempfile.mkdtemp()
        tmpstamp = os.path.join(tmpdir, "update-stamp")
        open(tmpstamp, "w")
        softwarecenter.paths.APT_XAPIAN_INDEX_UPDATE_STAMP_PATH = tmpstamp
        softwarecenter.paths.APT_XAPIAN_INDEX_DB_PATH = \
            softwarecenter.paths.XAPIAN_PATH
        db = get_test_db()
        db._axi_stamp_monitor = None
        db._on_axi_stamp_changed = Mock()
        self.assertFalse(db._on_axi_stamp_changed.called)
        db.open(use_axi=True)
        do_events()
        self.assertFalse(db._on_axi_stamp_changed.called)
        do_events()
        #print "modifiyng stampfile: ", tmpstamp
        os.utime(tmpstamp, (0, 0))
        # wait up to 5s until the gvfs delivers the signal
        for i in range(50):
            do_events()
            time.sleep(0.1)
            if db._on_axi_stamp_changed.called:
                break
        self.assertTrue(db._on_axi_stamp_changed.called)



class DBSearchTestCase(unittest.TestCase):

    APP_INFO_JSON="""
[
 {
    "application_name": "The apt",
    "package_name": "apt",
    "description": "meep"
 }
]
"""

    @classmethod
    def setUpClass(cls):
        cache = get_pkg_info()
        cache.open()
        db = xapian.WritableDatabase(TEST_DB,
                                     xapian.DB_CREATE_OR_OVERWRITE)
        update_from_json_string(db, cache, cls.APP_INFO_JSON, origin="local")
        db.close()

    def setUp(self):
        # create a fake database to simualte a run of software-center-agent
        # create a StoreDatabase and add our other db
        self.db = get_test_db()
        self.db.add_database(xapian.Database(TEST_DB))
        self.db.open(use_axi=True)
        self.enquire = AppEnquire(self.db._aptcache, self.db)
        
    def test_search_app_pkgname_duplication_lp891613(self):
        # simulate a pkg "apt" that is both in the agent and in the x-a-i db
        search_term = "apt"
        search_query = self.db.get_query_list_from_search_entry(search_term)
        self.enquire.set_query(search_query, nonblocking_load=False)
        self.assertTrue(len(self.enquire._matches) > 2)
        for m in self.enquire._matches:
            doc = m.document
            # ensure that all hits are "apps" and do not come from a-x-i
            self.assertNotEqual(
                doc.get_value(XapianValues.PKGNAME), "")

    def test_search_custom_pkgs_list_lp1043159(self):
        # simulate a pkg "apt" that is both in the agent and in the x-a-i db
        pkgs = ["apt","gedit"]
        search_query = self.db.get_query_for_pkgnames(pkgs)
        self.enquire.set_query(search_query, 
                               # custom package lists are always in this mode
                               nonapps_visible=NonAppVisibility.ALWAYS_VISIBLE,
                               nonblocking_load=False)
        self.assertEqual(len(self.enquire._matches), 2)


if __name__ == "__main__":
    unittest.main()
